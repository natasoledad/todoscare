"""Smoke test de los diferenciadores IA (punto 72).

Flujo: el paciente sube un examen → la IA (conector 'ia_clinica') genera una
sugerencia para su ficha con un próximo control → el paciente la aplica (la
ficha se actualiza) → recibe recordatorios → conversa con el chatbot y le pide
agendar → el bot le toma la próxima hora libre.

Run: `python -m tests.test_ia_clinica_smoke`.
"""

import asyncio
from datetime import datetime, timedelta, timezone

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
        pac = await login(client, "paciente.a@todoscare.dev")
        emp = await login(client, "empresa.a@todoscare.dev")

        # 1 · el paciente sube un examen cardiovascular -> la IA lo analiza
        up = await client.post("/salud/examenes/subir", headers=pac,
                               files={"file": ("presion_arterial.pdf", b"%PDF-1.4 demo", "application/pdf")})
        check("Subir examen -> 201", up.status_code == 201)

        sugs = (await client.get("/ia/sugerencias", headers=pac, params={"estado": "pendiente"})).json()
        check("La IA generó una sugerencia pendiente", len(sugs) >= 1)
        sug = sugs[0]
        check("Sugerencia trae hallazgos + próximo control", bool(sug["hallazgos"]) and sug["proximo_control"])
        check("Sugerencia detectó seguimiento cardiovascular", sug["hallazgos"].get("seguimiento_cardiovascular") is True)

        # 2 · aplicar -> la ficha se actualiza y queda el próximo control
        ap = await client.post(f"/ia/sugerencias/{sug['id']}/aplicar", headers=pac)
        check("Aplicar sugerencia -> 200", ap.status_code == 200)
        body = ap.json()
        check("La ficha incorporó el hallazgo", body["ficha"].get("seguimiento_cardiovascular") is True)
        check("La ficha guardó el próximo control", body["ficha"].get("proximo_control") == sug["proximo_control"])

        # aplicar dos veces -> 400
        ap2 = await client.post(f"/ia/sugerencias/{sug['id']}/aplicar", headers=pac)
        check("Reaplicar sugerencia -> 400", ap2.status_code == 400)

        # segunda sugerencia (glicemia) que se descarta
        await client.post("/salud/examenes/subir", headers=pac,
                          files={"file": ("glicemia_ayunas.pdf", b"%PDF demo", "application/pdf")})
        pend = (await client.get("/ia/sugerencias", headers=pac, params={"estado": "pendiente"})).json()
        gli = next((s for s in pend if s["hallazgos"].get("seguimiento_glicemia")), None)
        check("Sugerencia de glicemia detectada", gli is not None)
        de = await client.post(f"/ia/sugerencias/{gli['id']}/descartar", headers=pac)
        check("Descartar sugerencia -> 200 descartada", de.status_code == 200 and de.json()["estado"] == "descartada")

        # 3 · recordatorios: el control aplicado aparece
        recs = (await client.get("/ia/recordatorios", headers=pac)).json()
        check("Recordatorio de control presente", any(r["tipo"] == "control" for r in recs))

        # 4 · chatbot: intención de agendar
        ch = await client.post("/ia/chat", headers=pac, json={"texto": "quiero agendar una hora"})
        check("Chat detecta intención agendar", ch.status_code == 200 and ch.json()["intent"] == "agendar" and ch.json()["accion"] == "agendar")

        chs = await client.post("/ia/chat", headers=pac, json={"texto": "cómo está mi ficha y mis exámenes"})
        check("Chat responde sobre la ficha/IA", chs.status_code == 200 and chs.json()["intent"] == "salud")

        # 5 · el bot agenda la próxima hora libre (bloque futuro creado por empresa)
        prof = (await client.get("/empresa/profesionales", headers=emp)).json()[0]
        branch = (await client.get("/empresa/sucursales", headers=emp)).json()[0]
        base = (datetime.now(timezone.utc) + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
        await client.post("/empresa/agendas", headers=emp, json={
            "professional_id": prof["id"], "branch_id": branch["id"],
            "inicio": base.isoformat(), "fin": (base + timedelta(hours=4)).isoformat(),
        })
        service = next(s for s in (await client.get("/agenda/servicios", headers=pac)).json())
        antes = datetime.now(timezone.utc)
        ag = await client.post("/ia/agendar", headers=pac, json={"service_id": service["id"]})
        check("El bot agenda -> 201 con cita", ag.status_code == 201 and ag.json()["agendada"] and ag.json()["appointment_id"])
        # Comparar como datetime (no string): el bot reserva el primer slot libre,
        # que puede empezar en el 'ahora' del servidor con microsegundos; `antes`
        # se toma antes del POST, así el slot reservado nunca es anterior.
        check("La cita agendada es futura", datetime.fromisoformat(ag.json()["inicio"]) >= antes)

        # tras agendar, el recordatorio de cita aparece
        recs2 = (await client.get("/ia/recordatorios", headers=pac)).json()
        check("Recordatorio de próxima cita presente", any(r["tipo"] == "cita" for r in recs2))

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
