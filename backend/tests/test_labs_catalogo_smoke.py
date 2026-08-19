"""Smoke test del catálogo de laboratorios dentales (57.1 · 57.3b).

Laboratorios y sus prestaciones con costo (lo que se paga al lab) vs precio
(lo que se cobra al paciente). CRUD + RBAC.

Run: `python -m tests.test_labs_catalogo_smoke`.
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

        # ── laboratorio ──
        r = await client.post("/empresa/labs", headers=emp, json={"nombre": "Laboratorio Dental Sur", "rut": "77.888.999-0", "contacto": "trabajos@labsur.cl"})
        check("Crear laboratorio -> 201", r.status_code == 201)
        lab = r.json()
        r = await client.get("/empresa/labs", headers=emp)
        check("Laboratorio listado", any(x["id"] == lab["id"] for x in r.json()))
        r = await client.patch(f"/empresa/labs/{lab['id']}", headers=emp, json={"contacto": "ordenes@labsur.cl"})
        check("Editar laboratorio -> 200", r.status_code == 200 and r.json()["contacto"] == "ordenes@labsur.cl")

        # ── prestación con costo vs precio ──
        r = await client.post(f"/empresa/labs/{lab['id']}/servicios", headers=emp, json={"nombre": "Corona de circonio", "costo": 45000, "precio": 120000})
        check("Crear prestación -> 201", r.status_code == 201)
        svc = r.json()
        check("Margen calculado (precio - costo = 75000)", svc["margen"] == 75000)

        r = await client.get(f"/empresa/labs/{lab['id']}/servicios", headers=emp)
        check("Prestación listada bajo su lab", any(s["id"] == svc["id"] for s in r.json()))

        r = await client.patch(f"/empresa/labs/servicios/{svc['id']}", headers=emp, json={"costo": 50000})
        check("Editar costo -> margen recalculado 70000", r.status_code == 200 and r.json()["margen"] == 70000)

        # servicio en un lab inexistente -> 404
        r = await client.post("/empresa/labs/00000000-0000-0000-0000-000000000000/servicios", headers=emp, json={"nombre": "x"})
        check("Prestación en lab inexistente -> 404", r.status_code == 404)

        # ── RBAC: el médico no gestiona el catálogo de labs ──
        r = await client.get("/empresa/labs", headers=medico)
        check("Médico NO ve el catálogo de labs -> 403", r.status_code == 403)
        r = await client.post("/empresa/labs", headers=medico, json={"nombre": "x"})
        check("Médico NO crea labs -> 403", r.status_code == 403)

        # ── baja de prestación y de lab ──
        r = await client.delete(f"/empresa/labs/servicios/{svc['id']}", headers=emp)
        check("Eliminar prestación -> 204", r.status_code == 204)
        r = await client.get(f"/empresa/labs/{lab['id']}/servicios", headers=emp)
        check("Prestación ya no listada", all(s["id"] != svc["id"] for s in r.json()))
        r = await client.delete(f"/empresa/labs/{lab['id']}", headers=emp)
        check("Eliminar laboratorio -> 204", r.status_code == 204)

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
