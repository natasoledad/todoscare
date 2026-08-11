"""Smoke test de recintos (salas/boxes): la ocupación de un recinto la garantiza
Postgres con un EXCLUDE USING gist, igual que el anti doble-reserva por
profesional. Verifica dos niveles:

  · Base de datos: dos bloques de agenda (o dos citas) de profesionales
    DISTINTOS en el MISMO recinto y con horarios solapados son rechazados por la
    constraint; en distinto recinto o sin solape, se aceptan.
  · API (portal Empresa): alta de recintos (número único por tipo) y creación de
    bloques que respetan el recinto (409 si el recinto ya está ocupado).

Corre contra la BD real seedeada con `app.seed`. Run:
`python -m tests.test_recintos_smoke`.
"""

import asyncio
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import Range
from sqlalchemy.exc import IntegrityError

from app.core.database import AsyncSessionLocal
from app.main import app
from app.models.facility import Room
from app.models.identity import User
from app.models.patient import Patient
from app.models.scheduling import Appointment, AvailabilityBlock
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

    # ── Contexto: clínica A del seed demo, sus dos médicos y una sucursal ──
    async with AsyncSessionLocal() as db:
        clinic = (await db.execute(select(Clinic).where(Clinic.razon_social == "Clínica Demo A"))).scalar_one()
        branch = (await db.execute(select(Branch).where(Branch.clinic_id == clinic.id))).scalars().first()
        med_a = (await db.execute(select(User).where(User.email == "medico.a@todoscare.dev"))).scalar_one()
        med_b = (await db.execute(select(User).where(User.email == "medico.b@todoscare.dev"))).scalar_one()
        patient = (await db.execute(select(Patient).where(Patient.clinic_id == clinic.id))).scalars().first()
        # Recinto de prueba (número alto para no chocar con otros)
        room = Room(clinic_id=clinic.id, branch_id=branch.id, nombre="Sala Test", numero=97, tipo="medica")
        room2 = Room(clinic_id=clinic.id, branch_id=branch.id, nombre="Sala Test 2", numero=98, tipo="medica")
        db.add_all([room, room2])
        await db.commit()
        await db.refresh(room)
        await db.refresh(room2)
        clinic_id, branch_id, room_id, room2_id, med_a_id, med_b_id, patient_id = (
            clinic.id, branch.id, room.id, room2.id, med_a.id, med_b.id, patient.id,
        )

    base = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=400)

    async def try_block(prof_id, rid, start, end) -> bool:
        async with AsyncSessionLocal() as s:
            s.add(AvailabilityBlock(clinic_id=clinic_id, branch_id=branch_id, professional_id=prof_id, room_id=rid, rango=Range(start, end)))
            try:
                await s.commit()
                return True
            except IntegrityError:
                await s.rollback()
                return False

    async def try_appt(prof_id, rid, start, end) -> bool:
        async with AsyncSessionLocal() as s:
            s.add(Appointment(clinic_id=clinic_id, branch_id=branch_id, professional_id=prof_id, patient_id=patient_id, room_id=rid, slot=Range(start, end), estado="confirmada"))
            try:
                await s.commit()
                return True
            except IntegrityError:
                await s.rollback()
                return False

    # ───────── Nivel BD: bloques de agenda ─────────
    ok1 = await try_block(med_a_id, room_id, base + timedelta(hours=9), base + timedelta(hours=15))
    check("BD: primer bloque en la sala se acepta", ok1)

    ok2 = await try_block(med_b_id, room_id, base + timedelta(hours=10), base + timedelta(hours=12))
    check("BD: OTRO médico en la MISMA sala y horario solapado -> rechazado por Postgres", ok2 is False)

    ok3 = await try_block(med_b_id, room2_id, base + timedelta(hours=10), base + timedelta(hours=12))
    check("BD: el mismo médico en OTRA sala (room2) al mismo horario -> aceptado", ok3)

    ok4 = await try_block(med_b_id, room_id, base + timedelta(days=1, hours=9), base + timedelta(days=1, hours=15))
    check("BD: otro médico en la misma sala pero OTRO día (sin solape) -> aceptado", ok4)

    # ───────── Nivel BD: citas ─────────
    a1 = await try_appt(med_a_id, room_id, base + timedelta(hours=10), base + timedelta(hours=10, minutes=30))
    check("BD: primera cita en la sala se acepta", a1)

    a2 = await try_appt(med_b_id, room_id, base + timedelta(hours=10, minutes=15), base + timedelta(hours=10, minutes=45))
    check("BD: cita de otro médico en la MISMA sala solapada -> rechazada por Postgres", a2 is False)

    a3 = await try_appt(med_b_id, room_id, base + timedelta(hours=11), base + timedelta(hours=11, minutes=30))
    check("BD: cita en la misma sala sin solape (11:00) -> aceptada", a3)

    # ───────── Nivel API (portal Empresa) ─────────
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        emp = await login(client, "empresa.a@todoscare.dev")

        r = await client.post("/empresa/recintos", headers=emp, json={"nombre": "Box API", "numero": 91, "tipo": "dental"})
        check("API: empresa crea un recinto -> 201", r.status_code == 201)
        r_dup = await client.post("/empresa/recintos", headers=emp, json={"nombre": "Box API dup", "numero": 91, "tipo": "dental"})
        check("API: número de recinto duplicado (mismo tipo) -> 409", r_dup.status_code == 409)

        rooms = (await client.get("/empresa/recintos", headers=emp)).json()
        check("API: la lista de recintos incluye el creado", any(x["numero"] == 91 and x["tipo"] == "dental" for x in rooms))

        # Un recinto médico para probar el bloqueo de agenda por sala.
        rc = await client.post("/empresa/recintos", headers=emp, json={"nombre": "Sala API", "numero": 92, "tipo": "medica"})
        sala_api = rc.json()["id"]
        ini = (base + timedelta(days=2, hours=9)).isoformat()
        fin = (base + timedelta(days=2, hours=13)).isoformat()
        b1 = await client.post("/empresa/agendas", headers=emp, json={"professional_id": str(med_a_id), "branch_id": str(branch_id), "room_id": sala_api, "inicio": ini, "fin": fin})
        check("API: bloque de agenda con recinto -> 201 y trae room_id", b1.status_code == 201 and b1.json()["room_id"] == sala_api)

        ini2 = (base + timedelta(days=2, hours=11)).isoformat()
        fin2 = (base + timedelta(days=2, hours=12)).isoformat()
        b2 = await client.post("/empresa/agendas", headers=emp, json={"professional_id": str(med_b_id), "branch_id": str(branch_id), "room_id": sala_api, "inicio": ini2, "fin": fin2})
        check("API: OTRO profesional en la MISMA sala y horario solapado -> 409", b2.status_code == 409)

        # Otro día, misma sala: permitido.
        ini3 = (base + timedelta(days=3, hours=9)).isoformat()
        fin3 = (base + timedelta(days=3, hours=13)).isoformat()
        b3 = await client.post("/empresa/agendas", headers=emp, json={"professional_id": str(med_b_id), "branch_id": str(branch_id), "room_id": sala_api, "inicio": ini3, "fin": fin3})
        check("API: la misma sala otro día (sin solape) -> 201", b3.status_code == 201)

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
