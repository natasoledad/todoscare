"""Carga del catálogo CIE-10 (71.20) en producción.

El catálogo es dato de referencia global que el módulo de diagnósticos necesita.
Como producción no reseedea al arrancar (SEED_ON_START=false), este script carga
el catálogo una vez. Es IDEMPOTENTE: salta los códigos que ya existen.

Uso (dentro del contenedor de la API en el servidor):
    docker compose -f docker-compose.prod.yml exec api python -m app.load_cie10
"""

import asyncio

from sqlalchemy import func, select

from app.core.database import AsyncSessionLocal
from app.models.clinical import Cie10Code
from app.seed import CIE10_SEED, seed_cie10


async def main() -> None:
    async with AsyncSessionLocal() as db:
        nuevos = await seed_cie10(db)
        await db.commit()
        total = (await db.execute(select(func.count(Cie10Code.id)).where(Cie10Code.deleted_at.is_(None)))).scalar_one()
        print(f"Catálogo CIE-10: {nuevos} códigos nuevos insertados (de {len(CIE10_SEED)} base). Total en BD: {total}.")


if __name__ == "__main__":
    asyncio.run(main())
