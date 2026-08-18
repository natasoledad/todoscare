import uuid
from datetime import datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import Range
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scheduling import ScheduleException


async def overlaps_exception(
    db: AsyncSession,
    clinic_id: uuid.UUID,
    professional_id: uuid.UUID,
    start: datetime,
    end: datetime,
    branch_id: uuid.UUID | None = None,
) -> bool:
    """¿El rango [start, end) cae dentro de un bloqueo negativo del profesional?
    (puntos 51 / 52.9). Un bloqueo sin sucursal aplica a todas; con sucursal,
    solo a la suya. La usan la reserva, la disponibilidad y la generación de
    bloques para no ofrecer/crear agenda dentro de un cierre."""
    q = select(ScheduleException.id).where(
        ScheduleException.clinic_id == clinic_id,
        ScheduleException.professional_id == professional_id,
        ScheduleException.deleted_at.is_(None),
        ScheduleException.rango.op("&&")(Range(start, end)),
    )
    if branch_id is not None:
        q = q.where(or_(ScheduleException.branch_id.is_(None), ScheduleException.branch_id == branch_id))
    return (await db.execute(q)).scalars().first() is not None


def generate_slots(
    block_start: datetime,
    block_end: datetime,
    duration_min: int,
    booked_ranges: list[tuple[datetime, datetime]],
) -> list[tuple[datetime, datetime]]:
    """Discrete candidate slots of `duration_min` inside [block_start, block_end),
    skipping any that overlap an already-booked range for that professional.

    This is a convenience filter for the UI (don't even show a taken slot);
    the actual anti-double-booking guarantee is the DB's EXCLUDE constraint
    on `appointments` — this function is not the safety net, just the menu.
    """
    step = timedelta(minutes=duration_min)
    slots = []
    cursor = block_start
    while cursor + step <= block_end:
        candidate_end = cursor + step
        overlaps = any(cursor < b_end and candidate_end > b_start for b_start, b_end in booked_ranges)
        if not overlaps:
            slots.append((cursor, candidate_end))
        cursor += step
    return slots
