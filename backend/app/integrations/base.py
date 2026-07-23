"""Frontera común de los conectores: gate por IntegrationConfig + traza."""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.integrations import IntegrationConfig, IntegrationEvent


async def ensure_enabled(db: AsyncSession, clinic_id: uuid.UUID, tipo: str) -> None:
    """Un conector solo procesa eventos si la clínica lo tiene habilitado
    (Spec Admin §8: integraciones configurables por clínica). Si no existe o
    está apagado, se rechaza con 409 — nunca se ejecuta el efecto de dominio."""
    cfg = (
        await db.execute(
            select(IntegrationConfig).where(
                IntegrationConfig.clinic_id == clinic_id,
                IntegrationConfig.tipo == tipo,
                IntegrationConfig.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if cfg is None or not cfg.activo:
        raise HTTPException(status.HTTP_409_CONFLICT, f"El conector '{tipo}' no está habilitado para esta clínica")


def log_event(
    db: AsyncSession,
    *,
    clinic_id: uuid.UUID,
    tipo: str,
    direccion: str,
    estado: str = "procesado",
    ref: str | None = None,
    payload: dict | None = None,
    resultado: dict | None = None,
) -> IntegrationEvent:
    """Asienta el evento del conector (caller hace commit)."""
    ev = IntegrationEvent(
        clinic_id=clinic_id,
        tipo=tipo,
        direccion=direccion,
        estado=estado,
        ref=ref,
        payload=payload,
        resultado=resultado,
    )
    db.add(ev)
    return ev
