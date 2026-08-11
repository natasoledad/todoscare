"""Constructor de CFDI 4.0 para el SAT de México (Tanda 7).

Genera el Comprobante Fiscal Digital por Internet con la **forma real** del SAT
(cfdi:Comprobante → Emisor / Receptor / Conceptos con Impuestos / Impuestos +
complemento TimbreFiscalDigital):

  · **factura** → CFDI de **Ingreso** (`TipoDeComprobante = "I"`).
  · **nota_credito** → CFDI de **Egreso** (`TipoDeComprobante = "E"`).

El **IVA** es 16%. Se respeta el flag por línea: una prestación **exenta**
(muchos servicios médicos lo son) va con `ObjetoImp = "01"` (no objeto de
impuesto) y no traslada IVA; una **afecta** va con `ObjetoImp = "02"` y traslada
IVA 16%.

Punto de enganche real (documentado, no ejecutado aquí): el CFDI se sella con el
CSD (certificado de sello digital) del emisor y se envía a un **PAC** (Proveedor
Autorizado de Certificación), que lo timbra ante el SAT y devuelve el
**TimbreFiscalDigital** (UUID/folio fiscal, SelloSAT, NoCertificadoSAT,
FechaTimbrado). Aquí el UUID y los sellos son deterministas (hash del contenido)
para verificar el flujo sin CSD ni contrato PAC.
"""

import hashlib

from xml.sax.saxutils import escape

IVA_TASA = 0.16

TIPO_COMPROBANTE = {"factura": "I", "nota_credito": "E"}

RFC_PUBLICO_GENERAL = "XAXX010101000"  # receptor genérico (público en general)


def _mxn(x: float) -> float:
    return round(float(x), 2)


def _uuid(seed: str) -> str:
    h = hashlib.sha256(seed.encode()).hexdigest()
    return f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}".upper()


def _sello(seed: str) -> str:
    return hashlib.sha256(("sello|" + seed).encode()).hexdigest()


def _es_exenta(item: dict) -> bool:
    return bool(item.get("exento", False))


def build_cfdi(
    *,
    tipo_documento: str,
    numero: int,
    serie: str | None,
    emitter,
    receptor: dict | None,
    items: list[dict],
    fecha: str,
) -> dict:
    tipo_comp = TIPO_COMPROBANTE[tipo_documento]
    cfg = emitter.config or {}

    neto = 0.0     # base afecta (16%)
    exento = 0.0
    for it in items:
        importe = _mxn(it["cantidad"] * it["precio_unitario"])
        if _es_exenta(it):
            exento += importe
        else:
            neto += importe
    neto, exento = _mxn(neto), _mxn(exento)
    iva = _mxn(neto * IVA_TASA)
    subtotal = _mxn(neto + exento)
    total = _mxn(subtotal + iva)

    rfc_receptor = (receptor or {}).get("tax_id") or RFC_PUBLICO_GENERAL
    nombre_receptor = (receptor or {}).get("nombre") or "PUBLICO EN GENERAL"

    conceptos_xml = ""
    for it in items:
        importe = _mxn(it["cantidad"] * it["precio_unitario"])
        if _es_exenta(it):
            impuestos_concepto = ""
            objeto_imp = "01"  # no objeto de impuesto
        else:
            imp_iva = _mxn(importe * IVA_TASA)
            objeto_imp = "02"  # sí objeto de impuesto
            impuestos_concepto = (
                "<cfdi:Impuestos><cfdi:Traslados>"
                f'<cfdi:Traslado Base="{importe:.2f}" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.160000" Importe="{imp_iva:.2f}"/>'
                "</cfdi:Traslados></cfdi:Impuestos>"
            )
        conceptos_xml += (
            f'<cfdi:Concepto ClaveProdServ="85121600" Cantidad="{it["cantidad"]}" ClaveUnidad="E48" '
            f'Descripcion="{escape(str(it["descripcion"]))}" ValorUnitario="{_mxn(it["precio_unitario"]):.2f}" '
            f'Importe="{importe:.2f}" ObjetoImp="{objeto_imp}">{impuestos_concepto}</cfdi:Concepto>'
        )

    impuestos_xml = (
        f'<cfdi:Impuestos TotalImpuestosTrasladados="{iva:.2f}"><cfdi:Traslados>'
        f'<cfdi:Traslado Base="{neto:.2f}" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.160000" Importe="{iva:.2f}"/>'
        "</cfdi:Traslados></cfdi:Impuestos>"
        if iva
        else ""
    )

    seed = f"CFDI|{emitter.tax_id}|{tipo_comp}|{serie}|{numero}|{total}|{fecha}"
    uuid_fiscal = _uuid(seed)
    sello_cfd = _sello(seed)
    sello_sat = _sello("sat|" + seed)
    cp = str(cfg.get("codigo_postal", "01000"))
    serie_attr = f'Serie="{escape(serie)}" ' if serie else ""

    xml = (
        '<cfdi:Comprobante Version="4.0" '
        f'{serie_attr}Folio="{numero}" Fecha="{fecha}" '
        f'SubTotal="{subtotal:.2f}" Moneda="MXN" Total="{total:.2f}" '
        f'TipoDeComprobante="{tipo_comp}" Exportacion="01" MetodoPago="PUE" LugarExpedicion="{escape(cp)}" '
        f'Sello="{sello_cfd}">'
        f'<cfdi:Emisor Rfc="{emitter.tax_id}" Nombre="{escape(emitter.razon_social)}" '
        f'RegimenFiscal="{escape(str(cfg.get("regimen_fiscal", "612")))}"/>'
        f'<cfdi:Receptor Rfc="{rfc_receptor}" Nombre="{escape(nombre_receptor)}" '
        f'DomicilioFiscalReceptor="{escape(cp)}" RegimenFiscalReceptor="616" '
        f'UsoCFDI="{escape(str((receptor or {}).get("uso_cfdi", cfg.get("uso_cfdi", "G03"))))}"/>'
        f"<cfdi:Conceptos>{conceptos_xml}</cfdi:Conceptos>"
        f"{impuestos_xml}"
        "<cfdi:Complemento>"
        f'<tfd:TimbreFiscalDigital Version="1.1" UUID="{uuid_fiscal}" FechaTimbrado="{fecha}" '
        f'RfcProvCertif="PAC010101000" SelloCFD="{sello_cfd}" NoCertificadoSAT="00001000000500000000" SelloSAT="{sello_sat}"/>'
        "</cfdi:Complemento>"
        "</cfdi:Comprobante>"
    )

    return {
        "codigo": tipo_comp,
        "jurisdiccion": "federal",
        "organo": "SAT",
        "moneda": "MXN",
        "neto": neto,
        "exento": exento,
        "impuesto": iva,
        "total": total,
        "impuesto_detalle": {"tipo": "IVA", "tasa": IVA_TASA, "monto": iva, "uuid": uuid_fiscal},
        "sello": uuid_fiscal,  # el folio fiscal (UUID) identifica al CFDI
        "track_id": uuid_fiscal,
        "xml": xml,
        "estado": "aceptado",  # timbrado por el PAC simulado; hook real: PAC/SAT
    }
