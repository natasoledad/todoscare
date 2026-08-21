"""Smoke test · Fichas clínicas por especialidad (71.7).

Plantillas de campos configurables por especialidad + registro de esos campos en
la atención (contenido_extra del prontuario), con validación y RBAC.

Run: `python -m tests.test_fichas_esp_smoke`.
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
        paciente = await login(client, "paciente.a@todoscare.dev")

        # ── crear plantilla de ficha ──
        campos = [
            {"clave": "soplo", "label": "Soplo cardíaco", "tipo": "opcion", "opciones": ["sí", "no"]},
            {"clave": "fc_reposo", "label": "FC en reposo", "tipo": "numero"},
        ]
        r = await client.post("/medico/fichas-especialidad", headers=medico, json={"nombre": "Ficha cardiología", "campos": campos})
        t = r.json()
        results.append(("crear ficha -> 201 con 2 campos", r.status_code == 201 and len(t["campos"]) == 2))
        tid = t["id"]

        r = await client.get("/medico/fichas-especialidad", headers=medico)
        results.append(("listar fichas incluye la nueva", any(x["id"] == tid for x in r.json())))

        # ── validaciones ──
        r = await client.post("/medico/fichas-especialidad", headers=medico, json={"nombre": "Mala", "campos": [{"clave": "x", "label": "X", "tipo": "raro"}]})
        results.append(("tipo de campo inválido -> 400", r.status_code == 400))
        r = await client.post("/medico/fichas-especialidad", headers=medico, json={"nombre": "Dup", "campos": [{"clave": "a", "label": "A"}, {"clave": "a", "label": "B"}]})
        results.append(("clave duplicada -> 400", r.status_code == 400))

        # ── editar (agregar campo) ──
        r = await client.patch(f"/medico/fichas-especialidad/{tid}", headers=medico, json={"campos": campos + [{"clave": "notas", "label": "Notas", "tipo": "area"}]})
        results.append(("editar ficha -> 3 campos", r.status_code == 200 and len(r.json()["campos"]) == 3))

        # ── usar la ficha en la atención (contenido_extra) ──
        cita = next((c for c in (await client.get("/medico/agenda", headers=medico)).json() if "Camila" in c["paciente_nombre"]), None)
        r = await client.post(f"/medico/citas/{cita['id']}/atencion", headers=medico, json={
            "motivo": "Control cardiológico", "contenido_extra": {"soplo": "no", "fc_reposo": 72},
        })
        cont = r.json().get("contenido", {})
        results.append(("atención guarda los campos de la ficha", r.status_code == 201 and cont.get("soplo") == "no" and cont.get("fc_reposo") == 72))

        # ── RBAC + borrar ──
        r = await client.post("/medico/fichas-especialidad", headers=paciente, json={"nombre": "X", "campos": []})
        results.append(("paciente no crea fichas", r.status_code in (401, 403)))
        r = await client.delete(f"/medico/fichas-especialidad/{tid}", headers=medico)
        results.append(("borrar ficha -> 204", r.status_code == 204))

    print("\n=== Fichas por especialidad (71.7) · smoke ===")
    ok = True
    for name, passed in results:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
        ok = ok and passed
    print("=== OK ===" if ok else "=== FALLÓ ===")
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
