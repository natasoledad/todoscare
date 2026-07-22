from datetime import datetime, timedelta


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
