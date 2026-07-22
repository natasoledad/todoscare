"""Fase 3 smoke test: exercises the Rol Médico end-to-end against the real
app + real Postgres. Covers agenda, la regla de aislamiento clínico (un
médico que NO atiende al paciente es rechazado), prontuario + enmienda
auditada, prescripción con bloqueo por alerta de alergia y firma,
reemisión (anula+reemite), orden de examen (que aparece en la app del
paciente), odontograma, cierre de atención con liquidación/split, y que el
acceso a la ficha quedó auditado. Run: `python -m tests.test_medico_smoke`.
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
        medico = await login(client, "medico.a@todoscare.dev")       # Dra. Nátaly, atiende a Camila
        medico_b = await login(client, "medico.b@todoscare.dev")     # Dr. Fuentes, sin citas
        paciente = await login(client, "paciente.a@todoscare.dev")   # Camila

        # ---- agenda ----
        r = await client.get("/medico/agenda", headers=medico)
        agenda = r.json()
        results.append(("agenda del médico tiene 1 cita con Camila", r.status_code == 200 and len(agenda) == 1 and agenda[0]["paciente_nombre"] == "Camila Rodríguez"))
        cita = agenda[0]
        cita_id = cita["id"]
        patient_id = cita["patient_id"]
        results.append(("la cita aún no está atendida", agenda[0]["atendida"] is False))

        # médico_b's agenda is empty
        r = await client.get("/medico/agenda", headers=medico_b)
        results.append(("agenda del médico sin citas está vacía", r.json() == []))

        # ---- aislamiento clínico ----
        r = await client.get(f"/medico/pacientes/{patient_id}/ficha", headers=medico)
        results.append(("médico que atiende ve la ficha -> 200", r.status_code == 200 and r.json()["nombre"] == "Camila Rodríguez"))
        results.append(("la ficha trae exámenes seedeados", len(r.json()["examenes"]) == 3))

        r = await client.get(f"/medico/pacientes/{patient_id}/ficha", headers=medico_b)
        results.append(("médico que NO atiende es rechazado -> 403", r.status_code == 403))

        # paciente no puede usar endpoints de médico
        r = await client.get("/medico/agenda", headers=paciente)
        results.append(("paciente no accede a /medico/agenda -> 403", r.status_code == 403))

        # ---- prontuario ----
        r = await client.post(f"/medico/citas/{cita_id}/atencion", headers=medico, json={"motivo": "Dolor torácico", "evolucion": "Estable", "diagnostico": "Descartar causa cardíaca"})
        results.append(("registrar atención -> 201", r.status_code == 201 and r.json()["contenido"]["motivo"] == "Dolor torácico"))
        record_id = r.json()["id"]

        r = await client.get("/medico/agenda", headers=medico)
        results.append(("la cita ahora figura como atendida", r.json()[0]["atendida"] is True))

        # enmienda auditada (no borra el original)
        r = await client.patch(f"/medico/prontuario/{record_id}/enmienda", headers=medico, json={"nota": "Se corrige: diagnóstico confirmado"})
        cont = r.json()["contenido"]
        results.append(("enmienda apila sin borrar (motivo intacto + 1 enmienda)", cont["motivo"] == "Dolor torácico" and len(cont["enmiendas"]) == 1))

        # médico_b no puede enmendar el registro ajeno
        r = await client.patch(f"/medico/prontuario/{record_id}/enmienda", headers=medico_b, json={"nota": "hack"})
        results.append(("médico ajeno no puede enmendar -> 403", r.status_code == 403))

        # ---- prescripción con alerta de alergia ----
        # Camila declara alergia a Penicilina en su ficha (seed).
        r = await client.post(f"/medico/citas/{cita_id}/prescripcion", headers=medico, json={"items": [{"medicamento": "Amoxicilina/Penicilina 500mg"}], "confirmar_alertas": False})
        body = r.json()
        results.append(("prescribir alérgeno sin confirmar -> bloqueado (prescripcion None + alerta)", body["prescripcion"] is None and len(body["alertas"]) == 1))

        r = await client.post(f"/medico/citas/{cita_id}/prescripcion", headers=medico, json={"items": [{"medicamento": "Amoxicilina/Penicilina 500mg", "cantidad": "10", "indicaciones": "c/8h"}], "confirmar_alertas": True})
        body = r.json()
        results.append(("prescribir confirmando la alerta -> firmada", body["prescripcion"] is not None and body["prescripcion"]["firmado_en"] is not None))
        presc_id = body["prescripcion"]["id"]

        # prescripción sin alérgeno pasa directo
        r = await client.post(f"/medico/citas/{cita_id}/prescripcion", headers=medico, json={"items": [{"medicamento": "Paracetamol 500mg"}]})
        results.append(("prescribir sin alérgeno -> firmada sin alertas", r.json()["prescripcion"] is not None and r.json()["alertas"] == []))

        # reemitir (anula + reemite)
        r = await client.post(f"/medico/prescripciones/{presc_id}/reemitir", headers=medico, json={"items": [{"medicamento": "Paracetamol 1g"}]})
        results.append(("reemitir -> nueva vigente", r.status_code == 200 and r.json()["prescripcion"]["estado"] == "vigente"))

        # ---- orden de examen (aparece en la app del paciente) ----
        r = await client.post(f"/medico/citas/{cita_id}/orden-examen", headers=medico, json={"tipo": "laboratorio"})
        results.append(("crear orden de examen -> 201 pendiente", r.status_code == 201 and r.json()["estado"] == "pendiente"))
        orden_id = r.json()["id"]

        r = await client.get("/salud/examenes", headers=paciente)
        results.append(("la orden nueva aparece en /salud/examenes del paciente", any(e["estado"] == "pendiente" for e in r.json())))

        # editar y cancelar orden pendiente
        r = await client.patch(f"/medico/ordenes/{orden_id}", headers=medico, json={"tipo": "imagenes"})
        results.append(("editar orden pendiente -> tipo imagenes", r.json()["tipo"] == "imagenes"))
        r = await client.patch(f"/medico/ordenes/{orden_id}/cancelar", headers=medico)
        results.append(("cancelar orden pendiente -> cancelada", r.json()["estado"] == "cancelada"))

        # ---- odontograma ----
        r = await client.put(f"/medico/pacientes/{patient_id}/odontograma", headers=medico, json={"piezas": {"15": {"estado": "tratada"}, "24": {"estado": "pendiente"}}})
        results.append(("actualizar odontograma -> ok", r.status_code == 200 and r.json()["piezas"]["15"]["estado"] == "tratada"))

        r = await client.put(f"/medico/pacientes/{patient_id}/odontograma", headers=medico_b, json={"piezas": {}})
        results.append(("médico ajeno no actualiza odontograma -> 403", r.status_code == 403))

        # ---- cierre / liquidación ----
        r = await client.get("/medico/liquidaciones", headers=medico)
        results.append(("liquidaciones vacías antes de cerrar", r.json() == []))

        r = await client.post(f"/medico/citas/{cita_id}/cerrar", headers=medico)
        # Médico general = $450, split 60% = 270
        results.append(("cerrar atención -> completada + split 270", r.status_code == 200 and r.json()["estado"] == "completada" and abs(r.json()["split_monto"] - 270.0) < 0.01))

        r = await client.get("/medico/liquidaciones", headers=medico)
        results.append(("liquidación aparece en /medico/liquidaciones", len(r.json()) == 1 and abs(r.json()[0]["monto"] - 270.0) < 0.01))

        # cerrar dos veces -> 400
        r = await client.post(f"/medico/citas/{cita_id}/cerrar", headers=medico)
        results.append(("cerrar una cita ya cerrada -> 400", r.status_code == 400))

    print()
    failed = 0
    for name, ok in results:
        status = "PASS" if ok else "FAIL"
        if not ok:
            failed += 1
        print(f"  [{status}] {name}")
    print()
    if failed:
        print(f"{failed} check(s) FAILED")
        raise SystemExit(1)
    print(f"All {len(results)} checks passed.")


if __name__ == "__main__":
    asyncio.run(main())
