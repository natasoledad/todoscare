"""Smoke test del inventario base (56.2 · 56.7 · 56.14 · 56.16).

Catálogos de inventario para la empresa: proveedores, centros de costo,
bodegas por sucursal e ítems de insumo con stock mínimo. CRUD + RBAC.

Run: `python -m tests.test_inventario_base_smoke`.
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

        # ── proveedor ──
        r = await client.post("/empresa/inventario/proveedores", headers=emp, json={"nombre": "Dental Supply SpA", "rut": "76.111.222-3", "contacto": "ventas@dentalsupply.cl"})
        check("Crear proveedor -> 201", r.status_code == 201)
        prov = r.json()
        r = await client.get("/empresa/inventario/proveedores", headers=emp)
        check("Proveedor listado", any(p["id"] == prov["id"] for p in r.json()))
        r = await client.patch(f"/empresa/inventario/proveedores/{prov['id']}", headers=emp, json={"contacto": "nuevo@dentalsupply.cl"})
        check("Editar proveedor -> 200", r.status_code == 200 and r.json()["contacto"] == "nuevo@dentalsupply.cl")

        # ── centro de costo ──
        r = await client.post("/empresa/inventario/centros-costo", headers=emp, json={"nombre": "Esterilización"})
        check("Crear centro de costo -> 201", r.status_code == 201)
        cc = r.json()

        # ── bodega (con sucursal) ──
        branch = (await client.get("/empresa/sucursales", headers=emp)).json()[0]
        r = await client.post("/empresa/inventario/bodegas", headers=emp, json={"nombre": "Bodega Central", "branch_id": branch["id"]})
        check("Crear bodega -> 201 con sucursal", r.status_code == 201 and r.json()["branch_nombre"] == branch["nombre"])
        bod = r.json()
        r = await client.post("/empresa/inventario/bodegas", headers=emp, json={"nombre": "Bodega inválida", "branch_id": "00000000-0000-0000-0000-000000000000"})
        check("Bodega con sucursal inválida -> 400", r.status_code == 400)

        # ── ítem de insumo con stock mínimo, proveedor y centro de costo ──
        r = await client.post("/empresa/inventario/items", headers=emp, json={
            "nombre": "Guantes de nitrilo M", "sku": "GN-M", "unidad": "caja",
            "stock_minimo": 5, "supplier_id": prov["id"], "cost_center_id": cc["id"],
        })
        check("Crear ítem -> 201", r.status_code == 201)
        item = r.json()
        check("Ítem resuelve proveedor y centro de costo", item["supplier_nombre"] == "Dental Supply SpA" and item["cost_center_nombre"] == "Esterilización")
        check("Ítem trae stock mínimo", item["stock_minimo"] == 5)

        # SKU duplicado -> 409
        r = await client.post("/empresa/inventario/items", headers=emp, json={"nombre": "Otro", "sku": "GN-M"})
        check("SKU duplicado -> 409", r.status_code == 409)

        # editar stock mínimo
        r = await client.patch(f"/empresa/inventario/items/{item['id']}", headers=emp, json={"stock_minimo": 10})
        check("Editar stock mínimo -> 10", r.status_code == 200 and r.json()["stock_minimo"] == 10)

        # ── RBAC: el médico no gestiona inventario ──
        r = await client.get("/empresa/inventario/items", headers=medico)
        check("Médico NO ve inventario -> 403", r.status_code == 403)
        r = await client.post("/empresa/inventario/proveedores", headers=medico, json={"nombre": "x"})
        check("Médico NO crea proveedor -> 403", r.status_code == 403)

        # ── baja de proveedor ──
        r = await client.delete(f"/empresa/inventario/proveedores/{prov['id']}", headers=emp)
        check("Eliminar proveedor -> 204", r.status_code == 204)
        r = await client.get("/empresa/inventario/proveedores", headers=emp)
        check("Proveedor ya no listado tras baja", all(p["id"] != prov["id"] for p in r.json()))

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
