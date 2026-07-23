"""Conector de laboratorio (entrada: resultados por webhook).

Enganche real: se envía la orden al LIS del laboratorio y este devuelve el
resultado por webhook/HL7. Aquí `resultado_webhook` representa esa entrada:
adjunta el resultado a la orden y la marca disponible, de modo que el
paciente lo vea en Mi Salud › Exámenes.
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.base import ensure_enabled, log_event
from app.models.clinical import ExamOrder, ExamResult


async def resultado_webhook(db: AsyncSession, order_id: uuid.UUID, resultado: dict) -> dict:
    order = (await db.execute(select(ExamOrder).where(ExamOrder.id == order_id, ExamOrder.deleted_at.is_(None)))).scalar_one_or_none()
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Orden de examen no encontrada")
    await ensure_enabled(db, order.clinic_id, "lab")

    order.estado = "resultado_disponible"
    res = ExamResult(clinic_id=order.clinic_id, order_id=order.id, resultado=resultado, estado="disponible")
    db.add(res)
    log_event(db, clinic_id=order.clinic_id, tipo="lab", direccion="inbound", ref=f"order:{order.id}", payload=resultado, resultado={"estado": "disponible"})
    await db.commit()
    return {"order_id": str(order.id), "estado": "disponible"}
