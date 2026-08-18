"""Smoke test de entidades financieras: bancos e Isapres/Fonasa (63).

CRUD del catálogo por clínica, filtro por tipo, y RBAC.

Run: `python -m tests.test_entidades_smoke`.
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

        rb = await client.post("/empresa/entidades-financieras", headers=emp, json={"nombre": "Banco Estado", "tipo": "banco"})
        check("Banco: alta -> 201", rb.status_code == 201 and rb.json().get("tipo") == "banco")
        banco_id = rb.json()["id"]
        ri = await client.post("/empresa/entidades-financieras", headers=emp, json={"nombre": "Fonasa", "tipo": "isapre"})
        check("Isapre: alta -> 201", ri.status_code == 201 and ri.json().get("tipo") == "isapre")
        isapre_id = ri.json()["id"]

        bad = await client.post("/empresa/entidades-financieras", headers=emp, json={"nombre": "X", "tipo": "cooperativa"})
        check("Tipo inválido -> 422", bad.status_code == 422)

        todos = (await client.get("/empresa/entidades-financieras", headers=emp)).json()
        check("Listado: incluye banco e isapre", any(x["id"] == banco_id for x in todos) and any(x["id"] == isapre_id for x in todos))

        solo_isapre = (await client.get("/empresa/entidades-financieras?tipo=isapre", headers=emp)).json()
        check("Filtro tipo=isapre: solo isapres", all(x["tipo"] == "isapre" for x in solo_isapre) and any(x["id"] == isapre_id for x in solo_isapre))

        re = await client.patch(f"/empresa/entidades-financieras/{banco_id}", headers=emp, json={"activo": False})
        check("Deshabilitar banco -> 200", re.status_code == 200 and re.json().get("activo") is False)

        rd = await client.delete(f"/empresa/entidades-financieras/{isapre_id}", headers=emp)
        check("Baja isapre -> 204", rd.status_code == 204)
        todos2 = (await client.get("/empresa/entidades-financieras", headers=emp)).json()
        check("Isapre ya no aparece tras la baja", not any(x["id"] == isapre_id for x in todos2))

        med = await login(client, "medico.a@todoscare.dev")
        r403 = await client.post("/empresa/entidades-financieras", headers=med, json={"nombre": "X", "tipo": "banco"})
        check("RBAC: médico NO administra entidades -> 403", r403.status_code == 403)

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
