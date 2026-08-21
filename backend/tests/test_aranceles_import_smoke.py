"""Smoke test · Carga masiva de aranceles por Excel/CSV (62.8).

Importa prestaciones desde CSV (con encabezado, autodetección de separador,
formato de precio chileno), autocreando categorías, con upsert por código,
manejo de errores por fila y RBAC.

Run: `python -m tests.test_aranceles_import_smoke`.
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
        empresa = await login(client, "empresa.a@todoscare.dev")
        medico = await login(client, "medico.a@todoscare.dev")

        # arancel donde importar
        r = await client.post("/empresa/aranceles", headers=empresa, json={"nombre": "Importado", "tipo": "particular"})
        aid = r.json()["id"]

        csv = (
            "codigo,nombre,precio,categoria,precio_referencia\n"
            "CB01,Consulta general,25.000,Consultas,20000\n"
            "CB02,Limpieza dental,35000,Odontología,\n"
            ",Radiografía panorámica,15.500,Imágenes,\n"
            "CB03,Corona,\"12.345,50\",Rehabilitación,\n"
            "CBX,Fila mala,abc,Consultas,\n"
        )
        r = await client.post(f"/empresa/aranceles/{aid}/importar", headers=empresa, json={"contenido": csv})
        out = r.json()
        results.append(("importar -> 200", r.status_code == 200))
        results.append(("4 prestaciones creadas", out["creados"] == 4))
        results.append(("1 fila con error (precio inválido)", len(out["errores"]) == 1 and out["errores"][0]["fila"] == 6))

        r = await client.get(f"/empresa/aranceles/{aid}/items", headers=empresa)
        items = r.json()
        results.append(("las prestaciones quedan en el arancel", len(items) == 4))
        corona = next((i for i in items if i["codigo"] == "CB03"), None)
        results.append(("precio chileno '12.345,50' -> 12345.5", corona is not None and corona["precio"] == 12345.5))
        cb01 = next((i for i in items if i["codigo"] == "CB01"), None)
        results.append(("precio '25.000' -> 25000", cb01 is not None and cb01["precio"] == 25000))

        # categorías autocreadas
        r = await client.get(f"/empresa/aranceles/{aid}/categorias", headers=empresa)
        results.append(("categorías autocreadas", any(c["nombre"] == "Odontología" for c in r.json())))

        # ── upsert: reimportar CB01 con nuevo precio ──
        r = await client.post(f"/empresa/aranceles/{aid}/importar", headers=empresa, json={"contenido": "codigo,nombre,precio\nCB01,Consulta general,30000\n"})
        results.append(("reimportar CB01 -> actualizado (no duplica)", r.json()["actualizados"] == 1 and r.json()["creados"] == 0))
        r = await client.get(f"/empresa/aranceles/{aid}/items", headers=empresa)
        cb01 = next((i for i in r.json() if i["codigo"] == "CB01"), None)
        results.append(("CB01 actualizado a 30000", cb01["precio"] == 30000 and len([i for i in r.json() if i["codigo"] == "CB01"]) == 1))

        # ── separador ';' autodetectado ──
        r = await client.post(f"/empresa/aranceles/{aid}/importar", headers=empresa, json={"contenido": "codigo;nombre;precio\nCB09;Sellante;8000\n"})
        results.append(("separador ';' autodetectado", r.json()["creados"] == 1))

        # ── RBAC ──
        r = await client.post(f"/empresa/aranceles/{aid}/importar", headers=medico, json={"contenido": "nombre,precio\nX,1000\n"})
        results.append(("médico no importa aranceles", r.status_code in (401, 403)))

    print("\n=== Carga masiva de aranceles (62.8) · smoke ===")
    ok = True
    for name, passed in results:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
        ok = ok and passed
    print("=== OK ===" if ok else "=== FALLÓ ===")
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
