"""Smoke test del estado del profesional (punto 55).

Contra la BD seedeada con `app.seed`, en el portal Empresa:

  · Inhabilitar/habilitar un profesional (55.1).
  · Agenda congelada: un profesional inhabilitado no acepta nuevos bloques (55.3).
  · Login bloqueado: un profesional puro inhabilitado no puede loguear (55.2);
    al rehabilitarlo, vuelve a entrar.
  · Remanejo: las citas futuras del profesional se reasignan a otro; las que
    chocan de horario en el destino quedan sin mover (55.5).

Run: `python -m tests.test_estado_profesional_smoke`.
"""

import asyncio
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import Range

from app.core.database import AsyncSessionLocal
from app.main import app
from app.models.identity import User
from app.models.patient import Patient
from app.models.scheduling import Appointment
from app.models.tenant import Branch, Clinic

PASSWORD = "Demo1234!"


async def login(client: httpx.AsyncClient, email: str) -> httpx.Response:
    return await client.post("/auth/login", json={"email": email, "password": PASSWORD})


async def main() -> None:
    results: list[tuple[str, bool]] = []

    def check(name: str, ok: bool) -> None:
        results.append((name, ok))

    async with AsyncSessionLocal() as db:
        clinic = (await db.execute(select(Clinic).where(Clinic.razon_social == "Clínica Demo A"))).scalar_one()
        branch = (await db.execute(select(Branch).where(Branch.clinic_id == clinic.id))).scalars().first()
        med_a = (await db.execute(select(User).where(User.email == "medico.a@todoscare.dev"))).scalar_one()
        med_b = (await db.execute(select(User).where(User.email == "medico.b@todoscare.dev"))).scalar_one()
        patient = (await db.execute(select(Patient).where(Patient.clinic_id == clinic.id))).scalars().first()
        clinic_id, branch_id, med_a_id, med_b_id, patient_id = clinic.id, branch.id, med_a.id, med_b.id, patient.id

    # Dos citas futuras de med_a + una de med_b que forzará conflicto al remanejar.
    base = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=300)
    s1 = (base + timedelta(hours=9), base + timedelta(hours=9, minutes=30))   # med_b libre -> se mueve
    s2 = (base + timedelta(hours=11), base + timedelta(hours=11, minutes=30))  # med_b ocupado -> conflicto

    async with AsyncSessionLocal() as db:
        a1 = Appointment(clinic_id=clinic_id, branch_id=branch_id, professional_id=med_a_id, patient_id=patient_id, slot=Range(*s1), estado="confirmada")
        a2 = Appointment(clinic_id=clinic_id, branch_id=branch_id, professional_id=med_a_id, patient_id=patient_id, slot=Range(*s2), estado="confirmada")
        b2 = Appointment(clinic_id=clinic_id, branch_id=branch_id, professional_id=med_b_id, patient_id=patient_id, slot=Range(*s2), estado="confirmada")
        db.add_all([a1, a2, b2])
        await db.commit()
        a1_id, a2_id = a1.id, a2.id

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await login(client, "empresa.a@todoscare.dev")
        emp = {"Authorization": f"Bearer {r.json()['access_token']}"}

        # ── login del médico funciona ANTES de inhabilitar ──
        check("Login médico activo -> 200", (await login(client, "medico.a@todoscare.dev")).status_code == 200)

        # ── inhabilitar (55.1) ──
        r = await client.patch(f"/empresa/profesionales/{med_a_id}/estado", headers=emp, json={"activo": False})
        check("Inhabilitar profesional -> 200 y activo=false", r.status_code == 200 and r.json().get("activo") is False)

        # ── agenda congelada (55.3): no acepta nuevos bloques ──
        ini = (base + timedelta(days=1, hours=9)).isoformat()
        fin = (base + timedelta(days=1, hours=13)).isoformat()
        rb = await client.post("/empresa/agendas", headers=emp, json={"professional_id": str(med_a_id), "branch_id": str(branch_id), "inicio": ini, "fin": fin})
        check("Bloque para profesional inhabilitado -> 409", rb.status_code == 409)

        # ── login bloqueado (55.2) ──
        check("Login del profesional inhabilitado -> 403", (await login(client, "medico.a@todoscare.dev")).status_code == 403)

        # ── remanejo (55.5) ──
        rr = await client.post(f"/empresa/profesionales/{med_a_id}/remanejo", headers=emp, json={"destino_id": str(med_b_id)})
        check("Remanejo -> 200", rr.status_code == 200)
        data = rr.json() if rr.status_code == 200 else {}
        check("Remanejo: al menos 1 movida y 1 conflicto", data.get("movidas", 0) >= 1 and data.get("conflictos", 0) >= 1)

        # remanejo al mismo profesional -> 400
        rsame = await client.post(f"/empresa/profesionales/{med_a_id}/remanejo", headers=emp, json={"destino_id": str(med_a_id)})
        check("Remanejo al mismo profesional -> 400", rsame.status_code == 400)

        # ── rehabilitar y verificar que todo se reactiva ──
        r = await client.patch(f"/empresa/profesionales/{med_a_id}/estado", headers=emp, json={"activo": True})
        check("Rehabilitar -> 200 y activo=true", r.status_code == 200 and r.json().get("activo") is True)
        rb2 = await client.post("/empresa/agendas", headers=emp, json={"professional_id": str(med_a_id), "branch_id": str(branch_id), "inicio": ini, "fin": fin})
        check("Tras rehabilitar, el bloque -> 201", rb2.status_code == 201)
        check("Login del profesional rehabilitado -> 200", (await login(client, "medico.a@todoscare.dev")).status_code == 200)

    # Verifica en BD: s1 se movió a med_b, s2 quedó en med_a (conflicto).
    async with AsyncSessionLocal() as db:
        a1_after = await db.get(Appointment, a1_id)
        a2_after = await db.get(Appointment, a2_id)
        check("Cita sin choque quedó reasignada a med_b", a1_after is not None and a1_after.professional_id == med_b_id)
        check("Cita en conflicto permanece en med_a", a2_after is not None and a2_after.professional_id == med_a_id)

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
