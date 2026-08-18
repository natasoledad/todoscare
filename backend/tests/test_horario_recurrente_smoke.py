"""Smoke test del horario semanal recurrente (punto 52).

Contra la BD seedeada con `app.seed`, en el portal Empresa:

  · Alta de plantilla de horario con descanso, modalidad y capacidad (52.3/52.4/52.7).
  · Validaciones (término > inicio, descanso dentro del turno).
  · Materializar bloques desde la plantilla para un rango de fechas: el descanso
    parte el turno en DOS bloques.
  · Idempotencia: regenerar el mismo rango no duplica (omite los solapados).
  · Baja de la plantilla no borra los bloques ya generados.

Run: `python -m tests.test_horario_recurrente_smoke`.
"""

import asyncio
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.main import app
from app.models.identity import User
from app.models.scheduling import AvailabilityBlock
from app.models.tenant import Branch, Clinic

PASSWORD = "Demo1234!"


async def login(client: httpx.AsyncClient, email: str) -> dict:
    r = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def main() -> None:
    results: list[tuple[str, bool]] = []

    def check(name: str, ok: bool) -> None:
        results.append((name, ok))

    async with AsyncSessionLocal() as db:
        clinic = (await db.execute(select(Clinic).where(Clinic.razon_social == "Clínica Demo A"))).scalar_one()
        branch = (await db.execute(select(Branch).where(Branch.clinic_id == clinic.id))).scalars().first()
        med_a = (await db.execute(select(User).where(User.email == "medico.a@todoscare.dev"))).scalar_one()
        clinic_id, branch_id, med_a_id = clinic.id, branch.id, med_a.id

    # Día futuro para no chocar con bloques del seed.
    d = (datetime.now(timezone.utc) + timedelta(days=250)).date()
    dia_semana = d.weekday()  # 0=lunes … 6=domingo (igual que el modelo)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        emp = await login(client, "empresa.a@todoscare.dev")

        # ── alta de plantilla con descanso ──
        payload = {
            "professional_id": str(med_a_id), "branch_id": str(branch_id), "dia_semana": dia_semana,
            "hora_inicio": "09:00", "hora_fin": "13:00", "descanso_inicio": "11:00", "descanso_fin": "11:30",
            "modalidad": "ambas", "capacidad": 2,
        }
        r = await client.post("/empresa/horarios", headers=emp, json=payload)
        check("Horario: alta con descanso -> 201", r.status_code == 201)
        h = r.json() if r.status_code == 201 else {}
        check("Horario: guarda modalidad y capacidad", h.get("modalidad") == "ambas" and h.get("capacidad") == 2)
        horario_id = h.get("id")

        # ── validaciones ──
        bad1 = await client.post("/empresa/horarios", headers=emp, json={**payload, "hora_inicio": "14:00", "hora_fin": "13:00"})
        check("Horario: término <= inicio -> 400", bad1.status_code == 400)
        bad2 = await client.post("/empresa/horarios", headers=emp, json={**payload, "descanso_inicio": "08:00", "descanso_fin": "08:30"})
        check("Horario: descanso fuera del turno -> 400", bad2.status_code == 400)

        # ── listado + edición ──
        lst = (await client.get(f"/empresa/horarios?professional_id={med_a_id}", headers=emp)).json()
        check("Horario: aparece en el listado", any(x["id"] == horario_id for x in lst))
        re = await client.patch(f"/empresa/horarios/{horario_id}", headers=emp, json={"hora_fin": "14:00"})
        check("Horario: edición -> 200 y hora_fin nueva", re.status_code == 200 and re.json()["hora_fin"].startswith("14:00"))

        # ── generar bloques (un solo día) ──
        g = await client.post("/empresa/horarios/generar", headers=emp, json={"professional_id": str(med_a_id), "desde": d.isoformat(), "hasta": d.isoformat()})
        check("Generar: -> 200", g.status_code == 200)
        gd = g.json() if g.status_code == 200 else {}
        check("Generar: 2 bloques (descanso parte el turno), 0 omitidos", gd.get("generados") == 2 and gd.get("omitidos") == 0)

        # ── idempotencia ──
        g2 = await client.post("/empresa/horarios/generar", headers=emp, json={"professional_id": str(med_a_id), "desde": d.isoformat(), "hasta": d.isoformat()})
        gd2 = g2.json() if g2.status_code == 200 else {}
        check("Generar de nuevo: 0 generados, 2 omitidos (idempotente)", gd2.get("generados") == 0 and gd2.get("omitidos") == 2)

        # ── baja de plantilla ──
        rdel = await client.delete(f"/empresa/horarios/{horario_id}", headers=emp)
        check("Horario: baja -> 204", rdel.status_code == 204)
        lst2 = (await client.get(f"/empresa/horarios?professional_id={med_a_id}", headers=emp)).json()
        check("Horario: ya no aparece tras la baja", not any(x["id"] == horario_id for x in lst2))

    # Verifica en BD: 2 bloques con origen 'plantilla' (siguen tras borrar la plantilla).
    async with AsyncSessionLocal() as db:
        blocks = (
            await db.execute(
                select(AvailabilityBlock).where(
                    AvailabilityBlock.clinic_id == clinic_id, AvailabilityBlock.professional_id == med_a_id, AvailabilityBlock.deleted_at.is_(None)
                )
            )
        ).scalars().all()
        plantilla = [b for b in blocks if (b.reglas or {}).get("origen") == "plantilla"]
        check("BD: 2 bloques materializados desde la plantilla", len(plantilla) == 2)
        check("BD: los bloques persisten tras borrar la plantilla", len(plantilla) == 2)

    print()
    failed = sum(1 for _, ok in results if not ok)
    for name, ok in results:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    print()
    if failed:
        print(f"{failed} check(s) FAILED")
        raise SystemExit(1)
    print(f"All {len(results)} checks passed.")


if __name__ == "__main__":
    asyncio.run(main())
