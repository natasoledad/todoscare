"""Smoke test de la ficha financiera del plan de tratamiento (69.7).

Sobre el TreatmentPlan existente añade: descuento comercial, y el resumen
financiero (total bruto/descuento/neto, realizado, abonado, saldo, % progreso).
El "abonado" viene de pagos de caja atribuidos al plan.

Run: `python -m tests.test_ficha_financiera_smoke`.
"""

import asyncio

import httpx

from app.main import app

PASSWORD = "Demo1234!"


async def login(client: httpx.AsyncClient, email: str) -> dict:
    r = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def main() -> None:
    results: list[tuple[str, bool]] = []

    def check(name: str, ok: bool) -> None:
        results.append((name, ok))

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        medico = await login(client, "medico.a@todoscare.dev")
        emp = await login(client, "empresa.a@todoscare.dev")

        cita = next((c for c in (await client.get("/medico/agenda", headers=medico)).json() if "Camila" in c["paciente_nombre"]), None)
        pid = cita["patient_id"]

        # plan: 50000 + 30000*2 = 110000
        r = await client.post(f"/medico/pacientes/{pid}/planes", headers=medico, json={
            "titulo": "Rehab", "items": [
                {"descripcion": "Endodoncia", "pieza": "2.6", "cantidad": 1, "precio_unit": 50000},
                {"descripcion": "Corona", "pieza": "2.6", "cantidad": 2, "precio_unit": 30000},
            ],
        })
        check("Crear plan -> 201", r.status_code == 201)
        plan = r.json()
        plan_id = plan["id"]
        item1 = plan["items"][0]["id"]
        res = plan["resumen"]
        check("Resumen inicial: bruto 110000, neto 110000, saldo 110000, sin abonos", abs(res["total_bruto"] - 110000) < 0.01 and abs(res["total_neto"] - 110000) < 0.01 and abs(res["saldo"] - 110000) < 0.01 and res["abonado"] == 0)

        # descuento comercial 10%
        rd = await client.patch(f"/medico/planes/{plan_id}", headers=medico, json={"descuento_pct": 0.10})
        check("Descuento 10% -> 200", rd.status_code == 200)
        res = rd.json()["resumen"]
        check("Con descuento: descuento 11000, neto 99000, saldo 99000", abs(res["descuento"] - 11000) < 0.01 and abs(res["total_neto"] - 99000) < 0.01 and abs(res["saldo"] - 99000) < 0.01)

        bad = await client.patch(f"/medico/planes/{plan_id}", headers=medico, json={"descuento_pct": 1.5})
        check("Descuento fuera de rango -> 422", bad.status_code == 422)

        # marcar ítem 1 (50000) como realizado -> progreso
        rr = await client.patch(f"/medico/planes/{plan_id}/items/{item1}/estado", headers=medico, json={"estado": "realizado"})
        res = rr.json()["resumen"]
        check("Realizado 50000 y progreso ~45%", abs(res["realizado"] - 50000) < 0.01 and abs(res["progreso_pct"] - 0.4545) < 0.01)

        # atribuir un pago de caja al plan
        caja = (await client.post("/empresa/cajas", headers=emp, json={"abono_inicial": 0})).json()
        pay = await client.post(f"/empresa/cajas/{caja['id']}/movimientos", headers=emp, json={"tipo": "pago", "medio": "efectivo", "monto": 40000, "treatment_plan_id": plan_id})
        check("Pago atribuido al plan -> 201", pay.status_code == 201)

        planes = (await client.get(f"/medico/pacientes/{pid}/planes", headers=medico)).json()
        res = next(p for p in planes if p["id"] == plan_id)["resumen"]
        check("Tras el abono: abonado 40000, saldo 59000", abs(res["abonado"] - 40000) < 0.01 and abs(res["saldo"] - 59000) < 0.01)

        # plan inválido en el pago -> 400
        import uuid as _u
        bad2 = await client.post(f"/empresa/cajas/{caja['id']}/movimientos", headers=emp, json={"tipo": "pago", "medio": "efectivo", "monto": 100, "treatment_plan_id": str(_u.uuid4())})
        check("Pago con plan inválido -> 400", bad2.status_code == 400)

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
