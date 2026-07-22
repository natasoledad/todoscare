"""Liquidación de una atención: al cerrar una cita se registra el ingreso en
el ledger inmutable y se reparte (split) al profesional tratante.

El % por defecto es un placeholder — Spec Administrador §11 y Spec Médico §9
dejan abierto el modelo de split ("reglas de split por defecto vs. por
convenio"). Se centraliza aquí para cambiarlo en un solo lugar cuando
producto lo defina.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import CatalogItem
from app.models.finance import LedgerEntry, PaymentSplit

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
    priced service). Caller commits."""
    if service is None:
        return None

    monto = float(service.precio)
    ledger = LedgerEntry(clinic_id=clinic_id, tipo="ingreso", monto=monto, ref=f"appointment:{appointment_id}")
    db.add(ledger)
    await db.flush()

    split_monto = round(monto * PROFESSIONAL_SPLIT_PCT, 2)
    split = PaymentSplit(
        clinic_id=clinic_id,
        ledger_entry_id=ledger.id,
        beneficiario_id=professional_id,
        monto=split_monto,
        regla={"pct": PROFESSIONAL_SPLIT_PCT, "base": monto},
    )
    db.add(split)
    return split
