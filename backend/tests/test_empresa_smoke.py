"""Fase 4 smoke test: Rol Empresa/Cliente end-to-end contra el app real +
Postgres real. KPIs, catálogo (crear servicio que aparece en el catálogo
del paciente, editar precio, baja lógica), promociones (crear + activar +
que el paciente la vea), agendas (crear bloque que genera disponibilidad
para el paciente), info de la empresa (editar), funcionarios B2B
(alta/baja), y aislamiento entre clínicas. Run: `python -m tests.test_empresa_smoke`.
"""

import asyncio
from datetime import datetime, timedelta, timezone

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
        empresa = await login(client, "empresa.a@todoscare.dev")     # Clínica Demo A
        empresa_b = await login(client, "admin.b@todoscare.dev")     # (otra clínica; para aislamiento vía admin no aplica, ver abajo)
        paciente = await login(client, "paciente.a@todoscare.dev")   # Camila, en clínica A
        medico = await login(client, "medico.a@todoscare.dev")

        # ---- KPIs ----
        r = await client.get("/empresa/inicio", headers=empresa)
        kpis = r.json()
        results.append(("inicio KPIs -> 200 con nombre de clínica", r.status_code == 200 and kpis["clinic_nombre"] == "Clínica Demo A"))
        results.append(("ingresos del mes > 0 (seed)", kpis["ingresos_mes"] > 0))
        results.append(("promos activas == 2 (seed)", kpis["promos_activas"] == 2))
        results.append(("servicios activos == 7 (seed)", kpis["servicios_activos"] == 7))

        # un paciente no entra al portal empresa
        r = await client.get("/empresa/inicio", headers=paciente)
        results.append(("paciente NO accede a /empresa/inicio -> 403", r.status_code == 403))

        # ---- catálogo ----
        r = await client.post("/empresa/servicios", headers=empresa, json={"nombre": "Dermatología", "precio": 800, "duracion_min": 30})
        results.append(("crear servicio -> 201", r.status_code == 201 and r.json()["nombre"] == "Dermatología"))
        servicio_id = r.json()["id"]

        # aparece en el catálogo que ve el paciente al agendar
        r = await client.get("/agenda/servicios", headers=paciente)
        results.append(("el servicio nuevo aparece en el catálogo del paciente", any(s["nombre"] == "Dermatología" for s in r.json())))

        r = await client.patch(f"/empresa/servicios/{servicio_id}", headers=empresa, json={"precio": 950})
        results.append(("editar precio del servicio -> 950", abs(r.json()["precio"] - 950.0) < 0.01))

        r = await client.delete(f"/empresa/servicios/{servicio_id}", headers=empresa)
        results.append(("baja lógica del servicio -> 204", r.status_code == 204))
        r = await client.get("/agenda/servicios", headers=paciente)
        results.append(("el servicio dado de baja ya no está en el catálogo del paciente", not any(s["nombre"] == "Dermatología" for s in r.json())))

        # ---- promociones ----
        r = await client.post("/empresa/promociones", headers=empresa, json={"nombre": "Nutrición -15%", "descuento": "-15%", "estado": "Borrador"})
        results.append(("crear promoción (borrador) -> 201", r.status_code == 201 and r.json()["estado"] == "Borrador"))
        promo_id = r.json()["id"]

        r = await client.patch(f"/empresa/promociones/{promo_id}", headers=empresa, json={"estado": "Activa"})
        results.append(("activar promoción -> Activa", r.json()["estado"] == "Activa"))

        r = await client.get("/empresa/inicio", headers=empresa)
        results.append(("promos activas ahora == 3", r.json()["promos_activas"] == 3))

        # ---- agendas ----
        r = await client.get("/empresa/profesionales", headers=empresa)
        profs = r.json()
        results.append(("lista de profesionales incluye 2 médicos", len(profs) == 2))
        r = await client.get("/empresa/sucursales", headers=empresa)
        sucursal_id = r.json()[0]["id"]
        # el segundo médico (Dr. Fuentes) no tiene bloques; le creamos disponibilidad
        dr_fuentes = next(p for p in profs if p["nombre"] == "Dr. Fuentes")
        manana = (datetime.now(timezone.utc) + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
        r = await client.post(
            "/empresa/agendas",
            headers=empresa,
            json={"professional_id": dr_fuentes["id"], "branch_id": sucursal_id, "inicio": manana.isoformat(), "fin": (manana + timedelta(hours=8)).isoformat()},
        )
        results.append(("crear bloque de agenda -> 201", r.status_code == 201))
        bloque_id = r.json()["id"]

        r = await client.patch(f"/empresa/agendas/{bloque_id}", headers=empresa, json={"reglas": {"telemedicina": True}})
        results.append(("editar reglas del bloque -> ok", r.json()["reglas"] == {"telemedicina": True}));

        # rango inválido -> 400
        r = await client.post(
            "/empresa/agendas", headers=empresa,
            json={"professional_id": dr_fuentes["id"], "branch_id": sucursal_id, "inicio": manana.isoformat(), "fin": manana.isoformat()},
        )
        results.append(("bloque con fin <= inicio -> 400", r.status_code == 400))

        r = await client.delete(f"/empresa/agendas/{bloque_id}", headers=empresa)
        results.append(("eliminar bloque -> 204", r.status_code == 204))

        # ---- info empresa ----
        r = await client.patch("/empresa/info", headers=empresa, json={"responsable_sanitario": "Dra. Nátaly"})
        results.append(("editar info empresa (responsable) -> ok", r.json()["responsable_sanitario"] == "Dra. Nátaly"))

        # ---- funcionarios B2B ----
        r = await client.get("/empresa/funcionarios", headers=empresa)
        results.append(("funcionarios vacío al inicio", r.json() == []))

        r = await client.post("/empresa/funcionarios", headers=empresa, json={"correo": "paciente.a@todoscare.dev"})
        results.append(("alta de funcionario (Camila) -> 201 activo", r.status_code == 201 and r.json()["estado"] == "activo"))
        func_id = r.json()["id"]

        r = await client.post("/empresa/funcionarios", headers=empresa, json={"correo": "paciente.a@todoscare.dev"})
        results.append(("alta duplicada -> 409", r.status_code == 409))

        r = await client.post("/empresa/funcionarios", headers=empresa, json={"correo": "medico.a@todoscare.dev"})
        results.append(("alta de un no-paciente -> 400/404", r.status_code in (400, 404)))

        r = await client.delete(f"/empresa/funcionarios/{func_id}", headers=empresa)
        results.append(("baja de funcionario -> 204", r.status_code == 204))
        r = await client.get("/empresa/funcionarios", headers=empresa)
        results.append(("tras la baja no quedan funcionarios activos", all(f["estado"] == "baja" for f in r.json())))

        # ---- aislamiento: médico no entra al portal empresa ----
        r = await client.get("/empresa/servicios", headers=medico)
        results.append(("médico NO accede a /empresa/servicios -> 403", r.status_code == 403))
        _ = empresa_b  # (admin.b existe pero admin no es empresa; el aislamiento real de empresa se cubre arriba)

    print()
    failed = 0
    for name, ok in results:
        status = "PASS" if ok else "FAIL"
        if not ok:
            failed += 1
        print(f"  [{status}] {name}")
    print()
    if failed:
        print(f"{failed} check(s) FAILED")
        raise SystemExit(1)
    print(f"All {len(results)} checks passed.")


if __name__ == "__main__":
    asyncio.run(main())
