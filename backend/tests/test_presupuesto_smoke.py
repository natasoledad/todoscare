"""Smoke test · Presupuesto imprimible + financiamiento en cuotas (69.11 · 69.19).

Genera cuotas sobre el total neto del plan, marca pagos, arma el presupuesto
imprimible y valida rangos y RBAC.

Run: `python -m tests.test_presupuesto_smoke`.
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
    transport = httpx.ASGITransport(app=app)
    results: list[tuple[str, bool]] = []

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        medico = await login(client, "medico.a@todoscare.dev")
        paciente = await login(client, "paciente.a@todoscare.dev")

        cita = next((c for c in (await client.get("/medico/agenda", headers=medico)).json() if "Camila" in c["paciente_nombre"]), None)
        pid = cita["patient_id"]

        # ── plan con total bruto 100.000 y 10% de descuento => neto 90.000 ──
        r = await client.post(f"/medico/pacientes/{pid}/planes", headers=medico, json={
            "titulo": "Rehabilitación", "items": [{"descripcion": "Corona", "cantidad": 2, "precio_unit": 50000}],
        })
        plan = r.json()
        plan_id = plan["id"]
        await client.patch(f"/medico/planes/{plan_id}", headers=medico, json={"descuento_pct": 0.10})
        results.append(("plan creado (total bruto 100.000)", plan["total"] == 100000))

        venc = (date.today() + timedelta(days=15)).isoformat()

        # ── generar 3 cuotas sobre el neto (90.000) ──
        r = await client.post(f"/medico/planes/{plan_id}/cuotas", headers=medico, json={"n_cuotas": 3, "primer_vencimiento": venc})
        res = r.json()
        results.append(("generar 3 cuotas -> 201", r.status_code == 201 and len(res["cuotas"]) == 3))
        results.append(("las cuotas suman el total neto (90.000)", res["total"] == 90000))
        results.append(("cada cuota = 30.000", all(c["monto"] == 30000 for c in res["cuotas"])))
        results.append(("primera cuota vence en la fecha dada", res["cuotas"][0]["vencimiento"] == venc))

        # ── marcar la cuota 1 como pagada ──
        c1 = res["cuotas"][0]["id"]
        r = await client.patch(f"/medico/cuotas/{c1}", headers=medico, json={"pagado": True})
        results.append(("marcar cuota pagada -> 200 con fecha", r.status_code == 200 and r.json()["pagado"] and r.json()["pagado_at"]))
        r = await client.get(f"/medico/planes/{plan_id}/cuotas", headers=medico)
        results.append(("resumen: pagado 30.000, pendiente 60.000", r.json()["pagado"] == 30000 and r.json()["pendiente"] == 60000))

        # ── presupuesto imprimible ──
        r = await client.get(f"/medico/planes/{plan_id}/presupuesto", headers=medico)
        pres = r.json()
        results.append(("presupuesto trae paciente, profesional y cuotas", r.status_code == 200 and "Camila" in pres["paciente_nombre"] and pres["profesional_nombre"] and len(pres["cuotas"]) == 3))
        results.append(("presupuesto: total neto 90.000", pres["plan"]["resumen"]["total_neto"] == 90000))

        # ── regenerar reemplaza (2 cuotas, monto_total explícito 50.000) ──
        r = await client.post(f"/medico/planes/{plan_id}/cuotas", headers=medico, json={"n_cuotas": 2, "primer_vencimiento": venc, "monto_total": 50000})
        results.append(("regenerar reemplaza (2 cuotas de 25.000)", len(r.json()["cuotas"]) == 2 and r.json()["total"] == 50000))

        # ── validación: 0 cuotas -> 422 ──
        r = await client.post(f"/medico/planes/{plan_id}/cuotas", headers=medico, json={"n_cuotas": 0, "primer_vencimiento": venc})
        results.append(("n_cuotas = 0 -> 422", r.status_code == 422))

        # ── borrar cuotas ──
        r = await client.delete(f"/medico/planes/{plan_id}/cuotas", headers=medico)
        r2 = await client.get(f"/medico/planes/{plan_id}/cuotas", headers=medico)
        results.append(("borrar cuotas -> 204 y lista vacía", r.status_code == 204 and len(r2.json()["cuotas"]) == 0))

        # ── RBAC ──
        r = await client.post(f"/medico/planes/{plan_id}/cuotas", headers=paciente, json={"n_cuotas": 3, "primer_vencimiento": venc})
        results.append(("paciente no genera cuotas", r.status_code in (401, 403)))

    print("\n=== Presupuesto + cuotas (69.11 · 69.19) · smoke ===")
    ok = True
    for name, passed in results:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
        ok = ok and passed
    print("=== OK ===" if ok else "=== FALLÓ ===")
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
