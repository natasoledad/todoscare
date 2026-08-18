"""Smoke test de comisión por servicio + regla del profesional (57.10 / 62.7).

Contra la BD seedeada con `app.seed`:

  · API: alta/edición de servicio con flag `comisiona`; perfil del profesional
    con `comision_pct`.
  · Lógica de split (liquidar_atencion):
      - servicio que comisiona + profesional con % propio -> split a ese %.
      - servicio que NO comisiona -> sin split, pero el ingreso sí se asienta.
      - profesional sin % propio -> split al % por defecto de la clínica (60%).

Run: `python -m tests.test_comision_smoke`.
"""

import asyncio
import uuid

import httpx
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.main import app
from app.models.catalog import CatalogItem
from app.models.finance import LedgerEntry
from app.models.identity import User
from app.models.tenant import Clinic
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
        med_a = (await db.execute(select(User).where(User.email == "medico.a@todoscare.dev"))).scalar_one()
        med_b = (await db.execute(select(User).where(User.email == "medico.b@todoscare.dev"))).scalar_one()
        clinic_id, med_a_id, med_b_id = clinic.id, med_a.id, med_b.id
        # Servicios de prueba: uno que comisiona, otro que no.
        svc_com = CatalogItem(clinic_id=clinic_id, tipo="servicio", nombre="Acción clínica test", precio=100, duracion_min=30, comisiona=True)
        svc_nocom = CatalogItem(clinic_id=clinic_id, tipo="servicio", nombre="Prestación lab test", precio=200, duracion_min=30, comisiona=False)
        db.add_all([svc_com, svc_nocom])
        await db.commit()
        svc_com_id, svc_nocom_id = svc_com.id, svc_nocom.id

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        emp = await login(client, "empresa.a@todoscare.dev")

        # ── API: servicio con flag comisiona ──
        r = await client.post("/empresa/servicios", headers=emp, json={"nombre": "Corona lab", "precio": 300, "duracion_min": 30, "comisiona": False})
        check("Servicio: alta con comisiona=false -> 201", r.status_code == 201 and r.json().get("comisiona") is False)
        sid = r.json()["id"]
        re = await client.patch(f"/empresa/servicios/{sid}", headers=emp, json={"comisiona": True})
        check("Servicio: editar comisiona -> true", re.status_code == 200 and re.json().get("comisiona") is True)

        # ── API: perfil con comision_pct ──
        rp = await client.patch(f"/empresa/profesionales/{med_a_id}/perfil", headers=emp, json={"comision_pct": 0.5})
        check("Perfil: set comision_pct=0.5 -> 200", rp.status_code == 200 and abs((rp.json().get("comision_pct") or 0) - 0.5) < 0.01)
        profs = (await client.get("/empresa/profesionales", headers=emp)).json()
        me = next((p for p in profs if p["id"] == str(med_a_id)), None)
        check("Profesionales: el listado refleja comision_pct", me is not None and abs((me.get("comision_pct") or 0) - 0.5) < 0.01)

    # ── lógica de split ──
    async with AsyncSessionLocal() as db:
        svc = await db.get(CatalogItem, svc_com_id)
        split = await liquidar_atencion(db, clinic_id=clinic_id, professional_id=med_a_id, service=svc, appointment_id=uuid.uuid4())
        ok = split is not None and abs(float(split.monto) - 50.0) < 0.01 and float(split.regla.get("pct")) == 0.5
        await db.commit()
    check("Split: servicio que comisiona + perfil 50% -> split 50", ok)

    async with AsyncSessionLocal() as db:
        svc = await db.get(CatalogItem, svc_nocom_id)
        aid = uuid.uuid4()
        split = await liquidar_atencion(db, clinic_id=clinic_id, professional_id=med_a_id, service=svc, appointment_id=aid)
        await db.commit()
        led = (await db.execute(select(LedgerEntry).where(LedgerEntry.ref == f"appointment:{aid}"))).scalars().first()
        ok_nocom = split is None and led is not None and abs(float(led.monto) - 200.0) < 0.01
    check("Split: servicio que NO comisiona -> sin split pero con ingreso", ok_nocom)

    async with AsyncSessionLocal() as db:
        svc = await db.get(CatalogItem, svc_com_id)
        split = await liquidar_atencion(db, clinic_id=clinic_id, professional_id=med_b_id, service=svc, appointment_id=uuid.uuid4())
        ok_def = split is not None and abs(float(split.monto) - 60.0) < 0.01
        await db.commit()
    check("Split: profesional sin % propio -> 60% por defecto", ok_def)

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
