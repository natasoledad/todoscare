"""Smoke test · Firma manuscrita del profesional (48).

El profesional dibuja su firma en la app y la guarda en su perfil; al emitir un
documento, la firma queda estampada (instantánea inmutable). Cambiar la firma
después no altera documentos ya emitidos.

Run: `python -m tests.test_firma_smoke`.
"""

import asyncio

import httpx

from app.main import app

PASSWORD = "Demo1234!"
FIRMA = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
FIRMA2 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="


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

        # ── firma inicialmente vacía ──
        r = await client.get("/medico/mi-firma", headers=medico)
        results.append(("firma inicialmente vacía", r.status_code == 200 and r.json()["firma"] is None))

        # ── guardar firma ──
        r = await client.put("/medico/mi-firma", headers=medico, json={"firma": FIRMA})
        results.append(("guardar firma -> 200", r.status_code == 200 and r.json()["firma"] == FIRMA))
        r = await client.get("/medico/mi-firma", headers=medico)
        results.append(("firma persistida", r.json()["firma"] == FIRMA))

        # ── emitir documento: queda estampada la firma ──
        cita = next((c for c in (await client.get("/medico/agenda", headers=medico)).json() if "Camila" in c["paciente_nombre"]), None)
        pid = cita["patient_id"]
        r = await client.post(f"/medico/pacientes/{pid}/documentos", headers=medico, json={
            "tipo": "certificado", "titulo": "Certificado (con firma)", "contenido": "Asistió hoy.",
        })
        doc = r.json()
        results.append(("documento estampa la firma del profesional", r.status_code == 201 and doc["firma_profesional"] == FIRMA))

        # ── cambiar la firma NO altera el documento ya emitido (instantánea) ──
        await client.put("/medico/mi-firma", headers=medico, json={"firma": FIRMA2})
        docs = (await client.get(f"/medico/pacientes/{pid}/documentos", headers=medico)).json()
        emitido = next((d for d in docs if d["id"] == doc["id"]), None)
        results.append(("firma del documento es inmutable tras cambiarla", emitido is not None and emitido["firma_profesional"] == FIRMA))

        # ── un nuevo documento usa la firma nueva ──
        r = await client.post(f"/medico/pacientes/{pid}/documentos", headers=medico, json={
            "tipo": "certificado", "titulo": "Segundo certificado", "contenido": "Segundo.",
        })
        results.append(("documento nuevo usa la firma actualizada", r.json()["firma_profesional"] == FIRMA2))

        # ── borrar la firma (null) ──
        r = await client.put("/medico/mi-firma", headers=medico, json={"firma": None})
        results.append(("borrar firma -> null", r.status_code == 200 and r.json()["firma"] is None))

        # ── RBAC: el paciente no accede a mi-firma ──
        r = await client.get("/medico/mi-firma", headers=paciente)
        results.append(("paciente no accede a /medico/mi-firma", r.status_code in (401, 403)))

    print("\n=== Firma del profesional (48) · smoke ===")
    ok = True
    for name, passed in results:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
        ok = ok and passed
    print("=== OK ===" if ok else "=== FALLÓ ===")
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
