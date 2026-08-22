"""Catálogo de conectores externos (Bloque D). Cada entrada define el hookpoint
de una integración: qué credenciales necesita y en qué dirección opera. La
clínica los activa y configura; el envío/recepción real se conecta cuando exista
el contrato/credenciales (hoy la prueba es simulada, igual que el SII)."""


def _c(tipo, nombre, categoria, descripcion, direccion, campos):
    return {"tipo": tipo, "nombre": nombre, "categoria": categoria, "descripcion": descripcion, "direccion": direccion, "campos": campos}


def _campo(clave, label, secreto=False):
    return {"clave": clave, "label": label, "secreto": secreto}


CONECTORES: list[dict] = [
    _c("sii", "SII — Documentos tributarios reales", "Tributario",
       "Emisión real de boletas/facturas al SII (hoy el transporte es simulado).", "saliente",
       [_campo("rut_emisor", "RUT emisor"), _campo("certificado", "Certificado digital (.pfx)", True), _campo("clave_certificado", "Clave del certificado", True)]),
    _c("imed", "I-Med — Bonos electrónicos", "Salud / Bonos",
       "Bonificación electrónica de Isapres/Fonasa en el punto de atención (bono previsional).", "ambas",
       [_campo("codigo_prestador", "Código prestador"), _campo("usuario", "Usuario"), _campo("clave", "Clave", True)]),
    _c("seguro_complementario", "Seguros complementarios — Reembolso/bono", "Salud / Bonos",
       "Bonifica el copago tras la previsión (Consorcio, Vida Cámara, Bice Vida…), por convenio directo o reembolso.", "ambas",
       [_campo("aseguradora", "Aseguradora"), _campo("codigo_prestador", "Código prestador"), _campo("usuario", "Usuario"), _campo("clave", "Clave", True)]),
    _c("caja_compensacion", "Cajas de compensación (CCAF)", "Salud / Bonos",
       "Bonificación y financiamiento del copago para afiliados (Los Andes, La Araucana, Los Héroes, 18 de Septiembre).", "ambas",
       [_campo("ccaf", "Caja de compensación"), _campo("codigo_convenio", "Código de convenio"), _campo("usuario", "Usuario"), _campo("clave", "Clave", True)]),
    _c("klap", "POS / Klap — Transbank/Klap", "Pagos",
       "Importa y concilia transacciones de la máquina POS.", "entrante",
       [_campo("comercio_id", "ID de comercio"), _campo("api_key", "API key", True)]),
    _c("pix", "QR / Pix — Transferencias", "Pagos",
       "Cobro por QR / transferencia con confirmación automática.", "entrante",
       [_campo("clave_pix", "Clave Pix / alias"), _campo("token", "Token", True)]),
    _c("whatsapp", "WhatsApp — Mensajería saliente", "Mensajería",
       "Recordatorios y confirmaciones por WhatsApp Business.", "saliente",
       [_campo("phone_id", "Phone ID"), _campo("token", "Token", True), _campo("plantilla", "Plantilla por defecto")]),
    _c("meta", "Meta — Facebook e Instagram", "Marketing",
       "Publicaciones/anuncios y captación de leads desde Meta.", "ambas",
       [_campo("page_id", "Page ID"), _campo("access_token", "Access token", True)]),
    _c("tiktok", "TikTok — Ads/Business", "Marketing",
       "Campañas y métricas de captación desde TikTok.", "saliente",
       [_campo("advertiser_id", "Advertiser ID"), _campo("access_token", "Access token", True)]),
    _c("google_business", "Google Empresas — Business Profile", "Presencia",
       "Ficha del negocio, reseñas y reservas desde Google.", "ambas",
       [_campo("location_id", "Location ID"), _campo("api_key", "API key", True)]),
    _c("agenda_terceros", "Agenda de terceros (médico/dental)", "Agenda",
       "Sincroniza citas con software de agenda externo.", "ambas",
       [_campo("proveedor", "Proveedor"), _campo("base_url", "URL base"), _campo("api_key", "API key", True)]),
    _c("telefono_ip", "Teléfono IP — VoIP/PBX", "Comunicaciones",
       "Registro de llamadas y click-to-call desde la central IP.", "ambas",
       [_campo("pbx_host", "Host de la central"), _campo("usuario", "Usuario"), _campo("clave", "Clave", True)]),
    _c("email", "Correo de la empresa — SMTP saliente", "Comunicaciones",
       "Envío de correos (recordatorios, presupuestos) desde el correo de la clínica.", "saliente",
       [_campo("smtp_host", "Servidor SMTP"), _campo("smtp_port", "Puerto"), _campo("usuario", "Usuario"), _campo("clave", "Clave", True), _campo("remitente", "Correo remitente")]),
]

_POR_TIPO = {c["tipo"]: c for c in CONECTORES}
TIPOS = set(_POR_TIPO)


def por_tipo(tipo: str) -> dict | None:
    return _POR_TIPO.get(tipo)
