"""Smoke test de documentos + consentimientos (64).

Plantillas por bloques (64.3), emisión de un consentimiento desde plantilla
rellenando campos (64.6), y firma del paciente en su portal (64.8).

Run: `python -m tests.test_documentos_smoke`.
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
        paciente = await login(client, "paciente.a@todoscare.dev")

        # plantilla de consentimiento por bloques (requiere firma)
        r = await client.post("/medico/plantillas-documento", headers=medico, json={
            "nombre": "Consentimiento extracción", "tipo": "consentimiento", "requiere_firma": True,
            "bloques": [
                {"tipo": "parrafo", "texto": "Yo autorizo el procedimiento indicado a continuación."},
                {"tipo": "campo", "label": "Procedimiento", "clave": "procedimiento"},
                {"tipo": "campo", "label": "Pieza", "clave": "pieza"},
            ],
        })
        check("Crear plantilla -> 201", r.status_code == 201)
        tmpl = r.json()
        check("La plantilla guarda 3 bloques y requiere firma", len(tmpl["bloques"]) == 3 and tmpl["requiere_firma"])

        r = await client.get("/medico/plantillas-documento", headers=medico)
        check("Plantilla listada", any(t["id"] == tmpl["id"] for t in r.json()))

        # paciente de la agenda del médico
        cita = next((c for c in (await client.get("/medico/agenda", headers=medico)).json() if "Camila" in c["paciente_nombre"]), None)
        pid = cita["patient_id"]

        # emitir el documento desde la plantilla, rellenando campos
        r = await client.post(f"/medico/pacientes/{pid}/documentos", headers=medico, json={
            "tipo": "otro", "titulo": "Consentimiento de Camila", "template_id": tmpl["id"],
            "campos": {"procedimiento": "Extracción", "pieza": "3.6"},
        })
        check("Emitir documento desde plantilla -> 201", r.status_code == 201)
        doc = r.json()
        check("Tipo heredado de la plantilla (consentimiento)", doc["tipo"] == "consentimiento")
        check("Contenido renderizado con los campos", "Extracción" in (doc["contenido"] or "") and "3.6" in (doc["contenido"] or ""))
        check("El documento requiere firma", doc["requiere_firma"] and not doc["firmado_paciente"])

        # el paciente ve el documento y lo firma
        docs = (await client.get("/salud/documentos", headers=paciente)).json()
        mine = next((d for d in docs if d["id"] == doc["id"]), None)
        check("El paciente ve su documento pendiente de firma", mine is not None and mine["requiere_firma"] and not mine["firmado_paciente"])

        r = await client.post(f"/salud/documentos/{doc['id']}/firmar", headers=paciente)
        check("Firmar -> 200 firmado con fecha", r.status_code == 200 and r.json()["firmado_paciente"] and r.json()["firmado_at"])

        # firmar dos veces -> 400
        r = await client.post(f"/salud/documentos/{doc['id']}/firmar", headers=paciente)
        check("Firmar dos veces -> 400", r.status_code == 400)

        # un documento sin firma no se puede firmar
        r = await client.post(f"/medico/pacientes/{pid}/documentos", headers=medico, json={"tipo": "certificado", "titulo": "Certificado de asistencia", "contenido": "Asistió hoy."})
        doc2 = r.json()
        check("Certificado sin firma creado", r.status_code == 201 and not doc2["requiere_firma"])
        r = await client.post(f"/salud/documentos/{doc2['id']}/firmar", headers=paciente)
        check("Firmar un documento sin firma -> 400", r.status_code == 400)

        # RBAC: el paciente no gestiona plantillas
        r = await client.get("/medico/plantillas-documento", headers=paciente)
        check("Paciente NO gestiona plantillas -> 403", r.status_code == 403)

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
