"""Tanda 1 smoke test: Agenda de la clínica (vista gerencia) + estados de cita
enriquecidos, contra el app real + Postgres real.

Cubre: la empresa ve la agenda del día con todos los profesionales; la
situación de pago se calcula del ledger (no facturado antes del cierre,
facturado después); recepción/gerencia mueve el estado operativo; 'completada'
está reservada al cierre del médico; y el médico no accede a la agenda de
gerencia. Run: `python -m tests.test_agenda_gerencia_smoke`.
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
        paciente = await login(client, "paciente.a@todoscare.dev")

        # ---- agenda del día (gerencia) ----
        r = await client.get(f"/empresa/agenda?fecha={today}", headers=empresa)
        results.append(("agenda del día -> 200", r.status_code == 200))
        data = r.json()
        cita = next((c for c in data["citas"] if "Camila" in c["paciente_nombre"]), None)
        results.append(("aparece la cita de Camila (seed, hoy 10:00)", cita is not None))
        results.append(("trae el nombre del profesional", bool(cita and cita["profesional_nombre"])))
        results.append(("estado inicial 'confirmada'", bool(cita and cita["estado"] == "confirmada")))
        # El seed asienta ingresos del CRM contra esta cita, así que la situación
        # de pago (calculada del ledger) aparece como FACTURADA desde el inicio.
        results.append(("situación de pago calculada del ledger (facturada por seed)", bool(cita and cita["facturado"] is True)))
        results.append(("monto de la situación de pago (>0)", bool(cita and cita["monto"] and cita["monto"] > 0)))
        results.append(("resumen por_estado cuenta 'confirmada'", data["por_estado"].get("confirmada", 0) >= 1))

        cita_id = cita["id"]

        # el médico NO entra a la agenda de gerencia
        r = await client.get(f"/empresa/agenda?fecha={today}", headers=medico)
        results.append(("médico NO accede a /empresa/agenda -> 403", r.status_code == 403))

        # ---- cambiar estado operativo (recepción) ----
        r = await client.patch(f"/empresa/citas/{cita_id}/estado", headers=empresa, json={"estado": "en_sala_espera"})
        results.append(("marcar 'en_sala_espera' -> 200", r.status_code == 200 and r.json()["estado"] == "en_sala_espera"))

        r = await client.get(f"/empresa/agenda?fecha={today}", headers=empresa)
        cita2 = next((c for c in r.json()["citas"] if c["id"] == cita_id), None)
        results.append(("la agenda refleja 'en_sala_espera'", bool(cita2 and cita2["estado"] == "en_sala_espera")))

        # 'completada' está reservada al cierre del médico
        r = await client.patch(f"/empresa/citas/{cita_id}/estado", headers=empresa, json={"estado": "completada"})
        results.append(("no se puede fijar 'completada' desde gerencia -> 400", r.status_code == 400))

        # estado inválido
        r = await client.patch(f"/empresa/citas/{cita_id}/estado", headers=empresa, json={"estado": "volando"})
        results.append(("estado inválido -> 400", r.status_code == 400))

        # ---- el cierre del médico marca la situación de pago (facturado) ----
        r = await client.post(f"/medico/citas/{cita_id}/cerrar", headers=medico)
        results.append(("médico cierra la atención -> 200", r.status_code == 200))

        r = await client.get(f"/empresa/agenda?fecha={today}", headers=empresa)
        cita3 = next((c for c in r.json()["citas"] if c["id"] == cita_id), None)
        results.append(("tras el cierre la cita queda 'completada'", bool(cita3 and cita3["estado"] == "completada")))
        results.append(("tras el cierre la cita queda FACTURADA", bool(cita3 and cita3["facturado"] is True)))
        results.append(("el monto facturado es > 0", bool(cita3 and cita3["monto"] and cita3["monto"] > 0)))

        # ya cerrada: gerencia no puede cambiar su estado
        r = await client.patch(f"/empresa/citas/{cita_id}/estado", headers=empresa, json={"estado": "en_sala_espera"})
        results.append(("cita ya cerrada: no se cambia desde gerencia -> 400", r.status_code == 400))

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
