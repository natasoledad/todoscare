"""Smoke test del timeline clínico unificado (70.1).

El endpoint /medico/pacientes/{id}/timeline reúne en una sola línea de tiempo
—orden cronológico inverso— prontuarios, prescripciones, órdenes de examen,
planes, periodontogramas, documentos y signos vitales del paciente.

Run: `python -m tests.test_timeline_smoke`.
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
        medico = await login(client, "medico.a@todoscare.dev")
        medico_b = await login(client, "medico.b@todoscare.dev")  # no trata a Camila
        paciente = await login(client, "paciente.a@todoscare.dev")

        cita = next((c for c in (await client.get("/medico/agenda", headers=medico)).json() if "Camila" in c["paciente_nombre"]), None)
        pid = cita["patient_id"]
        aid = cita["id"]

        # Generar eventos de distintos tipos
        await client.post(f"/medico/citas/{aid}/atencion", headers=medico, json={"motivo": "Dolor torácico", "diagnostico": "Observación"})
        pres = await client.post(f"/medico/citas/{aid}/prescripcion", headers=medico, json={"items": [{"medicamento": "Paracetamol", "cantidad": "1", "indicaciones": "c/8h"}], "confirmar_alertas": True})
        check("Prescripción firmada", pres.status_code == 200 and pres.json().get("prescripcion") is not None)
        await client.post(f"/medico/citas/{aid}/orden-examen", headers=medico, json={"tipo": "laboratorio"})
        await client.post(f"/medico/pacientes/{pid}/planes", headers=medico, json={"titulo": "Rehab", "items": [{"descripcion": "Endodoncia", "precio_unit": 50000}]})
        await client.post(f"/medico/pacientes/{pid}/periodontograma", headers=medico, json={"datos": {"1.6": {"ps": 3, "sangrado": True}}})
        await client.post(f"/medico/pacientes/{pid}/documentos", headers=medico, json={"tipo": "consentimiento", "titulo": "Consentimiento informado"})
        await client.post(f"/medico/pacientes/{pid}/signos-vitales", headers=medico, json={"presion_sistolica": 120, "presion_diastolica": 80, "fc_ppm": 72})

        r = await client.get(f"/medico/pacientes/{pid}/timeline", headers=medico)
        check("Timeline -> 200", r.status_code == 200)
        eventos = r.json()
        tipos = {e["tipo"] for e in eventos}
        esperados = {"prontuario", "prescripcion", "orden_examen", "plan", "periodontograma", "documento", "signos"}
        check(f"Timeline cubre los 7 tipos (tiene {sorted(tipos)})", esperados <= tipos)

        fechas = [e["fecha"] for e in eventos]
        check("Orden cronológico inverso (desc)", fechas == sorted(fechas, reverse=True))

        pres_ev = next((e for e in eventos if e["tipo"] == "prescripcion"), None)
        check("Evento de prescripción trae estado 'vigente'", pres_ev is not None and pres_ev["estado"] == "vigente")

        plan_ev = next((e for e in eventos if e["tipo"] == "plan"), None)
        check("Evento de plan trae título y estado", plan_ev is not None and "Rehab" in plan_ev["titulo"] and plan_ev["estado"])

        signos_ev = next((e for e in eventos if e["tipo"] == "signos"), None)
        check("Evento de signos resume PA/FC", signos_ev is not None and "PA 120/80" in (signos_ev["resumen"] or ""))

        # RBAC: quien no trata al paciente no ve su timeline
        rb = await client.get(f"/medico/pacientes/{pid}/timeline", headers=medico_b)
        check("Médico ajeno -> 403/404", rb.status_code in (403, 404))
        rp = await client.get(f"/medico/pacientes/{pid}/timeline", headers=paciente)
        check("Paciente NO usa endpoint médico -> 403", rp.status_code == 403)

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
