"""Smoke test · Logo por empresa en documentos (65.1).

La empresa sube el logo de la clínica; se refleja en la info y se estampa en el
presupuesto imprimible del profesional.

Run: `python -m tests.test_logo_smoke`.
"""

import asyncio

import httpx

from app.main import app

PASSWORD = "Demo1234!"
LOGO = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="


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

        # ── logo inicialmente vacío ──
        r = await client.get("/empresa/info", headers=empresa)
        results.append(("info sin logo al inicio", r.status_code == 200 and r.json().get("logo") is None))

        # ── subir logo ──
        r = await client.patch("/empresa/info", headers=empresa, json={"logo": LOGO})
        results.append(("subir logo -> 200", r.status_code == 200 and r.json()["logo"] == LOGO))
        r = await client.get("/empresa/info", headers=empresa)
        results.append(("logo persistido", r.json()["logo"] == LOGO))

        # ── logo demasiado grande -> 400 ──
        r = await client.patch("/empresa/info", headers=empresa, json={"logo": "data:image/png;base64," + "A" * 2_000_001})
        results.append(("logo demasiado grande -> 400", r.status_code == 400))

        # ── el presupuesto del médico estampa el logo ──
        cita = next((c for c in (await client.get("/medico/agenda", headers=medico)).json() if "Camila" in c["paciente_nombre"]), None)
        pid = cita["patient_id"]
        r = await client.post(f"/medico/pacientes/{pid}/planes", headers=medico, json={"titulo": "Plan", "items": [{"descripcion": "Consulta", "cantidad": 1, "precio_unit": 30000}]})
        plan_id = r.json()["id"]
        r = await client.get(f"/medico/planes/{plan_id}/presupuesto", headers=medico)
        results.append(("presupuesto incluye el logo de la clínica", r.status_code == 200 and r.json()["clinica_logo"] == LOGO))

        # ── limpiar logo ("") ──
        r = await client.patch("/empresa/info", headers=empresa, json={"logo": ""})
        results.append(("limpiar logo -> null", r.status_code == 200 and r.json()["logo"] is None))

    print("\n=== Logo por empresa (65.1) · smoke ===")
    ok = True
    for name, passed in results:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
        ok = ok and passed
    print("=== OK ===" if ok else "=== FALLÓ ===")
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
