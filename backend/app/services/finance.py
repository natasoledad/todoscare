"""Liquidación de una atención: al cerrar una cita se registra el ingreso en
el ledger inmutable y se reparte (split) al profesional tratante.

El % por defecto es un placeholder — Spec Administrador §11 y Spec Médico §9
dejan abierto el modelo de split ("reglas de split por defecto vs. por
convenio"). Se centraliza aquí para cambiarlo en un solo lugar cuando
producto lo defina.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import CatalogItem
from app.models.finance import LedgerEntry, PaymentSplit
from app.models.professional import ProfessionalProfile

PROFESSIONAL_SPLIT_PCT = 0.60


async def liquidar_atencion(
    db: AsyncSession,
    *,
    clinic_id: uuid.UUID,
    professional_id: uuid.UUID,
    service: CatalogItem | None,
    appointment_id: uuid.UUID,
) -> PaymentSplit | None:
    """INSERT-only: an ingreso ledger entry for the service price plus the
    professional's split. Returns the split (None if the appointment had no
    priced service, or the service does not commission).

    El ingreso SIEMPRE se asienta (se cobra al paciente). El split solo existe
    si la prestación comisiona (57.10) y usa el % del perfil del profesional si
    está definido, o el % por defecto de la clínica (58). Caller commits."""
    if service is None:
        return None

    monto = float(service.precio)
    ledger = LedgerEntry(clinic_id=clinic_id, tipo="ingreso", monto=monto, ref=f"appointment:{appointment_id}")
    db.add(ledger)
    await db.flush()

    # Prestaciones que no comisionan (laboratorio, insumos): sin split.
    # `is False` (no `not …`) para que un objeto sin refrescar (comisiona=None
    # por el server_default) se trate como que sí comisiona, el comportamiento previo.
    if service.comisiona is False:
        return None

    pct = (
        await db.execute(
            select(ProfessionalProfile.comision_pct).where(
                ProfessionalProfile.clinic_id == clinic_id,
                ProfessionalProfile.user_id == professional_id,
                ProfessionalProfile.deleted_at.is_(None),
            )
        )
    ).scalars().first()
    pct = float(pct) if pct is not None else PROFESSIONAL_SPLIT_PCT

    split_monto = round(monto * pct, 2)
    split = PaymentSplit(
        clinic_id=clinic_id,
        ledger_entry_id=ledger.id,
        beneficiario_id=professional_id,
        monto=split_monto,
        regla={"pct": pct, "base": monto},
    )
    db.add(split)
    return split
