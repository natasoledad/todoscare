"""Smoke test de inventario · movimientos (56.9 · 56.11).

Lotes con vencimiento, entradas/salidas con kardex FEFO (primero el lote que
vence antes), ajustes, semáforo de stock y alertas de reposición/vencimiento.

Run: `python -m tests.test_inventario_movimientos_smoke`.
"""

import asyncio
from datetime import date, timedelta

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
        base = "/empresa/inventario"

        branch = (await client.get("/empresa/sucursales", headers=emp)).json()[0]
        bod = (await client.post(f"{base}/bodegas", headers=emp, json={"nombre": "Bodega Central", "branch_id": branch["id"]})).json()
        item = (await client.post(f"{base}/items", headers=emp, json={"nombre": "Anestesia", "sku": "AN-1", "unidad": "ampolla", "stock_minimo": 10})).json()
        iid = item["id"]

        # ítem recién creado: sin stock -> semáforo sin_stock
        it0 = next(i for i in (await client.get(f"{base}/items", headers=emp)).json() if i["id"] == iid)
        check("Ítem nuevo: stock 0 y estado sin_stock", it0["stock_actual"] == 0 and it0["estado"] == "sin_stock")

        hoy = date.today()
        venc_lejos = (hoy + timedelta(days=200)).isoformat()
        venc_pronto = (hoy + timedelta(days=10)).isoformat()

        # entrada lote que vence PRONTO (10 unidades) y lote que vence LEJOS (5)
        await client.post(f"{base}/items/{iid}/entrada", headers=emp, json={"warehouse_id": bod["id"], "cantidad": 10, "lote": "L-PRONTO", "vencimiento": venc_pronto})
        r = await client.post(f"{base}/items/{iid}/entrada", headers=emp, json={"warehouse_id": bod["id"], "cantidad": 5, "lote": "L-LEJOS", "vencimiento": venc_lejos})
        check("Entradas -> 201", r.status_code == 201)
        it = r.json()
        check("Stock 15 tras entradas, estado ok", it["stock_actual"] == 15 and it["estado"] == "ok")

        # salida de 12 -> FEFO consume primero L-PRONTO (10) y luego 2 de L-LEJOS
        r = await client.post(f"{base}/items/{iid}/salida", headers=emp, json={"warehouse_id": bod["id"], "cantidad": 12, "motivo": "Consumo box 1"})
        check("Salida -> 201, stock 3, estado bajo (min 10)", r.status_code == 201 and r.json()["stock_actual"] == 3 and r.json()["estado"] == "bajo")

        lotes = (await client.get(f"{base}/items/{iid}/lotes", headers=emp)).json()
        l_pronto = next(l for l in lotes if l["lote"] == "L-PRONTO")
        l_lejos = next(l for l in lotes if l["lote"] == "L-LEJOS")
        check("FEFO: L-PRONTO quedó en 0", l_pronto["cantidad"] == 0)
        check("FEFO: L-LEJOS quedó en 3", l_lejos["cantidad"] == 3)
        check("Lote que vence en 10 días marcado por_vencer", l_pronto["estado"] == "por_vencer")

        # salida imposible -> 400
        r = await client.post(f"{base}/items/{iid}/salida", headers=emp, json={"warehouse_id": bod["id"], "cantidad": 999})
        check("Salida mayor al stock -> 400", r.status_code == 400)

        # ajuste del lote L-LEJOS de 3 -> 8
        r = await client.post(f"{base}/items/{iid}/ajuste", headers=emp, json={"lot_id": l_lejos["id"], "cantidad_nueva": 8, "motivo": "Conteo físico"})
        check("Ajuste -> 201, stock 8", r.status_code == 201 and r.json()["stock_actual"] == 8)

        # kardex: entrada, entrada, salida, ajuste (4 movimientos), en orden inverso
        mov = (await client.get(f"{base}/items/{iid}/movimientos", headers=emp)).json()
        check("Kardex tiene 4 movimientos", len(mov) == 4)
        check("Último movimiento es el ajuste (+5) con saldo 8", mov[0]["tipo"] == "ajuste" and mov[0]["cantidad"] == 5 and mov[0]["saldo"] == 8)
        check("La salida quedó con cantidad negativa (-12)", any(m["tipo"] == "salida" and m["cantidad"] == -12 for m in mov))

        # stock por bodega
        st = (await client.get(f"{base}/items/{iid}/stock", headers=emp)).json()
        check("Stock por bodega suma 8", sum(b["cantidad"] for b in st["por_bodega"]) == 8 and st["estado"] == "bajo")

        # nuevo lote CON stock que vence pronto -> debe disparar la alerta de vencimiento.
        # subimos el mínimo a 15 para que el ítem siga bajo mínimo (stock pasa a 12).
        await client.post(f"{base}/items/{iid}/entrada", headers=emp, json={"warehouse_id": bod["id"], "cantidad": 4, "lote": "L-PRONTO2", "vencimiento": venc_pronto})
        await client.patch(f"{base}/items/{iid}", headers=emp, json={"stock_minimo": 15})

        # alertas: el ítem está bajo mínimo (12 < 15); L-PRONTO2 (con stock) por vencer
        al = (await client.get(f"{base}/alertas", headers=emp)).json()
        check("Alertas: ítem aparece bajo mínimo", any(i["id"] == iid for i in al["bajo_minimo"]))
        check("Alertas: L-PRONTO2 (con stock) por vencer", any(l["lote"] == "L-PRONTO2" for l in al["lotes_por_vencer"]))
        check("Alertas: no lista lotes vacíos como por vencer", all(l["cantidad"] > 0 for l in al["lotes_por_vencer"]))

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
