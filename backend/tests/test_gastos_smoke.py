"""Smoke test del reporte de gastos por período (54.11).

Contra la BD seedeada con `app.seed`: los movimientos de caja tipo 'gasto' se
consolidan en un reporte con total; los pagos no cuentan.

Run: `python -m tests.test_gastos_smoke`.
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
        caja = (await client.post("/empresa/cajas", headers=emp, json={"abono_inicial": 10000})).json()
        cid = caja["id"]
        await client.post(f"/empresa/cajas/{cid}/movimientos", headers=emp, json={"tipo": "gasto", "medio": "efectivo", "monto": 3000, "glosa": "Insumos"})
        await client.post(f"/empresa/cajas/{cid}/movimientos", headers=emp, json={"tipo": "gasto", "medio": "efectivo", "monto": 2000, "glosa": "Aseo"})
        await client.post(f"/empresa/cajas/{cid}/movimientos", headers=emp, json={"tipo": "pago", "medio": "efectivo", "monto": 9000})

        rep = await client.get("/empresa/cajas/reportes/gastos", headers=emp)
        check("Reporte gastos -> 200", rep.status_code == 200)
        d = rep.json() if rep.status_code == 200 else {}
        check("Total 5000 y 2 gastos (el pago no cuenta)", abs(d.get("total", 0) - 5000) < 0.01 and d.get("cantidad") == 2)
        check("Trae glosa y responsable", all(g.get("glosa") for g in d.get("gastos", [])) and all("caja_responsable" in g for g in d.get("gastos", [])))

        med = await login(client, "medico.a@todoscare.dev")
        r403 = await client.get("/empresa/cajas/reportes/gastos", headers=med)
        check("RBAC: médico NO ve gastos de la clínica -> 403", r403.status_code == 403)

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
