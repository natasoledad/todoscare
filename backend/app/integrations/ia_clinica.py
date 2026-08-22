"""Conector 'ia_clinica' — la IA que lee los documentos del paciente (punto 72).

Conmutable (72.4): si `settings.anthropic_api_key` está configurada, el conector
envía el CONTENIDO del documento (texto, imagen o PDF) a un modelo Claude y
extrae hallazgos + una fecha de próximo control estructurados. Si no hay key o
la llamada falla, cae a un heurístico determinista sobre el nombre del
documento, de modo que el flujo end-to-end (subir → sugerencia → aplicar a la
ficha → próximo control → recordatorio) siempre funciona y es verificable sin
depender de un modelo externo.
"""

import base64
import json
import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.integrations import IntegrationConfig

TIPO = "ia_clinica"


async def config_activa(db: AsyncSession, clinic_id: uuid.UUID) -> bool:
    """¿La clínica tiene habilitado el conector de IA clínica? (no lanza: la
    subida de un examen no debe fallar porque la IA esté apagada)."""
    cfg = (
        await db.execute(
            select(IntegrationConfig).where(
                IntegrationConfig.clinic_id == clinic_id,
                IntegrationConfig.tipo == TIPO,
                IntegrationConfig.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    return cfg is not None and cfg.activo


# Reglas: palabra clave en el nombre del documento -> (resumen, parche de ficha,
# meses hasta el próximo control sugerido).
_REGLAS: list[tuple[tuple[str, ...], str, dict, int]] = [
    (("presion", "presión", "arterial", "cardio", "ecg", "electrocardio"),
     "Documento cardiovascular: se recomienda seguimiento de presión arterial.",
     {"seguimiento_cardiovascular": True}, 3),
    (("glicemia", "glucosa", "glucemia", "hba1c", "diabet"),
     "Perfil metabólico: control de glicemia recomendado.",
     {"seguimiento_glicemia": True}, 6),
    (("hemograma", "sangre", "perfil", "colesterol", "lipid"),
     "Examen de laboratorio general incorporado a la ficha.",
     {"ultimo_laboratorio": "cargado"}, 12),
    (("radiograf", "rx", "panoram", "imagen", "scanner", "tac", "resonancia"),
     "Estudio de imágenes incorporado a la ficha.",
     {"ultima_imagen": "cargada"}, 12),
]

_DEFAULT = ("Documento clínico incorporado a tu ficha.", {"documentos_cargados": True}, 12)


def _heuristico(nombre: str) -> dict:
    """Análisis determinista por nombre/tipo del documento (sin modelo externo)."""
    t = (nombre or "").lower()
    for claves, resumen, hallazgos, meses in _REGLAS:
        if any(k in t for k in claves):
            return {"resumen": resumen, "hallazgos": dict(hallazgos), "proximo_control_meses": meses}
    resumen, hallazgos, meses = _DEFAULT
    return {"resumen": resumen, "hallazgos": dict(hallazgos), "proximo_control_meses": meses}


_PROMPT = (
    "Eres un asistente clínico. Te entrego un documento de examen de un paciente. "
    "Devuelve SOLO un objeto JSON (sin texto adicional, sin markdown) con exactamente estas claves: "
    '"resumen" (una frase breve en español sobre el hallazgo principal), '
    '"hallazgos" (objeto con pares clave→valor cortos: parámetros relevantes y si requieren seguimiento), '
    'y "proximo_control_meses" (entero entre 1 y 24 con la anticipación sugerida para el próximo control). '
    "No inventes diagnósticos; si el documento no es clínico, resume lo que veas."
)


def _bloque_documento(contenido: bytes, content_type: str | None) -> dict:
    """Arma el bloque de contenido para la API según el tipo (imagen/PDF/texto)."""
    ct = (content_type or "").lower()
    if ct.startswith("image/"):
        return {"type": "image", "source": {"type": "base64", "media_type": ct, "data": base64.b64encode(contenido).decode()}}
    if ct == "application/pdf" or contenido[:5] == b"%PDF-":
        return {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": base64.b64encode(contenido).decode()}}
    # texto: si no decodifica como UTF-8, no es analizable como texto plano
    texto = contenido.decode("utf-8", errors="strict")[:20000]
    return {"type": "text", "text": f"Contenido del examen:\n\n{texto}"}


def _parse_respuesta(texto: str) -> dict:
    """Extrae y valida el JSON de la respuesta del modelo."""
    ini, fin = texto.find("{"), texto.rfind("}")
    if ini < 0 or fin <= ini:
        raise ValueError("respuesta sin JSON")
    data = json.loads(texto[ini:fin + 1])
    resumen = str(data["resumen"]).strip()
    hallazgos = data.get("hallazgos") or {}
    if not isinstance(hallazgos, dict):
        raise ValueError("hallazgos inválido")
    meses = int(data["proximo_control_meses"])
    meses = max(1, min(24, meses))
    if not resumen:
        raise ValueError("resumen vacío")
    return {"resumen": resumen[:500], "hallazgos": {str(k): v for k, v in list(hallazgos.items())[:20]}, "proximo_control_meses": meses}


async def _analizar_con_ia(nombre: str, contenido: bytes, content_type: str | None) -> dict:
    """Llama al modelo Claude con el contenido del documento (72.4)."""
    bloque = _bloque_documento(contenido, content_type)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{settings.ia_base_url}/v1/messages",
            headers={
                "x-api-key": settings.anthropic_api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": settings.ia_model,
                "max_tokens": 500,
                "messages": [{"role": "user", "content": [bloque, {"type": "text", "text": _PROMPT}]}],
            },
        )
        r.raise_for_status()
        partes = r.json().get("content", [])
    texto = "".join(p.get("text", "") for p in partes if p.get("type") == "text")
    return _parse_respuesta(texto)


async def analizar_examen(nombre: str, contenido: bytes | None = None, content_type: str | None = None) -> dict:
    """Analiza un documento y devuelve {resumen, hallazgos, proximo_control_meses}.

    Usa el modelo Claude si hay API key y contenido; ante cualquier problema (sin
    key, error de red, respuesta inválida, binario no soportado) cae al
    heurístico. La subida de un examen nunca debe fallar por la IA."""
    if settings.anthropic_api_key and contenido:
        try:
            return await _analizar_con_ia(nombre, contenido, content_type)
        except Exception:  # noqa: BLE001 — degradación elegante al heurístico
            pass
    return _heuristico(nombre)
