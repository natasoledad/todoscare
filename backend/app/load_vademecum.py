"""Carga del vademécum (71.21) en producción.

Catálogo de medicamentos de referencia para prescribir. Como producción no
reseedea al arrancar, este script lo carga una vez. IDEMPOTENTE.

Uso (dentro del contenedor de la API en el servidor):
    docker compose -f docker-compose.prod.yml exec api python -m app.load_vademecum
"""

import asyncio

from sqlalchemy import func, select

from app.core.database import AsyncSessionLocal
from app.models.catalog import Medication
from app.seed import VADEMECUM_SEED, seed_vademecum


async def main() -> None:
    async with AsyncSessionLocal() as db:
        nuevos = await seed_vademecum(db)
        await db.commit()
        total = (await db.execute(select(func.count(Medication.id)).where(Medication.deleted_at.is_(None)))).scalar_one()
        print(f"Vademécum: {nuevos} medicamentos nuevos (de {len(VADEMECUM_SEED)} base). Total en BD: {total}.")


if __name__ == "__main__":
    asyncio.run(main())
