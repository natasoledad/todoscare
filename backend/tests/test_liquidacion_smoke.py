"""Smoke test de liquidación de profesionales (58).

Contra la BD seedeada con `app.seed`:

  · Se generan splits (comisiones) para un profesional vía liquidar_atencion.
  · API empresa: liquidaciones activas (realizado/a_pagar), detalle con
    prestación y paciente, y "finalizar" (marca conciliado + asienta egreso).
  · Tras finalizar, el profesional deja de estar en "activas" y aparece en
    "finalizadas"; el ledger tiene los egresos.
  · RBAC: un médico no accede a las liquidaciones de la clínica (403).

Run: `python -m tests.test_liquidacion_smoke`.
"""

import asyncio
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import Range

from app.core.database import AsyncSessionLocal
from app.main import app
from app.models.catalog import CatalogItem
from app.models.finance import LedgerEntry
from app.models.identity import User
from app.models.patient import Patient
from app.models.scheduling import Appointment
from app.models.tenant import Branch, Clinic
from app.services.finance import liquidar_atencion

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
        patient = (await db.execute(select(Patient).where(Patient.clinic_id == clinic.id))).scalars().first()
        clinic_id, branch_id, med_a_id, patient_id = clinic.id, branch.id, med_a.id, patient.id

        svc1 = CatalogItem(clinic_id=clinic_id, tipo="servicio", nombre="Consulta liq", precio=100, duracion_min=30, comisiona=True)
        svc2 = CatalogItem(clinic_id=clinic_id, tipo="servicio", nombre="Procedimiento liq", precio=200, duracion_min=30, comisiona=True)
        db.add_all([svc1, svc2])
        await db.commit()

        base = datetime.now(timezone.utc) + timedelta(days=300)
        appts = []
        for i, svc in enumerate((svc1, svc2)):
            appt = Appointment(
                clinic_id=clinic_id, branch_id=branch_id, professional_id=med_a_id, patient_id=patient_id,
                service_id=svc.id, slot=Range(base + timedelta(hours=i), base + timedelta(hours=i, minutes=30)), estado="completada",
            )
            db.add(appt)
            appts.append((appt, svc))
        await db.commit()
        for appt, svc in appts:
            await db.refresh(appt)
            await liquidar_atencion(db, clinic_id=clinic_id, professional_id=med_a_id, service=svc, appointment_id=appt.id)
        await db.commit()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        emp = await login(client, "empresa.a@todoscare.dev")

        # ── activas ──
        act = (await client.get("/empresa/liquidaciones?estado=activas", headers=emp)).json()
        me = next((x for x in act if x["professional_id"] == str(med_a_id)), None)
        check("Liquidaciones activas: aparece el profesional", me is not None)
        check("Liquidaciones: realizado=300 y a_pagar=180 (60% def), cantidad=2",
              me is not None and abs(me["realizado"] - 300) < 0.01 and abs(me["a_pagar"] - 180) < 0.01 and me["cantidad"] == 2)

        # ── detalle ──
        det = (await client.get(f"/empresa/liquidaciones/{med_a_id}/detalle?estado=activas", headers=emp)).json()
        check("Detalle: 2 líneas", len(det) == 2)
        check("Detalle: resuelve prestación y paciente", all(d["prestacion"] for d in det) and all(d["paciente"] for d in det))

        # ── finalizar ──
        fin = await client.post(f"/empresa/liquidaciones/{med_a_id}/finalizar", headers=emp, json={})
        check("Finalizar -> 200", fin.status_code == 200)
        fd = fin.json() if fin.status_code == 200 else {}
        check("Finalizar: 2 finalizadas, monto 180", fd.get("finalizadas") == 2 and abs(fd.get("monto", 0) - 180) < 0.01)

        # ── tras finalizar ──
        act2 = (await client.get("/empresa/liquidaciones?estado=activas", headers=emp)).json()
        check("Activas: el profesional ya no aparece", not any(x["professional_id"] == str(med_a_id) for x in act2))
        finz = (await client.get("/empresa/liquidaciones?estado=finalizadas", headers=emp)).json()
        me_fin = next((x for x in finz if x["professional_id"] == str(med_a_id)), None)
        check("Finalizadas: aparece con a_pagar 180", me_fin is not None and abs(me_fin["a_pagar"] - 180) < 0.01)

        # ── RBAC ──
        med = await login(client, "medico.a@todoscare.dev")
        r403 = await client.get("/empresa/liquidaciones", headers=med)
        check("RBAC: médico NO accede a liquidaciones -> 403", r403.status_code == 403)

    # ── ledger: egresos asentados ──
    async with AsyncSessionLocal() as db:
        total = (
            await db.execute(
                select(func.coalesce(func.sum(LedgerEntry.monto), 0)).where(
                    LedgerEntry.clinic_id == clinic_id, LedgerEntry.tipo == "liquidacion_pagada"
                )
            )
        ).scalar_one()
        check("Ledger: egresos de liquidación por 180", abs(float(total) - 180) < 0.01)

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
