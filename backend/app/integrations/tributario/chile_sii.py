"""Constructor de DTE para el SII de Chile (Tanda 7).

Genera el documento tributario electrónico con la **forma real** que exige el
SII (Encabezado/IdDoc/Emisor/Receptor/Totales + Detalle + TED) y calcula el IVA
según el tipo:

  · **Boleta electrónica (39)** — precios con IVA incluido: el neto se despeja
    del total (`neto = total / 1.19`).
  · **Factura electrónica (33)** — precios netos: el IVA se agrega
    (`total = neto + neto*0.19`).
  · **Nota de crédito (61)** — anula un documento anterior; referencia al folio
    original con `CodRef=1` (anula documento de referencia).

Punto de enganche real (documentado, no ejecutado aquí): el timbre `TED` se
firma con la llave privada del CAF (RSA-SHA1) y el sobre `EnvioBOLETA`/
`EnvioDTE` se firma con el certificado digital del emisor y se despacha al SII
(`palena.sii.cl`), que responde con un **TrackID**; el estado real se consulta
luego con `QueryEstDte`. Aquí el sello y el TrackID son deterministas
(hash del contenido) para poder verificar el flujo end-to-end sin credenciales.
"""

import base64
import hashlib
from xml.sax.saxutils import escape

IVA_TASA = 0.19

CODIGOS = {
    "boleta_electronica": "39",
    "factura_electronica": "33",
    "nota_credito": "61",
}


def _clp(x: float) -> int:
    """El peso chileno no usa decimales en los DTE."""
    return int(round(x))


def _sello(dd: str) -> str:
    """TED simulado: en producción es la firma RSA-SHA1 del bloque DD con la
    llave del CAF. Aquí, un digest determinista del mismo contenido."""
    return base64.b64encode(hashlib.sha256(dd.encode()).digest()).decode()[:64]


def _track_id(xml: str) -> str:
    return str(int(hashlib.sha256(xml.encode()).hexdigest(), 16) % 10_000_000_000)


def _totales(tipo_documento: str, items: list[dict]) -> tuple[int, int, int]:
    """Devuelve (neto, iva, total) en CLP según la convención del tipo."""
    bruto = sum(_clp(it["cantidad"] * it["precio_unitario"]) for it in items)
    if tipo_documento == "boleta_electronica":
        # Precios con IVA incluido -> se despeja el neto.
        neto = _clp(bruto / (1 + IVA_TASA))
        iva = bruto - neto
        total = bruto
    else:
        # Factura / nota de crédito: precios netos -> IVA por fuera.
        neto = bruto
        iva = _clp(bruto * IVA_TASA)
        total = neto + iva
    return neto, iva, total


def build_dte(
    *,
    tipo_documento: str,
    folio: int,
    caf_ref: str | None,
    emitter,
    receptor: dict | None,
    items: list[dict],
    fecha: str,
    referencia: dict | None = None,
) -> dict:
    """Construye el DTE completo. `referencia` (solo NC): {"tipo": "39",
    "folio": 123, "fecha": "2026-08-10", "razon": "Anula boleta"}."""
    codigo = CODIGOS[tipo_documento]
    neto, iva, total = _totales(tipo_documento, items)

    cfg = emitter.config or {}
    rut_emisor = emitter.tax_id
    rut_receptor = (receptor or {}).get("tax_id") or "66666666-6"  # 66.666.666-6 = consumidor final (SII)
    razon_receptor = (receptor or {}).get("nombre") or "Consumidor final"

    # ── Detalle ──
    detalle_xml = ""
    for i, it in enumerate(items, start=1):
        monto_item = _clp(it["cantidad"] * it["precio_unitario"])
        detalle_xml += (
            f"<Detalle><NroLinDet>{i}</NroLinDet>"
            f"<NmbItem>{escape(str(it['descripcion']))}</NmbItem>"
            f"<QtyItem>{it['cantidad']}</QtyItem>"
            f"<PrcItem>{_clp(it['precio_unitario'])}</PrcItem>"
            f"<MontoItem>{monto_item}</MontoItem></Detalle>"
        )

    # ── Referencia (NC) ──
    referencia_xml = ""
    if referencia is not None:
        referencia_xml = (
            "<Referencia><NroLinRef>1</NroLinRef>"
            f"<TpoDocRef>{escape(str(referencia['tipo']))}</TpoDocRef>"
            f"<FolioRef>{referencia['folio']}</FolioRef>"
            f"<FchRef>{escape(str(referencia['fecha']))}</FchRef>"
            "<CodRef>1</CodRef>"  # 1 = anula documento de referencia
            f"<RazonRef>{escape(str(referencia.get('razon', 'Anula documento')))}</RazonRef>"
            "</Referencia>"
        )

    # ── TED (timbre) ──
    primer_item = escape(str(items[0]["descripcion"]))[:40] if items else ""
    dd = (
        f"<DD><RE>{rut_emisor}</RE><TD>{codigo}</TD><F>{folio}</F><FE>{fecha}</FE>"
        f"<RR>{rut_receptor}</RR><RSR>{escape(razon_receptor)[:40]}</RSR>"
        f"<MNT>{total}</MNT><IT1>{primer_item}</IT1>"
        f"<CAF>{escape(caf_ref or 'CAF-SIM')}</CAF></DD>"
    )
    sello = _sello(dd)
    ted_xml = f"<TED version=\"1.0\">{dd}<FRMT algoritmo=\"SHA1withRSA\">{sello}</FRMT></TED>"

    # ── IVA (las boletas exentas no lo llevan; aquí todo es afecto) ──
    iva_xml = f"<TasaIVA>{IVA_TASA * 100:.0f}</TasaIVA><IVA>{iva}</IVA>" if iva else ""

    xml = (
        f'<DTE version="1.0"><Documento ID="T{codigo}F{folio}">'
        "<Encabezado>"
        f"<IdDoc><TipoDTE>{codigo}</TipoDTE><Folio>{folio}</Folio><FchEmis>{fecha}</FchEmis></IdDoc>"
        f"<Emisor><RUTEmisor>{rut_emisor}</RUTEmisor>"
        f"<RznSoc>{escape(emitter.razon_social)}</RznSoc>"
        f"<GiroEmis>{escape(emitter.giro or '')}</GiroEmis>"
        f"<Acteco>{escape(str(cfg.get('acteco', '')))}</Acteco>"
        f"<DirOrigen>{escape(emitter.direccion or '')}</DirOrigen>"
        f"<CmnaOrigen>{escape(str(cfg.get('comuna', '')))}</CmnaOrigen></Emisor>"
        f"<Receptor><RUTRecep>{rut_receptor}</RUTRecep>"
        f"<RznSocRecep>{escape(razon_receptor)}</RznSocRecep></Receptor>"
        f"<Totales><MntNeto>{neto}</MntNeto>{iva_xml}<MntTotal>{total}</MntTotal></Totales>"
        "</Encabezado>"
        f"{detalle_xml}{referencia_xml}{ted_xml}"
        "</Documento></DTE>"
    )

    return {
        "codigo": codigo,
        "jurisdiccion": "federal",
        "organo": "SII",
        "moneda": "CLP",
        "neto": neto,
        "exento": 0,
        "impuesto": iva,
        "total": total,
        "impuesto_detalle": {"tipo": "IVA", "tasa": IVA_TASA, "monto": iva},
        "sello": sello,
        "track_id": _track_id(xml),
        "xml": xml,
        "estado": "aceptado",  # respuesta del SII simulada; hook real: pendiente -> QueryEstDte
    }
