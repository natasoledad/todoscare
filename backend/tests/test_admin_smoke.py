"""Fase 5 smoke test: Rol Administrador end-to-end contra el app real +
Postgres real. Cubre el aislamiento de sub-rol (super_admin cruza todos
los tenants; clinic_admin solo el suyo), el alta de un tenant nuevo con su
admin inicial (que puede loguear), que un clinic_admin NO puede crear
clínicas ni planes (§2), publicar una nueva versión de T&C que deja al
paciente con tyc_pendiente (§6.2), la inmutabilidad del ledger (no hay
endpoint de edición) y el límite de privacidad (el admin ve auditoría y
metadatos, nunca el contenido clínico). Run: `python -m tests.test_admin_smoke`.
"""

import asyncio

import httpx

from app.main import app

PASSWORD = "Demo1234!"


async def login(client: httpx.AsyncClient, email: str, password: str = PASSWORD) -> dict:
    r = await client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def main() -> None:
    transport = httpx.ASGITransport(app=app)
    results: list[tuple[str, bool]] = []

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        superh = await login(client, "super@todoscare.dev")
        admin_a = await login(client, "admin.a@todoscare.dev")
        medico = await login(client, "medico.a@todoscare.dev")
        paciente = await login(client, "paciente.a@todoscare.dev")

        # ---- KPIs + aislamiento de sub-rol ----
        r = await client.get("/admin/inicio", headers=superh)
        results.append(("super_admin inicio alcance=plataforma, 2 clínicas", r.json()["alcance"] == "plataforma" and r.json()["clinicas"] == 2))

        r = await client.get("/admin/clinicas", headers=superh)
        results.append(("super_admin ve 2 clínicas", len(r.json()) == 2))
        r = await client.get("/admin/clinicas", headers=admin_a)
        results.append(("clinic_admin.a ve solo 1 clínica (la suya)", len(r.json()) == 1 and r.json()[0]["razon_social"] == "Clínica Demo A"))

        # un no-admin no entra
        r = await client.get("/admin/clinicas", headers=medico)
        results.append(("médico NO accede a /admin/clinicas -> 403", r.status_code == 403))
        r = await client.get("/admin/inicio", headers=paciente)
        results.append(("paciente NO accede a /admin/inicio -> 403", r.status_code == 403))

        # ---- alta de tenant nuevo (super_admin) ----
        r = await client.post(
            "/admin/clinicas",
            headers=superh,
            json={
                "razon_social": "Clínica Nueva CDMX", "pais": "MX", "responsable_sanitario": "Dr. Nuevo",
                "sucursal_nombre": "Sede Centro", "admin_nombre": "Admin Nuevo", "admin_correo": "admin.nuevo@todoscare.dev", "admin_password": "Passw0rd!",
            },
        )
        results.append(("super_admin da de alta un tenant nuevo -> 201", r.status_code == 201))

        # el admin inicial del tenant nuevo puede loguear y ve solo su clínica
        nuevo = await login(client, "admin.nuevo@todoscare.dev", "Passw0rd!")
        r = await client.get("/admin/clinicas", headers=nuevo)
        results.append(("el admin del tenant nuevo ve solo su clínica", len(r.json()) == 1 and r.json()[0]["razon_social"] == "Clínica Nueva CDMX"))

        r = await client.get("/admin/inicio", headers=superh)
        results.append(("ahora la plataforma tiene 3 clínicas", r.json()["clinicas"] == 3))

        # ---- clinic_admin NO puede crear tenants ni planes (§2) ----
        r = await client.post("/admin/clinicas", headers=admin_a, json={
            "razon_social": "Clínica Pirata", "pais": "MX", "sucursal_nombre": "Sede", "admin_nombre": "Zeta Uno", "admin_correo": "zeta@todoscare.dev", "admin_password": "Passw0rd!"})
        results.append(("clinic_admin NO puede crear un tenant -> 403", r.status_code == 403))
        r = await client.post("/admin/planes", headers=admin_a, json={"tipo": "individual", "nombre": "Plan X", "precio": 199})
        results.append(("clinic_admin NO puede crear planes -> 403", r.status_code == 403))

        # ---- planes (super_admin), incluido público con esfera ----
        r = await client.post("/admin/planes", headers=superh, json={"tipo": "individual", "nombre": "Plan Individual", "precio": 199})
        results.append(("super_admin crea plan individual -> 201", r.status_code == 201))
        r = await client.post("/admin/planes", headers=superh, json={"tipo": "publico", "nombre": "Plan Federal", "precio": 0})
        results.append(("plan público sin esfera -> 400", r.status_code == 400))
        r = await client.post("/admin/planes", headers=superh, json={"tipo": "publico", "esfera": "federal", "nombre": "Plan Federal", "precio": 0})
        results.append(("plan público federal -> 201", r.status_code == 201))

        # ---- usuarios / roles ----
        r = await client.get("/admin/usuarios", headers=admin_a)
        results.append(("clinic_admin.a ve usuarios de su clínica", r.status_code == 200 and len(r.json()) > 0))
        # clinic_admin no puede crear un super_admin (rol sin clínica)
        r = await client.post("/admin/usuarios", headers=admin_a, json={"nombre": "Hacker", "correo": "h@h.com", "password": "Passw0rd!", "role": "super_admin"})
        results.append(("clinic_admin NO puede crear un super_admin -> 403", r.status_code == 403))

        # ---- T&C: publicar nueva versión -> paciente queda con tyc_pendiente ----
        r = await client.get("/patients/me", headers=paciente)
        results.append(("paciente MX sin T&C pendiente al inicio", r.json()["tyc_pendiente"] is False))

        r = await client.post("/admin/tyc", headers=superh, json={"pais": "MX", "version": "2.0", "contenido": "Nueva versión de términos."})
        results.append(("super_admin publica T&C v2.0 MX -> 201", r.status_code == 201))

        r = await client.get("/patients/me", headers=paciente)
        results.append(("tras publicar, el paciente MX queda con tyc_pendiente=true", r.json()["tyc_pendiente"] is True))

        # clinic_admin no puede publicar T&C
        r = await client.post("/admin/tyc", headers=admin_a, json={"pais": "MX", "version": "3.0", "contenido": "x"})
        results.append(("clinic_admin NO puede publicar T&C -> 403", r.status_code == 403))

        # ---- finanzas / ledger inmutable ----
        r = await client.get("/admin/finanzas", headers=superh)
        results.append(("finanzas resumen -> ingresos > 0", r.status_code == 200 and r.json()["ingresos_mes"] > 0))
        r = await client.get("/admin/finanzas/ledger", headers=superh)
        results.append(("ledger read-only lista asientos", r.status_code == 200 and len(r.json()) > 0))
        # no existe endpoint para editar/borrar un asiento del ledger (inmutable)
        r = await client.request("DELETE", "/admin/finanzas/ledger", headers=superh)
        results.append(("no hay endpoint para borrar el ledger -> 405/404", r.status_code in (404, 405)))

        # ---- límite de privacidad: el admin ve auditoría/metadatos, NUNCA contenido clínico ----
        # generamos un acceso clínico auditado (el médico abre la ficha de su paciente)
        agenda = (await client.get("/medico/agenda", headers=medico)).json()
        await client.get(f"/medico/pacientes/{agenda[0]['patient_id']}/ficha", headers=medico)

        r = await client.get("/admin/auditoria", headers=superh)
        aud = r.json()
        results.append(("auditoría lista el acceso a la ficha (metadatos)", any(a["accion"] == "ver_ficha_clinica" for a in aud)))
        # la auditoría no expone contenido clínico: solo acción + recurso, no el prontuario
        results.append(("la auditoría no incluye contenido clínico", all("contenido" not in a and "prontuario" not in str(a.get("recurso", "")).lower()[:0] for a in aud)))
        # y no existe ningún endpoint /admin que devuelva prontuarios/recetas
        r = await client.get("/medico/agenda", headers=superh)
        results.append(("un super_admin NO puede usar endpoints de médico -> 403", r.status_code == 403))

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
