"""Smoke test de órdenes de laboratorio (57.11 · 57.12 · 57.6).

Órdenes de trabajo al lab con flujo de estados, origen desde el plan de
tratamiento del paciente, y cuentas por pagar por laboratorio.

Run: `python -m tests.test_labs_ordenes_smoke`.
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
        emp = await login(client, "empresa.a@todoscare.dev")
        medico = await login(client, "medico.a@todoscare.dev")

        lab = (await client.post("/empresa/labs", headers=emp, json={"nombre": "Laboratorio Dental Sur"})).json()
        svc = (await client.post(f"/empresa/labs/{lab['id']}/servicios", headers=emp, json={"nombre": "Corona de circonio", "costo": 45000, "precio": 120000})).json()

        # orden desde la prestación: hereda costo/precio
        r = await client.post("/empresa/labs/ordenes", headers=emp, json={"lab_id": lab["id"], "lab_service_id": svc["id"], "descripcion": "Corona pieza 2.6", "pieza": "2.6"})
        check("Crear orden desde prestación -> 201", r.status_code == 201)
        o1 = r.json()
        check("Orden hereda costo 45000 y arranca 'solicitado'", o1["costo"] == 45000 and o1["estado"] == "solicitado")

        # orden con origen en el plan de tratamiento del paciente (57.12)
        cita = next((c for c in (await client.get("/medico/agenda", headers=medico)).json() if "Camila" in c["paciente_nombre"]), None)
        pid = cita["patient_id"]
        plan = (await client.post(f"/medico/pacientes/{pid}/planes", headers=medico, json={"titulo": "Rehab", "items": [{"descripcion": "Prótesis", "precio_unit": 60000}]})).json()
        r = await client.post("/empresa/labs/ordenes", headers=emp, json={"lab_id": lab["id"], "descripcion": "Prótesis removible", "treatment_plan_id": plan["id"], "costo": 60000})
        check("Crear orden desde el plan -> 201", r.status_code == 201)
        o2 = r.json()
        check("Orden hereda el paciente del plan (Camila)", o2["patient_id"] == pid and (o2["paciente_nombre"] or "").startswith("Camila"))

        # plan inválido -> 400
        r = await client.post("/empresa/labs/ordenes", headers=emp, json={"lab_id": lab["id"], "descripcion": "x", "treatment_plan_id": "00000000-0000-0000-0000-000000000000"})
        check("Orden con plan inválido -> 400", r.status_code == 400)

        # cuentas por pagar: 2 órdenes, total 105000
        cxp = (await client.get("/empresa/labs/cuentas-por-pagar", headers=emp)).json()
        linea = next((c for c in cxp if c["lab_id"] == lab["id"]), None)
        check("Cuentas por pagar: 2 órdenes, total 105000", linea is not None and linea["cantidad_ordenes"] == 2 and linea["total"] == 105000)

        # flujo de estados válido en o1
        bad = await client.patch(f"/empresa/labs/ordenes/{o1['id']}/estado", headers=emp, json={"estado": "terminado"})
        check("Transición inválida solicitado->terminado -> 400", bad.status_code == 400)
        for est in ("en_proceso", "en_revision", "terminado"):
            r = await client.patch(f"/empresa/labs/ordenes/{o1['id']}/estado", headers=emp, json={"estado": est})
            check(f"Transición -> {est}", r.status_code == 200 and r.json()["estado"] == est)

        # editar una orden terminada -> 400
        r = await client.patch(f"/empresa/labs/ordenes/{o1['id']}", headers=emp, json={"costo": 1})
        check("Editar orden terminada -> 400", r.status_code == 400)

        # pagar la orden terminada
        r = await client.post(f"/empresa/labs/ordenes/{o1['id']}/pagar", headers=emp)
        check("Pagar orden -> 200 pagado", r.status_code == 200 and r.json()["pagado"] is True)
        r = await client.post(f"/empresa/labs/ordenes/{o1['id']}/pagar", headers=emp)
        check("Pagar dos veces -> 400", r.status_code == 400)

        # cuentas por pagar: ahora solo o2 (60000)
        cxp = (await client.get("/empresa/labs/cuentas-por-pagar", headers=emp)).json()
        linea = next((c for c in cxp if c["lab_id"] == lab["id"]), None)
        check("Cuentas por pagar tras pago: 1 orden, 60000", linea is not None and linea["cantidad_ordenes"] == 1 and linea["total"] == 60000)

        # cancelar o2 -> sale de cuentas por pagar
        r = await client.patch(f"/empresa/labs/ordenes/{o2['id']}/estado", headers=emp, json={"estado": "cancelado"})
        check("Cancelar orden -> 200", r.status_code == 200 and r.json()["estado"] == "cancelado")
        cxp = (await client.get("/empresa/labs/cuentas-por-pagar", headers=emp)).json()
        check("Tras cancelar y pagar: sin cuentas por pagar del lab", all(c["lab_id"] != lab["id"] for c in cxp))

        # filtro por estado
        terminadas = (await client.get("/empresa/labs/ordenes", headers=emp, params={"estado": "terminado"})).json()
        check("Filtro estado=terminado incluye o1", any(o["id"] == o1["id"] for o in terminadas))

        # RBAC
        r = await client.get("/empresa/labs/ordenes", headers=medico)
        check("Médico NO ve órdenes de lab -> 403", r.status_code == 403)

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
