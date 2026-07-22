"""Shared médico-side guards. The RBAC matrix (app/rbac) only grants the
coarse "a médico may view a prontuario" permission — it can't know *which*
patients. Spec Médico §1/§3: the médico sees clinical data only for
patients they actually treat ("solo de los pacientes que atiende"), and
every access is audited. Both rules live here so every clinical endpoint
enforces them identically.
"""

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.integrations import AuditLog
from app.models.patient import Patient
from app.models.scheduling import Appointment
from app.tenancy.context import TenantContext


async def get_treated_patient(db: AsyncSession, ctx: TenantContext, patient_id: uuid.UUID) -> Patient:
    """Return the patient IFF this médico has a real care relationship with
    them — at least one non-cancelled appointment where they are the
    professional. Otherwise 403/404. This is the enforcement point for
    "pacientes que no atiende: No" in the Spec Médico RBAC matrix."""
    patient = await db.get(Patient, patient_id)
    if patient is None or patient.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Paciente no encontrado")

    if not ctx.has_access_to_clinic(patient.clinic_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Sin acceso a esta clínica")

    treats = (
        await db.execute(
            select(Appointment.id).where(
                Appointment.professional_id == ctx.user_id,
                Appointment.patient_id == patient_id,
                Appointment.deleted_at.is_(None),
                Appointment.estado != "cancelada",
            )
        )
    ).first()
    if treats is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No atiendes a este paciente")

    return patient


async def get_own_appointment(db: AsyncSession, ctx: TenantContext, appointment_id: uuid.UUID) -> Appointment:
    """An appointment assigned to this médico, or 403/404."""
    appt = await db.get(Appointment, appointment_id)
    if appt is None or appt.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cita no encontrada")
    if appt.professional_id != ctx.user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Esta cita no está asignada a ti")
    return appt


def audit(db: AsyncSession, ctx: TenantContext, *, clinic_id, accion: str, recurso: str, antes=None, despues=None) -> None:
    """Append an immutable audit entry. Caller commits. Used for every access
    to clinical data and every clinical mutation (Spec Médico §1/§8: "Todo
    acceso queda auditado")."""
    db.add(
        AuditLog(
            clinic_id=clinic_id,
            actor_id=ctx.user_id,
            accion=accion,
            recurso=recurso,
            antes=antes,
            despues=despues,
            fecha=datetime.now(timezone.utc),
        )
    )
