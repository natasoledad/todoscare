"""Smoke test de aranceles multi-tabla (62).

Contra la BD seedeada con `app.seed`, en el portal Empresa:
  · CRUD de arancel, categoría y prestación (código, precio, referencial, flags).
  · Incremento porcentual de precios (62.9).
  · Copiar del arancel base a otro arancel, idempotente por código (62.15).
  · es_base es exclusivo por clínica. RBAC: un médico no accede.

Run: `python -m tests.test_aranceles_smoke`.
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

        # ── aranceles base + particular ──
        rb = await client.post("/empresa/aranceles", headers=emp, json={"nombre": "Arancel Base", "tipo": "base", "es_base": True})
        check("Arancel base -> 201, es_base", rb.status_code == 201 and rb.json().get("es_base") is True)
        base_id = rb.json()["id"]
        rp = await client.post("/empresa/aranceles", headers=emp, json={"nombre": "Particular", "tipo": "particular"})
        check("Arancel particular -> 201", rp.status_code == 201)
        part_id = rp.json()["id"]

        # ── categoría + ítems en el base ──
        rc = await client.post(f"/empresa/aranceles/{base_id}/categorias", headers=emp, json={"nombre": "Cirugía", "orden": 1})
        check("Categoría -> 201", rc.status_code == 201)
        cat_id = rc.json()["id"]
        i1 = await client.post(f"/empresa/aranceles/{base_id}/items", headers=emp, json={"categoria_id": cat_id, "codigo": "CB01", "nombre": "Exodoncia", "precio": 10000})
        check("Ítem CB01 -> 201 con categoría", i1.status_code == 201 and i1.json().get("categoria_nombre") == "Cirugía")
        item_id = i1.json()["id"]
        await client.post(f"/empresa/aranceles/{base_id}/items", headers=emp, json={"categoria_id": cat_id, "codigo": "CB02", "nombre": "Colgajo", "precio": 20000})

        items_base = (await client.get(f"/empresa/aranceles/{base_id}/items", headers=emp)).json()
        check("Base tiene 2 ítems", len(items_base) == 2)

        # ── incremento de precios +10% ──
        inc = await client.post(f"/empresa/aranceles/{base_id}/incrementar", headers=emp, json={"pct": 0.10})
        check("Incrementar +10% -> afectados 2", inc.status_code == 200 and inc.json().get("afectados") == 2)
        items_base2 = {i["codigo"]: i["precio"] for i in (await client.get(f"/empresa/aranceles/{base_id}/items", headers=emp)).json()}
        check("Precios subieron 10% (CB01=11000, CB02=22000)", abs(items_base2["CB01"] - 11000) < 0.01 and abs(items_base2["CB02"] - 22000) < 0.01)

        # ── copiar del base al particular ──
        cp = await client.post(f"/empresa/aranceles/{part_id}/copiar-base", headers=emp, json={})
        check("Copiar base -> copiados 2", cp.status_code == 200 and cp.json().get("copiados") == 2)
        items_part = (await client.get(f"/empresa/aranceles/{part_id}/items", headers=emp)).json()
        check("Particular quedó con 2 ítems y categoría copiada", len(items_part) == 2 and all(x["categoria_nombre"] == "Cirugía" for x in items_part))
        cp2 = await client.post(f"/empresa/aranceles/{part_id}/copiar-base", headers=emp, json={})
        check("Copiar de nuevo -> 0 (idempotente por código)", cp2.json().get("copiados") == 0)
        cpb = await client.post(f"/empresa/aranceles/{base_id}/copiar-base", headers=emp, json={})
        check("Copiar base sobre sí mismo -> 400", cpb.status_code == 400)

        # ── edición y baja de ítem ──
        re = await client.patch(f"/empresa/aranceles/items/{item_id}", headers=emp, json={"precio": 5000, "permite_descuento": False})
        check("Editar ítem -> 200", re.status_code == 200 and abs(re.json()["precio"] - 5000) < 0.01 and re.json()["permite_descuento"] is False)
        rd = await client.delete(f"/empresa/aranceles/items/{item_id}", headers=emp)
        check("Baja de ítem -> 204", rd.status_code == 204)
        check("Base quedó con 1 ítem", len((await client.get(f"/empresa/aranceles/{base_id}/items", headers=emp)).json()) == 1)

        # ── es_base exclusivo ──
        r3 = await client.post("/empresa/aranceles", headers=emp, json={"nombre": "Nuevo Base", "tipo": "base", "es_base": True})
        base2_id = r3.json()["id"]
        aranceles = {a["id"]: a["es_base"] for a in (await client.get("/empresa/aranceles", headers=emp)).json()}
        check("es_base exclusivo: el base anterior se desmarcó", aranceles.get(base_id) is False and aranceles.get(base2_id) is True)

        # ── baja de arancel ──
        check("Baja de arancel -> 204", (await client.delete(f"/empresa/aranceles/{part_id}", headers=emp)).status_code == 204)

        # ── RBAC ──
        med = await login(client, "medico.a@todoscare.dev")
        check("RBAC: médico NO accede a aranceles -> 403", (await client.get("/empresa/aranceles", headers=med)).status_code == 403)

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
