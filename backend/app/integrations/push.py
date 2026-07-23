"""Conector de web push (notificaciones).

Enganche real: Web Push API con claves VAPID; el navegador entrega una
suscripción (endpoint + keys) que se guarda y a la que luego se le envían
mensajes cifrados. Aquí se guarda la suscripción y cada envío se asienta como
evento de salida (outbox) que el usuario puede consultar — sin entrega real
por red. El conector 'push' de la clínica debe estar habilitado para enviar.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.base import ensure_enabled, log_event
from app.models.integrations import IntegrationEvent, PushSubscription


async def suscribir(db: AsyncSession, user_id: uuid.UUID, endpoint: str) -> dict:
    existe = (await db.execute(select(PushSubscription).where(PushSubscription.user_id == user_id, PushSubscription.endpoint == endpoint, PushSubscription.deleted_at.is_(None)))).scalar_one_or_none()
    if existe is not None:
        existe.activo = True
        await db.commit()
        return {"subscription_id": str(existe.id), "estado": "activa"}
    sub = PushSubscription(user_id=user_id, endpoint=endpoint)
    db.add(sub)
    await db.commit()
    await db.refresh(sub)
    return {"subscription_id": str(sub.id), "estado": "activa"}


async def enviar(db: AsyncSession, *, clinic_id: uuid.UUID, user_id: uuid.UUID, titulo: str, cuerpo: str) -> dict:
    """Envía (simuladamente) una notificación a las suscripciones activas del
    usuario. Requiere el conector 'push' habilitado en la clínica."""
    await ensure_enabled(db, clinic_id, "push")
    subs = (await db.execute(select(PushSubscription).where(PushSubscription.user_id == user_id, PushSubscription.activo.is_(True), PushSubscription.deleted_at.is_(None)))).scalars().all()
    log_event(db, clinic_id=clinic_id, tipo="push", direccion="outbound", estado="enviado", ref=f"user:{user_id}", payload={"titulo": titulo, "cuerpo": cuerpo}, resultado={"entregas": len(subs)})
    await db.commit()
    return {"entregas": len(subs), "titulo": titulo}


async def mis_notificaciones(db: AsyncSession, user_id: uuid.UUID) -> list[dict]:
    rows = (
        await db.execute(
            select(IntegrationEvent)
            .where(IntegrationEvent.tipo == "push", IntegrationEvent.direccion == "outbound", IntegrationEvent.ref == f"user:{user_id}", IntegrationEvent.deleted_at.is_(None))
            .order_by(IntegrationEvent.created_at.desc())
        )
    ).scalars().all()
    return [{"titulo": (e.payload or {}).get("titulo"), "cuerpo": (e.payload or {}).get("cuerpo"), "fecha": e.created_at} for e in rows]
