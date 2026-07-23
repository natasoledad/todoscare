"""Conector de mapas (geolocalización de sucursales).

Enganche real: geocoding + Distance Matrix (Google/Mapbox). Aquí se calcula
la cercanía con la fórmula de Haversine sobre el `geo` de cada sucursal, sin
llamadas externas — suficiente para ordenar las sedes por distancia al
paciente.
"""

import math
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.base import log_event
from app.models.tenant import Branch


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    return round(2 * r * math.asin(math.sqrt(a)), 2)


async def sucursales_cercanas(db: AsyncSession, clinic_ids, lat: float, lng: float) -> list[dict]:
    q = select(Branch).where(Branch.deleted_at.is_(None), Branch.activo.is_(True))
    if clinic_ids is not None:
        q = q.where(Branch.clinic_id.in_(clinic_ids))
    branches = (await db.execute(q)).scalars().all()
    out = []
    for b in branches:
        geo = b.geo or {}
        dist = None
        if "lat" in geo and "lng" in geo:
            dist = _haversine_km(lat, lng, float(geo["lat"]), float(geo["lng"]))
        out.append({"branch_id": b.id, "clinic_id": b.clinic_id, "nombre": b.nombre, "direccion": b.direccion, "geo": geo or None, "distancia_km": dist})
    # las que tienen distancia primero, ordenadas por cercanía
    out.sort(key=lambda x: (x["distancia_km"] is None, x["distancia_km"] if x["distancia_km"] is not None else 0))
    return out
