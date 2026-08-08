"""Tanda 6 smoke test: gestión CRM (tareas, encuestas de satisfacción,
plantillas) contra el app real + Postgres real.
Run: `python -m tests.test_crm_gestion_smoke`.
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
        empresa = await login(client, "empresa.a@todoscare.dev")
        medico = await login(client, "medico.a@todoscare.dev")

        # ---- tareas de gestión ----
        r = await client.post("/crm/tareas", headers=empresa, json={"titulo": "Llamar a Camila para control", "descripcion": "Recordar cita de limpieza"})
        results.append(("crear tarea -> 201 pendiente", r.status_code == 201 and r.json()["estado"] == "pendiente"))
        tarea_id = r.json()["id"]

        r = await client.get("/crm/tareas", headers=empresa)
        results.append(("listar tareas -> 1", r.status_code == 200 and len(r.json()) == 1))

        r = await client.patch(f"/crm/tareas/{tarea_id}", headers=empresa, json={"estado": "hecha"})
        results.append(("marcar tarea hecha -> 200", r.status_code == 200 and r.json()["estado"] == "hecha"))

        r = await client.get("/crm/tareas?estado=pendiente", headers=empresa)
        results.append(("filtro pendientes ya no la incluye", all(t["id"] != tarea_id for t in r.json())))

        r = await client.patch(f"/crm/tareas/{tarea_id}", headers=empresa, json={"estado": "volando"})
        results.append(("estado de tarea inválido -> 400", r.status_code == 400))

        r = await client.delete(f"/crm/tareas/{tarea_id}", headers=empresa)
        results.append(("eliminar tarea -> 204", r.status_code == 204))

        # ---- encuestas de satisfacción ----
        r = await client.post("/crm/encuestas", headers=empresa, json={"paciente_nombre": "Camila Reyes"})
        results.append(("enviar encuesta -> 201 enviada", r.status_code == 201 and r.json()["estado"] == "enviada"))
        e1 = r.json()["id"]
        r = await client.post("/crm/encuestas", headers=empresa, json={"paciente_nombre": "Otro Paciente"})
        e2 = r.json()["id"]

        r = await client.get("/crm/encuestas/resumen", headers=empresa)
        results.append(("resumen: 2 enviadas, 0 respondidas", r.json()["enviadas"] == 2 and r.json()["respondidas"] == 0))

        r = await client.post(f"/crm/encuestas/{e1}/responder", headers=empresa, json={"score": 10, "comentario": "Excelente atención"})
        results.append(("responder encuesta (10) -> respondida", r.status_code == 200 and r.json()["estado"] == "respondida"))
        r = await client.post(f"/crm/encuestas/{e2}/responder", headers=empresa, json={"score": 5})
        results.append(("responder segunda (5)", r.status_code == 200))

        # score fuera de rango
        r = await client.post(f"/crm/encuestas/{e2}/responder", headers=empresa, json={"score": 12})
        results.append(("score fuera de rango (0-10) -> 422", r.status_code == 422))

        r = await client.get("/crm/encuestas/resumen", headers=empresa)
        d = r.json()
        results.append(("resumen: 2 respondidas", d["respondidas"] == 2))
        results.append(("promedio = 7.5", abs(d["promedio"] - 7.5) < 0.01))
        results.append(("NPS = 0 (1 promotor 10 − 1 detractor 5)", d["nps"] == 0))
        results.append(("tasa de respuesta = 100%", abs(d["tasa_respuesta"] - 100) < 0.01))

        # ---- plantillas ----
        r = await client.post("/crm/plantillas", headers=empresa, json={"nombre": "Bienvenida", "canal": "email", "asunto": "¡Bienvenido!", "cuerpo": "Hola {nombre}…"})
        results.append(("crear plantilla -> 201", r.status_code == 201))
        pl_id = r.json()["id"]
        r = await client.post("/crm/plantillas", headers=empresa, json={"nombre": "x", "canal": "paloma", "cuerpo": "y"})
        results.append(("canal de plantilla inválido -> 400", r.status_code == 400))
        r = await client.get("/crm/plantillas", headers=empresa)
        results.append(("listar plantillas -> 1", len(r.json()) == 1))
        r = await client.patch(f"/crm/plantillas/{pl_id}", headers=empresa, json={"asunto": "Bienvenida a la clínica"})
        results.append(("editar plantilla -> 200", r.status_code == 200 and r.json()["asunto"] == "Bienvenida a la clínica"))
        r = await client.delete(f"/crm/plantillas/{pl_id}", headers=empresa)
        results.append(("eliminar plantilla -> 204", r.status_code == 204))

        # ---- aislamiento por rol ----
        r = await client.get("/crm/tareas", headers=medico)
        results.append(("médico NO accede a tareas CRM -> 403", r.status_code == 403))

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
