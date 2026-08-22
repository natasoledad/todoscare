"""Asistente conversacional con base de conocimiento (RAG, 72).

Recupera los fragmentos relevantes de la base de conocimiento de la clínica y
redacta una respuesta fundamentada en ellos. El generador es CONMUTABLE: usa un
modelo Claude si hay API key; si no, responde de forma extractiva (determinista,
sin red). Siempre con guardrails clínicos.
"""

import uuid

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services import conocimiento

DISCLAIMER = (
    "Esta respuesta es informativa, se basa en el material de la clínica y no reemplaza la "
    "evaluación de un profesional. Para tu caso puntual, contacta a la clínica."
)

_SIN_INFO = (
    "No encuentro esa información en el material de la clínica. Te recomiendo contactar directamente "
    "a la clínica para resolverlo. " + DISCLAIMER
)

_SYSTEM = (
    "Eres el asistente virtual de una clínica y hablas con un paciente. Responde SOLO con la información "
    "del CONTEXTO entregado. Si la respuesta no está en el contexto, dilo y sugiere contactar a la clínica; "
    "no inventes. No entregues diagnósticos, dosis ni indicaciones médicas personalizadas: para eso deriva "
    "a un profesional. Responde en español, breve, claro y amable."
)


async def _generar_con_ia(pregunta: str, contexto: str) -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{settings.ia_base_url}/v1/messages",
            headers={"x-api-key": settings.anthropic_api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={
                "model": settings.ia_model,
                "max_tokens": 400,
                "system": _SYSTEM,
                "messages": [{"role": "user", "content": f"CONTEXTO:\n{contexto}\n\nPREGUNTA DEL PACIENTE:\n{pregunta}"}],
            },
        )
        r.raise_for_status()
        partes = r.json().get("content", [])
    texto = "".join(p.get("text", "") for p in partes if p.get("type") == "text").strip()
    if not texto:
        raise ValueError("respuesta vacía")
    return texto


def _extractivo(fragmentos: list[str]) -> str:
    """Respuesta sin modelo: cita el material más relevante."""
    cuerpo = " ".join(fragmentos[:2]).strip()
    return f"Según el material de la clínica: {cuerpo}"


async def responder(db: AsyncSession, clinic_id: uuid.UUID, pregunta: str) -> dict:
    """Devuelve {respuesta, fuentes, uso_ia}. Nunca falla: ante error de IA cae
    al modo extractivo."""
    hits = await conocimiento.buscar(db, clinic_id, pregunta, k=4)
    if not hits:
        return {"respuesta": _SIN_INFO, "fuentes": [], "uso_ia": False}

    fragmentos = [ch.texto for _, ch, _ in hits]
    fuentes = list(dict.fromkeys(src.nombre for _, _, src in hits))  # únicas, en orden
    contexto = "\n\n".join(f"[{src.nombre}] {ch.texto}" for _, ch, src in hits)

    uso_ia = False
    if settings.anthropic_api_key:
        try:
            respuesta = await _generar_con_ia(pregunta, contexto)
            uso_ia = True
        except Exception:  # noqa: BLE001 — degradación al modo extractivo
            respuesta = _extractivo(fragmentos)
    else:
        respuesta = _extractivo(fragmentos)

    return {"respuesta": f"{respuesta}\n\n{DISCLAIMER}", "fuentes": fuentes, "uso_ia": uso_ia}
