"""Constructor de DTE para el SII de Chile (Tanda 7).

Genera el documento tributario electrónico con la **forma real** que exige el
SII (Encabezado/IdDoc/Emisor/Receptor/Totales + Detalle + TED) y calcula el IVA
según el tipo y **si cada línea está afecta o exenta**:

  · **Boleta electrónica (39)** — precios con IVA incluido en las líneas
    afectas: el neto se despeja (`neto = afecto / 1.19`).
  · **Boleta exenta (41)** — todas las líneas exentas, sin IVA. Es el documento
    natural de una clínica: las prestaciones médicas/odontológicas son exentas
    (D.L. 825 Art. 12 letra E N°17).
  · **Factura electrónica (33)** — precios netos afectos: el IVA se agrega.
  · **Factura exenta (34)** — todas las líneas exentas.
  · **Nota de crédito (61)** — anula un documento anterior (referencia al folio).

Las líneas exentas se marcan con **IndExe=1** y suman a `MntExento`; una boleta
puede mezclar una consulta exenta con un examen afecto y el IVA recae solo sobre
el examen.

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
    "boleta_exenta": "41",
    "factura_electronica": "33",
    "factura_exenta": "34",
    "nota_credito": "61",
}

# Tipos cuyas líneas van SIEMPRE exentas, sin importar el flag de cada línea.
TIPOS_EXENTOS = {"boleta_exenta", "factura_exenta"}
# Tipos "boleta": las líneas afectas traen el IVA incluido en el precio.
TIPOS_BOLETA = {"boleta_electronica", "boleta_exenta"}


def _clp(x: float) -> int:
    """El peso chileno no usa decimales en los DTE."""
    return int(round(x))


def _sello(dd: str) -> str:
    """TED simulado: en producción es la firma RSA-SHA1 del bloque DD con la
    llave del CAF. Aquí, un digest determinista del mismo contenido."""
    return base64.b64encode(hashlib.sha256(dd.encode()).digest()).decode()[:64]


def _track_id(xml: str) -> str:
    return str(int(hashlib.sha256(xml.encode()).hexdigest(), 16) % 10_000_000_000)


def _es_exenta(tipo_documento: str, item: dict) -> bool:
    return tipo_documento in TIPOS_EXENTOS or bool(item.get("exento", False))


def _totales(tipo_documento: str, items: list[dict]) -> tuple[int, int, int, int]:
    """Devuelve (neto, iva, exento, total) en CLP.

    Separa líneas afectas de exentas. En una boleta la línea afecta trae IVA
    incluido (se despeja el neto); en una factura la línea afecta es neta (el
    IVA se agrega). Las líneas exentas nunca llevan IVA."""
    es_boleta = tipo_documento in TIPOS_BOLETA
    afecto_bruto = 0
    exento = 0
    for it in items:
        monto = _clp(it["cantidad"] * it["precio_unitario"])
        if _es_exenta(tipo_documento, it):
            exento += monto
        else:
            afecto_bruto += monto

    if es_boleta:
        # Precio afecto con IVA incluido -> se despeja el neto.
        neto = _clp(afecto_bruto / (1 + IVA_TASA)) if afecto_bruto else 0
        iva = afecto_bruto - neto
    else:
        # Factura / nota de crédito: la línea afecta es neta -> IVA por fuera.
        neto = afecto_bruto
        iva = _clp(afecto_bruto * IVA_TASA)

    total = neto + iva + exento
    return neto, iva, exento, total


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
    neto, iva, exento, total = _totales(tipo_documento, items)

    cfg = emitter.config or {}
    rut_emisor = emitter.tax_id
    rut_receptor = (receptor or {}).get("tax_id") or "66666666-6"  # 66.666.666-6 = consumidor final (SII)
    razon_receptor = (receptor or {}).get("nombre") or "Consumidor final"

    # ── Detalle ──
    detalle_xml = ""
    for i, it in enumerate(items, start=1):
        monto_item = _clp(it["cantidad"] * it["precio_unitario"])
        ind_exe = "<IndExe>1</IndExe>" if _es_exenta(tipo_documento, it) else ""
        detalle_xml += (
            f"<Detalle><NroLinDet>{i}</NroLinDet>{ind_exe}"
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

    # ── Totales (MntNeto/IVA solo si hay afecto; MntExento si hay exento) ──
    totales_xml = f"<MntNeto>{neto}</MntNeto>"
    if exento:
        totales_xml += f"<MntExe>{exento}</MntExe>"
    if iva:
        totales_xml += f"<TasaIVA>{IVA_TASA * 100:.0f}</TasaIVA><IVA>{iva}</IVA>"
    totales_xml += f"<MntTotal>{total}</MntTotal>"

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
        f"<Totales>{totales_xml}</Totales>"
        "</Encabezado>"
        f"{detalle_xml}{referencia_xml}{ted_xml}"
        "</Documento></DTE>"
    )

    detalle_impuesto = {"tipo": "IVA", "tasa": IVA_TASA, "monto": iva, "exento": exento}
    if exento and not iva:
        detalle_impuesto["nota"] = "Documento exento de IVA (prestación no afecta, D.L. 825 Art. 12 E)"

    return {
        "codigo": codigo,
        "jurisdiccion": "federal",
        "organo": "SII",
        "moneda": "CLP",
        "neto": neto,
        "exento": exento,
        "impuesto": iva,
        "total": total,
        "impuesto_detalle": detalle_impuesto,
        "sello": sello,
        "track_id": _track_id(xml),
        "xml": xml,
        "estado": "aceptado",  # respuesta del SII simulada; hook real: pendiente -> QueryEstDte
    }
