"""Backfill de los 12 perfiles de acceso base (48) para clínicas ya existentes.

Los perfiles base se siembran automáticamente solo al crear una clínica nueva
(ver app/seed.py). Este script los carga en las clínicas que ya estaban en
producción antes de la entrega de perfiles.

Es IDEMPOTENTE: reutiliza `seed_permission_profiles`, que salta cualquier perfil
que ya exista (por nombre) en la clínica. Correrlo varias veces no duplica nada
ni toca ningún otro dato.

Uso (dentro del contenedor de la API en el servidor):
    docker compose -f docker-compose.prod.yml exec api python -m app.backfill_perfiles

    # opcional: limitar a una clínica por razón social
    docker compose -f docker-compose.prod.yml exec api python -m app.backfill_perfiles "Clínica Visión"
"""

import asyncio
import sys

from sqlalchemy import func, select

from app.core.database import AsyncSessionLocal
from app.models.identity import PermissionProfile
from app.models.tenant import Clinic
from app.seed import PERFILES_BASE, seed_permission_profiles


async def main(filtro: str | None = None) -> None:
    async with AsyncSessionLocal() as db:
        q = select(Clinic).where(Clinic.deleted_at.is_(None))
        if filtro:
            q = q.where(Clinic.razon_social == filtro)
        clinics = (await db.execute(q.order_by(Clinic.razon_social))).scalars().all()

        if not clinics:
            print("No se encontró ninguna clínica" + (f' con razón social "{filtro}"' if filtro else "") + ".")
            return

        print(f"Backfill de perfiles de acceso · {len(PERFILES_BASE)} perfiles base por clínica\n")
        for c in clinics:
            antes = (
                await db.execute(
                    select(func.count(PermissionProfile.id)).where(
                        PermissionProfile.clinic_id == c.id, PermissionProfile.deleted_at.is_(None)
                    )
                )
            ).scalar_one()
            await seed_permission_profiles(db, c.id)
            await db.commit()
            despues = (
                await db.execute(
                    select(func.count(PermissionProfile.id)).where(
                        PermissionProfile.clinic_id == c.id, PermissionProfile.deleted_at.is_(None)
                    )
                )
            ).scalar_one()
            creados = despues - antes
            estado = f"+{creados} creados" if creados else "sin cambios (ya estaban)"
            print(f"  · {c.razon_social:<30} {despues} perfiles ({estado})")

        print("\nListo. Los perfiles ya aparecen en Admin → Perfiles de acceso.")


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(main(arg))
