"""Smoke test · Paciente descarga su ficha (72.2).

El paciente exporta su ficha consolidada desde su propio login: datos, previsión,
exámenes y documentos, con RBAC.

Run: `python -m tests.test_descargar_ficha_smoke`.
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
        pac = await login(client, "paciente.a@todoscare.dev")
        empresa = await login(client, "empresa.a@todoscare.dev")

        # ── exportar la ficha ──
        r = await client.get("/salud/ficha", headers=pac)
        f = r.json()
        results.append(("exportar ficha -> 200", r.status_code == 200))
        results.append(("trae nombre y RUT del paciente", bool(f["nombre"]) and bool(f["rut"])))
        results.append(("incluye clínica y fecha de generación", f["clinica"] and f["generado"]))
        results.append(("trae listas de exámenes y documentos", isinstance(f["examenes"], list) and isinstance(f["documentos"], list)))
        results.append(("incluye bloque de previsión/GES", "prevision" in f and "ges" in f))

        # ── un examen subido aparece en la exportación ──
        await client.post("/salud/examenes/subir", headers=pac, files={"file": ("mi_hemograma.pdf", b"%PDF demo", "application/pdf")})
        r = await client.get("/salud/ficha", headers=pac)
        results.append(("el examen subido aparece en la ficha exportada", any("hemograma" in (e["nombre"] or "").lower() for e in r.json()["examenes"])))

        # ── RBAC: la empresa no usa el endpoint del paciente ──
        r = await client.get("/salud/ficha", headers=empresa)
        results.append(("la empresa no accede a /salud/ficha", r.status_code in (401, 403)))

    print("\n=== Descargar mi ficha (72.2) · smoke ===")
    ok = True
    for name, passed in results:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
        ok = ok and passed
    print("=== OK ===" if ok else "=== FALLÓ ===")
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
