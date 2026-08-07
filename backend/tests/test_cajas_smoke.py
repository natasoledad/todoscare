"""Tanda 2 smoke test: Módulo de Cajas contra el app real + Postgres real.

Cubre: abrir caja (una sola abierta por usuario), registrar pagos por medio de
pago y gastos, totales y desglose, el ledger inmutable ('cobro'/'egreso') por
cada movimiento, el enlace pago→cita que marca la cita 'pagada' en la agenda de
gerencia (Tanda 1), aislamiento por rol, y cierre de caja.
Run: `python -m tests.test_cajas_smoke`.
"""

import asyncio
from datetime import datetime, timezone

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
    today = datetime.now(timezone.utc).date().isoformat()

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        empresa = await login(client, "empresa.a@todoscare.dev")
        medico = await login(client, "medico.a@todoscare.dev")

        # cita de Camila (para ligar un pago)
        r = await client.get(f"/empresa/agenda?fecha={today}", headers=empresa)
        cita = next((c for c in r.json()["citas"] if "Camila" in c["paciente_nombre"]), None)
        results.append(("hay una cita para ligar el pago", cita is not None))

        # ---- abrir caja ----
        r = await client.get("/empresa/cajas/mi-caja", headers=empresa)
        results.append(("sin caja abierta al inicio -> null", r.status_code == 200 and r.json() is None))

        r = await client.post("/empresa/cajas", headers=empresa, json={"abono_inicial": 10000})
        results.append(("abrir caja -> 201 abierta", r.status_code == 201 and r.json()["estado"] == "abierta"))
        caja = r.json()
        caja_id = caja["id"]
        results.append(("total inicial = abono_inicial (10000)", abs(caja["total"] - 10000) < 0.01))

        r = await client.post("/empresa/cajas", headers=empresa, json={"abono_inicial": 0})
        results.append(("no se puede abrir una segunda caja -> 409", r.status_code == 409))

        r = await client.get("/empresa/cajas/mi-caja", headers=empresa)
        results.append(("mi-caja devuelve la caja abierta", r.status_code == 200 and r.json() and r.json()["id"] == caja_id))

        # ---- registrar movimientos ----
        r = await client.post(
            f"/empresa/cajas/{caja_id}/movimientos", headers=empresa,
            json={"tipo": "pago", "medio": "efectivo", "monto": 30000, "convenio": "Particular",
                  "patient_id": cita["paciente_id"], "appointment_id": cita["id"], "boleta": "1001"},
        )
        results.append(("registrar pago efectivo (ligado a cita) -> 201", r.status_code == 201 and r.json()["medio"] == "efectivo"))

        r = await client.post(
            f"/empresa/cajas/{caja_id}/movimientos", headers=empresa,
            json={"tipo": "pago", "medio": "debito", "monto": 20000, "convenio": "Fonasa", "boleta": "1002"},
        )
        results.append(("registrar pago débito -> 201", r.status_code == 201))

        r = await client.post(
            f"/empresa/cajas/{caja_id}/movimientos", headers=empresa,
            json={"tipo": "gasto", "medio": "efectivo", "monto": 5000, "glosa": "Insumos"},
        )
        results.append(("registrar gasto -> 201", r.status_code == 201))

        # medio inválido
        r = await client.post(f"/empresa/cajas/{caja_id}/movimientos", headers=empresa, json={"tipo": "pago", "medio": "bitcoin", "monto": 1})
        results.append(("medio de pago inválido -> 400", r.status_code == 400))

        # ---- totales y desglose ----
        r = await client.get(f"/empresa/cajas/{caja_id}", headers=empresa)
        det = r.json()
        results.append(("recaudado = 50000", abs(det["recaudado"] - 50000) < 0.01))
        results.append(("gastos = 5000", abs(det["gastos"] - 5000) < 0.01))
        results.append(("total = 10000 + 50000 - 5000 = 55000", abs(det["total"] - 55000) < 0.01))
        results.append(("desglose efectivo = 30000", abs(det["por_medio"].get("efectivo", 0) - 30000) < 0.01))
        results.append(("desglose débito = 20000", abs(det["por_medio"].get("debito", 0) - 20000) < 0.01))
        results.append(("3 transacciones registradas", len(det["transacciones"]) == 3))

        # ---- conexión con la agenda (Tanda 1): la cita queda 'pagada' ----
        r = await client.get(f"/empresa/agenda?fecha={today}", headers=empresa)
        cita2 = next((c for c in r.json()["citas"] if c["id"] == cita["id"]), None)
        results.append(("la cita ligada aparece 'pagada' en la agenda", bool(cita2 and cita2["pagado"] is True)))

        # ---- aislamiento por rol: el médico no opera caja ----
        r = await client.post("/empresa/cajas", headers=medico, json={"abono_inicial": 0})
        results.append(("médico NO abre caja -> 403", r.status_code == 403))

        # ---- cerrar caja ----
        r = await client.post(f"/empresa/cajas/{caja_id}/cerrar", headers=empresa, json={"fondo_fijo": 8000})
        results.append(("cerrar caja -> 200 cerrada", r.status_code == 200 and r.json()["estado"] == "cerrada"))
        results.append(("fondo fijo guardado = 8000", abs((r.json()["fondo_fijo"] or 0) - 8000) < 0.01))

        # ya cerrada: no admite movimientos
        r = await client.post(f"/empresa/cajas/{caja_id}/movimientos", headers=empresa, json={"tipo": "pago", "medio": "efectivo", "monto": 100})
        results.append(("caja cerrada: no admite movimientos -> 400", r.status_code == 400))

        # aparece en cerradas y ya no hay caja abierta
        r = await client.get("/empresa/cajas?estado=cerrada", headers=empresa)
        results.append(("la caja aparece en 'cerradas'", any(c["id"] == caja_id for c in r.json())))
        r = await client.get("/empresa/cajas/mi-caja", headers=empresa)
        results.append(("tras cerrar, mi-caja vuelve a null", r.status_code == 200 and r.json() is None))

    print()
    failed = 0
    for name, ok in results:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
        failed += 0 if ok else 1
    print()
    if failed:
        print(f"{failed} check(s) FAILED")
        raise SystemExit(1)
    print(f"All {len(results)} checks passed.")


if __name__ == "__main__":
    asyncio.run(main())
