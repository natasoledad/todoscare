"""Tanda 3 smoke test: signos vitales + planes de tratamiento/presupuestos,
contra el app real + Postgres real.

Cubre: registrar y listar signos vitales; crear un plan con ítems y que el
total se calcule de los ítems; cambiar estado del plan y marcar un ítem como
realizado; acceso auditado solo del profesional tratante; y aislamiento (otro
médico que no trata al paciente no accede). Run: `python -m tests.test_clinico_smoke`.
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
    transport = httpx.ASGITransport(app=app)
    results: list[tuple[str, bool]] = []

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        medico = await login(client, "medico.a@todoscare.dev")
        medico_b = await login(client, "medico.b@todoscare.dev")   # no trata a Camila
        paciente = await login(client, "paciente.a@todoscare.dev")

        r = await client.get("/medico/agenda", headers=medico)
        cita = next((c for c in r.json() if "Camila" in c["paciente_nombre"]), None)
        results.append(("médico tiene la cita de Camila", cita is not None))
        pid = cita["patient_id"]

        # ---- signos vitales ----
        r = await client.post(
            f"/medico/pacientes/{pid}/signos-vitales", headers=medico,
            json={"presion_sistolica": 120, "presion_diastolica": 80, "fc_ppm": 72, "spo2": 98, "peso_kg": 68.5, "temperatura": 36.6, "eva": 2},
        )
        results.append(("registrar signos vitales -> 201", r.status_code == 201 and r.json()["presion_sistolica"] == 120))

        r = await client.get(f"/medico/pacientes/{pid}/signos-vitales", headers=medico)
        results.append(("listar signos vitales -> 1 registro", r.status_code == 200 and len(r.json()) == 1))
        results.append(("el peso se conserva (68.5)", abs(r.json()[0]["peso_kg"] - 68.5) < 0.01))

        # el paciente no registra signos vitales
        r = await client.post(f"/medico/pacientes/{pid}/signos-vitales", headers=paciente, json={"fc_ppm": 60})
        results.append(("paciente NO registra signos vitales -> 403", r.status_code == 403))

        # otro médico que no trata al paciente
        r = await client.get(f"/medico/pacientes/{pid}/signos-vitales", headers=medico_b)
        results.append(("médico que no trata al paciente -> 403/404", r.status_code in (403, 404)))

        # ---- planes de tratamiento / presupuesto ----
        r = await client.post(
            f"/medico/pacientes/{pid}/planes", headers=medico,
            json={
                "titulo": "Rehabilitación oral",
                "notas": "Plan en 2 sesiones",
                "items": [
                    {"descripcion": "Endodoncia 2.6", "pieza": "2.6", "cantidad": 1, "precio_unit": 50000},
                    {"descripcion": "Corona", "pieza": "2.6", "cantidad": 2, "precio_unit": 30000},
                ],
            },
        )
        results.append(("crear plan con 2 ítems -> 201", r.status_code == 201))
        plan = r.json()
        results.append(("el total se calcula de los ítems (110000)", abs(plan["total"] - 110000) < 0.01))
        results.append(("el subtotal del ítem 2 = 60000", abs(plan["items"][1]["subtotal"] - 60000) < 0.01))
        results.append(("estado inicial 'propuesto'", plan["estado"] == "propuesto"))
        plan_id = plan["id"]
        item_id = plan["items"][0]["id"]

        r = await client.get(f"/medico/pacientes/{pid}/planes", headers=medico)
        results.append(("listar planes -> 1", r.status_code == 200 and len(r.json()) == 1))

        # aceptar el plan
        r = await client.patch(f"/medico/planes/{plan_id}/estado", headers=medico, json={"estado": "aceptado"})
        results.append(("aceptar el plan -> estado 'aceptado'", r.status_code == 200 and r.json()["estado"] == "aceptado"))

        # estado inválido
        r = await client.patch(f"/medico/planes/{plan_id}/estado", headers=medico, json={"estado": "volando"})
        results.append(("estado de plan inválido -> 400", r.status_code == 400))

        # marcar un ítem como realizado
        r = await client.patch(f"/medico/planes/{plan_id}/items/{item_id}/estado", headers=medico, json={"estado": "realizado"})
        results.append(("marcar ítem 'realizado' -> 200", r.status_code == 200))
        item0 = next((i for i in r.json()["items"] if i["id"] == item_id), None)
        results.append(("el ítem quedó 'realizado'", bool(item0 and item0["estado"] == "realizado")))

        # otro médico no accede al plan
        r = await client.patch(f"/medico/planes/{plan_id}/estado", headers=medico_b, json={"estado": "completado"})
        results.append(("médico ajeno NO cambia el plan -> 403/404", r.status_code in (403, 404)))

    print()
    failed = 0
    for name, ok in results:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
        failed += 0 if ok else 1
    print()
    if failed:
        print(f"{failed} check(s) FAILED")
        raise SystemExit(1)
    print(f"All {len(results)} checks passed.")


if __name__ == "__main__":
    asyncio.run(main())
