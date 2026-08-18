"""Smoke test de bloqueos negativos de agenda / horarios especiales (51 · 52.9).

Contra la BD seedeada con `app.seed`, en el portal Empresa:

  · CRUD de bloqueos con auditoría (creado_por) y validación.
  · La generación de bloques desde el horario semanal SALTA los días bloqueados;
    al quitar el bloqueo, sí genera.
  · La reserva del paciente dentro de un bloqueo se rechaza (409); al quitarlo,
    se puede reservar.

Run: `python -m tests.test_bloqueos_agenda_smoke`.
"""

import asyncio
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.main import app
from app.models.catalog import CatalogItem
from app.models.identity import User
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
        service = (await db.execute(select(CatalogItem).where(CatalogItem.clinic_id == clinic.id, CatalogItem.tipo == "servicio"))).scalars().first()
        branch_id, med_a_id, service_id = branch.id, med_a.id, service.id

    base = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=260)
    d1_09 = (base + timedelta(hours=9)).isoformat()
    d1_13 = (base + timedelta(hours=13)).isoformat()
    d1_10 = (base + timedelta(hours=10)).isoformat()
    d1_1030 = (base + timedelta(hours=10, minutes=30)).isoformat()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        emp = await login(client, "empresa.a@todoscare.dev")

        # ───────── CRUD + auditoría ─────────
        r = await client.post("/empresa/bloqueos", headers=emp, json={"professional_id": str(med_a_id), "inicio": d1_09, "fin": d1_13, "motivo": "Vacaciones"})
        check("Bloqueo: alta -> 201", r.status_code == 201)
        b1 = r.json() if r.status_code == 201 else {}
        check("Bloqueo: trae motivo, profesional y creado_por (auditoría)", b1.get("motivo") == "Vacaciones" and b1.get("professional_nombre") and b1.get("creado_por"))
        b1_id = b1.get("id")

        bad = await client.post("/empresa/bloqueos", headers=emp, json={"professional_id": str(med_a_id), "inicio": d1_13, "fin": d1_09})
        check("Bloqueo: fin <= inicio -> 400", bad.status_code == 400)

        lst = (await client.get(f"/empresa/bloqueos?professional_id={med_a_id}", headers=emp)).json()
        check("Bloqueo: aparece en el listado", any(x["id"] == b1_id for x in lst))

        # ───────── generación respeta el bloqueo ─────────
        base2 = base + timedelta(days=10)
        d2 = base2.date()
        await client.post("/empresa/horarios", headers=emp, json={
            "professional_id": str(med_a_id), "branch_id": str(branch_id), "dia_semana": d2.weekday(),
            "hora_inicio": "09:00", "hora_fin": "13:00",
        })
        b2 = await client.post("/empresa/bloqueos", headers=emp, json={
            "professional_id": str(med_a_id),
            "inicio": base2.isoformat(), "fin": (base2 + timedelta(days=2)).isoformat(), "motivo": "Feriado",
        })
        b2_id = b2.json()["id"]
        g = await client.post("/empresa/horarios/generar", headers=emp, json={"professional_id": str(med_a_id), "desde": d2.isoformat(), "hasta": d2.isoformat()})
        gd = g.json()
        check("Generar con bloqueo: 0 generados, 1 omitido (día cerrado)", gd.get("generados") == 0 and gd.get("omitidos") == 1)

        await client.delete(f"/empresa/bloqueos/{b2_id}", headers=emp)
        g2 = await client.post("/empresa/horarios/generar", headers=emp, json={"professional_id": str(med_a_id), "desde": d2.isoformat(), "hasta": d2.isoformat()})
        check("Generar sin bloqueo: 1 generado", g2.json().get("generados") == 1)

        # ───────── reserva rechazada dentro del bloqueo ─────────
        await client.post("/empresa/agendas", headers=emp, json={"professional_id": str(med_a_id), "branch_id": str(branch_id), "inicio": d1_09, "fin": d1_13})
        pac = await login(client, "paciente.a@todoscare.dev")
        rr = await client.post("/agenda/reservar", headers=pac, json={"service_id": str(service_id), "professional_id": str(med_a_id), "inicio": d1_10, "fin": d1_1030})
        check("Reserva dentro del bloqueo -> 409", rr.status_code == 409)

        await client.delete(f"/empresa/bloqueos/{b1_id}", headers=emp)
        rr2 = await client.post("/agenda/reservar", headers=pac, json={"service_id": str(service_id), "professional_id": str(med_a_id), "inicio": d1_10, "fin": d1_1030})
        check("Tras quitar el bloqueo, la reserva -> 201", rr2.status_code == 201)

        lst2 = (await client.get(f"/empresa/bloqueos?professional_id={med_a_id}", headers=emp)).json()
        check("Bloqueo: ya no aparece tras la baja", not any(x["id"] == b1_id for x in lst2))

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
