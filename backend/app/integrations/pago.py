"""Conector de pasarela de pago (bidireccional: API + webhook — Spec CRM §6).

Enganche real: crear un PaymentIntent en la pasarela (Stripe/MercadoPago/…)
y recibir la confirmación por webhook firmado. Aquí `crear_intent` devuelve
un intent simulado y `confirmar` representa el webhook de la pasarela: al
confirmarse el pago se asienta el ingreso en el ledger inmutable y su split
al profesional — los mismos asientos que alimentan el CRM y las
liquidaciones del médico. El pago es idempotente por `ref`.
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.base import ensure_enabled, log_event
from app.models.finance import LedgerEntry
from app.models.scheduling import Appointment
from app.services.finance import liquidar_atencion


async def crear_intent(db: AsyncSession, appointment_id: uuid.UUID, ctx_clinic_scope) -> dict:
    """Crea el intent de pago para una cita (monto = precio del servicio)."""
    appt = (await db.execute(select(Appointment).where(Appointment.id == appointment_id, Appointment.deleted_at.is_(None)))).scalar_one_or_none()
    if appt is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cita no encontrada")
    if ctx_clinic_scope is not None and appt.clinic_id not in ctx_clinic_scope:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Sin acceso a esa cita")
    await ensure_enabled(db, appt.clinic_id, "pago")
    ref = f"pago:{appt.id}"
    log_event(db, clinic_id=appt.clinic_id, tipo="pago", direccion="outbound", estado="enviado", ref=ref, payload={"appointment_id": str(appt.id)}, resultado={"intent_id": ref, "estado": "requiere_confirmacion"})
    await db.commit()
    return {"intent_id": ref, "appointment_id": str(appt.id), "estado": "requiere_confirmacion"}


async def confirmar(db: AsyncSession, appointment_id: uuid.UUID) -> dict:
    """Webhook de la pasarela: pago confirmado -> ingreso + split en el ledger.
    Idempotente: si ya hay un ingreso para la cita, no se duplica."""
    appt = (await db.execute(select(Appointment).where(Appointment.id == appointment_id, Appointment.deleted_at.is_(None)))).scalar_one_or_none()
    if appt is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cita no encontrada")
    await ensure_enabled(db, appt.clinic_id, "pago")

    ref = f"appointment:{appt.id}"
    ya = (await db.execute(select(LedgerEntry).where(LedgerEntry.ref == ref, LedgerEntry.tipo == "ingreso", LedgerEntry.deleted_at.is_(None)))).scalars().first()
    if ya is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "El pago de esta cita ya fue asentado")

    service = None
    if appt.service_id is not None:
        from app.models.catalog import CatalogItem

        service = await db.get(CatalogItem, appt.service_id)
    split = await liquidar_atencion(db, clinic_id=appt.clinic_id, professional_id=appt.professional_id, service=service, appointment_id=appt.id)
    monto = float(service.precio) if service else 0.0
    log_event(db, clinic_id=appt.clinic_id, tipo="pago", direccion="inbound", ref=f"pago:{appt.id}", payload={"appointment_id": str(appt.id)}, resultado={"pagado": monto, "split": float(split.monto) if split else 0.0})
    await db.commit()
    return {"appointment_id": str(appt.id), "monto": monto, "split": float(split.monto) if split else 0.0, "estado": "pagado"}
