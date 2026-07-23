"""Fase 6 smoke test: CRM / gestión financiera multi-clínica, contra el app
real + Postgres real. Cubre lo que la Spec CRM Clínicas fija como invariante:

  · Alcance por consumidor (§2/§7): super_admin ve el consolidado global;
    clinic_admin/empresa solo su clínica; médico/paciente no ven el CRM.
  · Fuente única de verdad (§1): los KPIs se calculan del ledger + agenda
    (ingresos, ticket promedio, por liquidar, ingresos por servicio).
  · Aislamiento por clinic_id (§9): un admin de clínica no ve otra clínica.
  · Conciliación de liquidaciones (§5.2): marcar pagado asienta un egreso
    inmutable en el ledger y saca el split de "por liquidar"; es idempotente
    (no se puede conciliar dos veces).
  · Exportar a ERP (§7): solo Admin.

Run: `python -m tests.test_crm_smoke` (requiere la BD seedeada).
"""

import asyncio

import httpx

from app.main import app

PASSWORD = "Demo1234!"


async def login(client: httpx.AsyncClient, email: str, password: str = PASSWORD) -> dict:
    r = await client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def main() -> None:
    transport = httpx.ASGITransport(app=app)
    results: list[tuple[str, bool]] = []

    def check(name: str, ok: bool) -> None:
        results.append((name, ok))

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        superh = await login(client, "super@todoscare.dev")
        admin_a = await login(client, "admin.a@todoscare.dev")
        admin_b = await login(client, "admin.b@todoscare.dev")
        empresa = await login(client, "empresa.a@todoscare.dev")
        medico = await login(client, "medico.a@todoscare.dev")
        paciente = await login(client, "paciente.a@todoscare.dev")

        # clinic ids (via admin)
        clinics = (await client.get("/admin/clinicas", headers=superh)).json()
        clinic_a = next(c["id"] for c in clinics if c["razon_social"] == "Clínica Demo A")
        clinic_b = next(c["id"] for c in clinics if c["razon_social"] == "Clínica Demo B")

        # ── Consolidado (§2/§7) ──
        r = await client.get("/crm/consolidado", headers=superh)
        cons = r.json()
        check("super_admin ve consolidado global (alcance=plataforma)", r.status_code == 200 and cons["alcance"] == "plataforma")
        check("consolidado: 2 clínicas y filas por clínica", cons["n_clinicas"] == 2 and len(cons["clinicas"]) == 2)
        check("consolidado: ingresos del mes > 0 (del ledger)", cons["ingresos_totales"] > 0)
        check("consolidado: variación vs mes anterior calculada (no None)", cons["variacion"] is not None)

        r = await client.get("/crm/consolidado", headers=admin_a)
        cons_a = r.json()
        check("clinic_admin.a ve consolidado acotado (alcance=clínica, 1 fila)", r.status_code == 200 and cons_a["alcance"] == "clínica" and len(cons_a["clinicas"]) == 1)
        check("clinic_admin.a solo ve su clínica en el consolidado", cons_a["clinicas"][0]["razon_social"] == "Clínica Demo A")

        check("médico NO ve el consolidado -> 403", (await client.get("/crm/consolidado", headers=medico)).status_code == 403)
        check("paciente NO ve el consolidado -> 403", (await client.get("/crm/consolidado", headers=paciente)).status_code == 403)
        check("empresa NO ve el consolidado global -> 403", (await client.get("/crm/consolidado", headers=empresa)).status_code == 403)

        # ── Detalle / KPIs de una clínica (§3/§4) ──
        r = await client.get(f"/crm/clinicas/{clinic_a}", headers=superh)
        det = r.json()
        check("detalle de clínica -> 200 con KPIs", r.status_code == 200 and det["razon_social"] == "Clínica Demo A")
        check("ticket promedio = 270 (ingresos de atención / n.º atenciones)", abs(det["ticket_promedio"] - 270.0) < 0.01)
        # ── Indicadores de marketing / captación ──
        mkt = det["marketing"]
        check("marketing: gasto = 300 y 1 paciente nuevo", abs(mkt["gasto_marketing"] - 300) < 0.01 and mkt["nuevos_pacientes"] == 1)
        check("marketing: CAC = 300 (gasto / nuevos)", abs(mkt["cac"] - 300) < 0.01)
        check("marketing: LTV, ratio LTV:CAC y ROAS calculados", mkt["ltv"] is not None and mkt["ltv_cac_ratio"] is not None and mkt["roas"] is not None)
        check("por liquidar = 486 (3 splits × 162 pendientes)", abs(det["por_liquidar"] - 486.0) < 0.01)
        check("ocupación entre 0 y 1", 0.0 <= det["ocupacion"] <= 1.0)
        svc = {s["servicio"]: s["monto"] for s in det["ingresos_por_servicio"]}
        check("ingresos por servicio incluye 'Médico general' = 810", abs(svc.get("Médico general", 0) - 810.0) < 0.01)

        # ── Empresa: su clínica sí, ajeno no ──
        r = await client.get("/crm/mi-clinica", headers=empresa)
        check("empresa ve KPIs de SU clínica (/crm/mi-clinica) -> 200", r.status_code == 200 and r.json()["razon_social"] == "Clínica Demo A")
        check("empresa NO puede conciliar (sin CRM_CONCILIAR) -> 403", (await client.get("/crm/liquidaciones", headers=empresa)).status_code == 403)
        check("empresa NO puede exportar a ERP -> 403", (await client.get("/crm/exportar", headers=empresa)).status_code == 403)

        # ── Aislamiento por clinic_id (§9) ──
        check("clinic_admin.a NO ve el detalle de Clínica Demo B -> 403", (await client.get(f"/crm/clinicas/{clinic_b}", headers=admin_a)).status_code == 403)

        # ── Liquidaciones + conciliación (§5.2) ──
        r = await client.get("/crm/liquidaciones", headers=superh)
        liqs = r.json()
        check("liquidaciones: 3 pendientes", r.status_code == 200 and len(liqs) == 3)
        check("liquidaciones: prestador = Dr. Fuentes", all(x["prestador"] == "Dr. Fuentes" for x in liqs))
        split_id = liqs[0]["split_id"]

        ledger_before = (await client.get("/crm/exportar", headers=superh)).json()
        n_liq_pagada_before = sum(1 for e in ledger_before if e["tipo"] == "liquidacion_pagada")

        r = await client.post(f"/crm/liquidaciones/{split_id}/conciliar", headers=superh)
        check("conciliar liquidación -> 200 estado=conciliado", r.status_code == 200 and r.json()["estado"] == "conciliado")

        r = await client.get("/crm/liquidaciones", headers=superh)
        check("tras conciliar quedan 2 pendientes", len(r.json()) == 2)

        r = await client.get(f"/crm/clinicas/{clinic_a}", headers=superh)
        check("por liquidar baja a 324 (486 − 162)", abs(r.json()["por_liquidar"] - 324.0) < 0.01)

        ledger_after = (await client.get("/crm/exportar", headers=superh)).json()
        n_liq_pagada_after = sum(1 for e in ledger_after if e["tipo"] == "liquidacion_pagada")
        check("la conciliación asienta un egreso inmutable en el ledger", n_liq_pagada_after == n_liq_pagada_before + 1)

        r = await client.post(f"/crm/liquidaciones/{split_id}/conciliar", headers=superh)
        check("conciliar el mismo split de nuevo -> 409 (idempotente)", r.status_code == 409)

        check("médico NO puede conciliar -> 403", (await client.post(f"/crm/liquidaciones/{split_id}/conciliar", headers=medico)).status_code == 403)

        # ── Export ERP solo Admin ──
        r = await client.get("/crm/exportar", headers=superh)
        check("super_admin exporta asientos a ERP -> 200 (no vacío)", r.status_code == 200 and len(r.json()) > 0)

    print()
    failed = 0
    for name, ok in results:
        st = "PASS" if ok else "FAIL"
        if not ok:
            failed += 1
        print(f"  [{st}] {name}")
    print()
    if failed:
        print(f"{failed} check(s) FAILED")
        raise SystemExit(1)
    print(f"All {len(results)} checks passed.")


if __name__ == "__main__":
    asyncio.run(main())
