"""Conector de farmacia (entrada: estado de dispensación por webhook).

Enganche real: se envía la prescripción a la farmacia (interna o externa) y
esta reporta el avance (recibida → preparando → en camino → entregada). Aquí
`estado_webhook` deja la traza de ese avance; el estado surtido de una receta
es información logística, no clínica, por eso vive en el evento y no muta la
prescripción firmada.
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.base import ensure_enabled, log_event
from app.models.clinical import Prescription

ESTADOS = ("recibida", "preparando", "en_camino", "entregada")


async def estado_webhook(db: AsyncSession, prescription_id: uuid.UUID, estado: str) -> dict:
    if estado not in ESTADOS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"estado inválido, use uno de {ESTADOS}")
    presc = (await db.execute(select(Prescription).where(Prescription.id == prescription_id, Prescription.deleted_at.is_(None)))).scalar_one_or_none()
    if presc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prescripción no encontrada")
    await ensure_enabled(db, presc.clinic_id, "farmacia")
    log_event(db, clinic_id=presc.clinic_id, tipo="farmacia", direccion="inbound", ref=f"prescription:{presc.id}", payload={"estado": estado}, resultado={"estado": estado})
    await db.commit()
    return {"prescription_id": str(presc.id), "estado": estado}
