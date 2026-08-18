"""Smoke test de anulación auditada de pagos de caja (67.1/67.2).

Contra la BD seedeada con `app.seed`, en el portal Empresa:
  · Anular un pago lo saca de los totales/detalle de la caja pero NO lo borra.
  · Queda con traza (quién, cuándo, motivo) y un reverso en el ledger.
  · Aparece en el listado de anulados. Reanular -> 409.

Run: `python -m tests.test_anulacion_smoke`.
"""

import asyncio

import httpx
from sqlalchemy import func, select

from app.core.database import AsyncSessionLocal
from app.main import app
from app.models.finance import LedgerEntry
from app.models.tenant import Clinic

PASSWORD = "Demo1234!"


async def login(client: httpx.AsyncClient, email: str) -> dict:
    r = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def main() -> None:
    results: list[tuple[str, bool]] = []

    def check(name: str, ok: bool) -> None:
        results.append((name, ok))

    async with AsyncSessionLocal() as db:
        clinic_id = (await db.execute(select(Clinic).where(Clinic.razon_social == "Clínica Demo A"))).scalar_one().id

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        emp = await login(client, "empresa.a@todoscare.dev")

        # abrir caja + registrar un pago
        caja = (await client.post("/empresa/cajas", headers=emp, json={"abono_inicial": 10000})).json()
        caja_id = caja["id"]
        mov = await client.post(f"/empresa/cajas/{caja_id}/movimientos", headers=emp, json={"tipo": "pago", "medio": "efectivo", "monto": 5000})
        check("Pago: registrado -> 201", mov.status_code == 201)
        mov_id = mov.json()["id"]

        det = (await client.get(f"/empresa/cajas/{caja_id}", headers=emp)).json()
        check("Caja: recaudado 5000 antes de anular", abs(det["recaudado"] - 5000) < 0.01 and any(t["id"] == mov_id for t in det["transacciones"]))

        # anular
        an = await client.post(f"/empresa/cajas/pagos/{mov_id}/anular", headers=emp, json={"motivo": "cobro duplicado"})
        check("Anular -> 200 con traza", an.status_code == 200 and an.json().get("anulado_por") and an.json().get("anulado_at") and an.json().get("motivo") == "cobro duplicado")

        det2 = (await client.get(f"/empresa/cajas/{caja_id}", headers=emp)).json()
        check("Caja: recaudado 0 tras anular (sale de totales)", abs(det2["recaudado"]) < 0.01)
        check("Caja: el pago ya no está en el detalle", not any(t["id"] == mov_id for t in det2["transacciones"]))

        anulados = (await client.get("/empresa/cajas/pagos/anulados", headers=emp)).json()
        me = next((x for x in anulados if x["id"] == mov_id), None)
        check("Anulados: aparece con motivo y quién anuló", me is not None and me["motivo"] == "cobro duplicado" and me["anulado_por"])

        re = await client.post(f"/empresa/cajas/pagos/{mov_id}/anular", headers=emp, json={"motivo": "otra vez"})
        check("Reanular -> 409", re.status_code == 409)

    # ledger: reverso asentado
    async with AsyncSessionLocal() as db:
        n = (
            await db.execute(
                select(func.count()).select_from(LedgerEntry).where(
                    LedgerEntry.clinic_id == clinic_id, LedgerEntry.tipo == "cobro_anulado"
                )
            )
        ).scalar_one()
        check("Ledger: reverso (cobro_anulado) asentado", n >= 1)

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
