"""Fase 7 smoke test: Rol Aseguradora / Prestador contra el app real +
Postgres real. Cubre lo que la Spec Aseguradora Prestador fija:

  · Alcance por entidad (§3): la aseguradora ve su cartera (convenios,
    padrón, autorizaciones) — médico/paciente no acceden al portal.
  · Resolver autorizaciones (§5.1): aprobar / rechazar (con motivo);
    idempotente (no se re-resuelve).
  · Mínimo dato clínico (§3): la ficha del afiliado solo se abre si hay una
    autorización aprobada, y queda auditada.
  · Liquidar a la clínica (§5.2): generar asienta 'facturado' (sube la CxC
    del CRM) y pagar asienta 'cobrado' (la baja) — trazable en el ledger
    inmutable; el pago es idempotente.

Run: `python -m tests.test_aseguradora_smoke` (requiere la BD seedeada).
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
        aseg = await login(client, "aseguradora.x@todoscare.dev")
        medico = await login(client, "medico.a@todoscare.dev")
        paciente = await login(client, "paciente.a@todoscare.dev")
        superh = await login(client, "super@todoscare.dev")

        # ── Inicio / KPIs ──
        r = await client.get("/aseguradora/inicio", headers=aseg)
        kpis = r.json()
        check("inicio -> 200 con nombre de la aseguradora", r.status_code == 200 and kpis["insurer_nombre"] == "Seguros Bienestar MX")
        check("KPIs: 1 afiliado, 2 autorizaciones pendientes", kpis["afiliados"] == 1 and kpis["autorizaciones_pendientes"] == 2)
        check("KPIs: por liquidar = 0 al inicio", kpis["por_liquidar"] == 0)

        # ── RBAC: otros roles no entran ──
        check("médico NO accede a /aseguradora/convenios -> 403", (await client.get("/aseguradora/convenios", headers=medico)).status_code == 403)
        check("paciente NO accede a /aseguradora/autorizaciones -> 403", (await client.get("/aseguradora/autorizaciones", headers=paciente)).status_code == 403)

        # ── Convenios y aranceles ──
        r = await client.get("/aseguradora/convenios", headers=aseg)
        convenios = r.json()
        check("1 convenio vigente con Clínica Demo A (1 arancel)", len(convenios) == 1 and convenios[0]["clinica"] == "Clínica Demo A" and convenios[0]["vigente"] and convenios[0]["aranceles"] == 1)
        agreement_id = convenios[0]["agreement_id"]

        r = await client.get(f"/aseguradora/convenios/{agreement_id}/aranceles", headers=aseg)
        aran = r.json()
        check("arancel 'Médico general' con cobertura 80%", len(aran) == 1 and aran[0]["servicio"] == "Médico general" and abs(aran[0]["cobertura_pct"] - 80) < 0.01)

        # ── Padrón ──
        r = await client.get("/aseguradora/afiliados", headers=aseg)
        padron = r.json()
        check("padrón: Camila afiliada y vigente", len(padron) == 1 and padron[0]["nombre"] == "Camila Rodríguez" and padron[0]["vigente"])
        patient_id = padron[0]["patient_id"]

        # ── Autorizaciones ──
        r = await client.get("/aseguradora/autorizaciones?estado=pendiente", headers=aseg)
        auths = r.json()
        check("2 autorizaciones pendientes en bandeja", len(auths) == 2)
        auth1, auth2 = auths[0]["authorization_id"], auths[1]["authorization_id"]

        # ── Mínimo dato clínico: sin aprobación, sin ficha ──
        check("ficha del afiliado SIN autorización aprobada -> 403", (await client.get(f"/aseguradora/afiliados/{patient_id}/ficha", headers=aseg)).status_code == 403)

        # ── Resolver ──
        r = await client.post(f"/aseguradora/autorizaciones/{auth1}/resolver", headers=aseg, json={"decision": "aprobar"})
        check("aprobar autorización -> 200 estado=aprobada", r.status_code == 200 and r.json()["estado"] == "aprobada")
        check("rechazar sin motivo -> 400", (await client.post(f"/aseguradora/autorizaciones/{auth2}/resolver", headers=aseg, json={"decision": "rechazar"})).status_code == 400)
        r = await client.post(f"/aseguradora/autorizaciones/{auth2}/resolver", headers=aseg, json={"decision": "rechazar", "motivo": "Prestación fuera de cobertura"})
        check("rechazar con motivo -> 200 estado=rechazada", r.status_code == 200 and r.json()["estado"] == "rechazada")
        check("re-resolver una autorización ya resuelta -> 409", (await client.post(f"/aseguradora/autorizaciones/{auth1}/resolver", headers=aseg, json={"decision": "aprobar"})).status_code == 409)

        # ── Ficha del afiliado tras aprobación (minimizada + auditada) ──
        r = await client.get(f"/aseguradora/afiliados/{patient_id}/ficha", headers=aseg)
        ficha = r.json()
        check("ficha del afiliado tras aprobar -> 200 minimizada", r.status_code == 200 and ficha["nombre"] == "Camila Rodríguez" and "prestaciones_autorizadas" in ficha)
        check("la ficha NO expone el prontuario completo (solo prestaciones autorizadas)", set(ficha.keys()) == {"patient_id", "nombre", "documento_identidad", "plan_cobertura", "prestaciones_autorizadas"})

        # el acceso quedó auditado (lo ve el admin)
        audit = (await client.get("/admin/auditoria", headers=superh)).json()
        check("el acceso a la ficha del afiliado queda auditado", any(a["accion"] == "ver_ficha_afiliado" for a in audit))

        # ── Liquidación + integración con la CxC del CRM ──
        r = await client.post(f"/aseguradora/convenios/{agreement_id}/liquidaciones", headers=aseg, json={"periodo": "2026-07"})
        check("generar liquidación -> 201 monto=360 (450 × 80%)", r.status_code == 201 and abs(r.json()["monto"] - 360.0) < 0.01)
        settlement_id = r.json()["settlement_id"]

        r = await client.get(f"/crm/clinicas/{convenios[0]['clinic_id']}", headers=superh)
        check("CRM: la liquidación sube las Cuentas por Cobrar a 360", abs(r.json()["cuentas_por_cobrar"] - 360.0) < 0.01)

        r = await client.get("/aseguradora/liquidaciones", headers=aseg)
        check("liquidación pendiente en bandeja", len(r.json()) == 1 and r.json()[0]["estado"] == "pendiente")

        r = await client.post(f"/aseguradora/liquidaciones/{settlement_id}/pagar", headers=aseg)
        check("pagar liquidación -> 200 estado=pagado", r.status_code == 200 and r.json()["estado"] == "pagado")

        r = await client.get(f"/crm/clinicas/{convenios[0]['clinic_id']}", headers=superh)
        check("CRM: tras pagar, las Cuentas por Cobrar vuelven a 0", abs(r.json()["cuentas_por_cobrar"]) < 0.01)

        check("pagar la misma liquidación de nuevo -> 409", (await client.post(f"/aseguradora/liquidaciones/{settlement_id}/pagar", headers=aseg)).status_code == 409)
        check("generar liquidación del mismo período de nuevo -> 409", (await client.post(f"/aseguradora/convenios/{agreement_id}/liquidaciones", headers=aseg, json={"periodo": "2026-07"})).status_code == 409)

        # ── Padrón: alta y baja ──
        r = await client.post("/aseguradora/afiliados", headers=aseg, json={"documento_identidad": "MX-NUEVO-99", "plan_cobertura": "Plan Básico"})
        check("alta de afiliado -> 201 vigente", r.status_code == 201 and r.json()["documento_identidad"] == "MX-NUEVO-99")
        nuevo_id = r.json()["affiliate_id"]
        check("alta duplicada -> 409", (await client.post("/aseguradora/afiliados", headers=aseg, json={"documento_identidad": "MX-NUEVO-99"})).status_code == 409)
        check("baja de afiliado -> 204", (await client.delete(f"/aseguradora/afiliados/{nuevo_id}", headers=aseg)).status_code == 204)

        # ── Red de prestadores ──
        r = await client.get("/aseguradora/red", headers=aseg)
        check("red: 1 clínica en convenio", r.status_code == 200 and len(r.json()) == 1 and r.json()[0]["clinica"] == "Clínica Demo A")

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
