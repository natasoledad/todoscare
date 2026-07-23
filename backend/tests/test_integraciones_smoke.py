"""Fase 8 smoke test: capa de conectores externos, contra el app real +
Postgres real. Verifica que la plataforma se integra con el mundo exterior
por una frontera tipada, auditable y gobernada por IntegrationConfig:

  · Estado/traza: solo el Administrador ve y gobierna los conectores.
  · WhatsApp/IA: el asistente responde al paciente con datos reales.
  · Pago: el webhook de la pasarela asienta ingreso + split en el ledger
    inmutable (sube los ingresos del CRM); idempotente.
  · Laboratorio: el webhook de resultado lo publica en Mi Salud.
  · Farmacia: el webhook de estado deja traza logística.
  · Mapas: ordena sucursales por cercanía (Haversine).
  · Push: un conector deshabilitado rechaza el envío (409); habilitado,
    entrega y el usuario ve su notificación.

Run: `python -m tests.test_integraciones_smoke` (requiere la BD seedeada).
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
        admin = await login(client, "admin.a@todoscare.dev")
        superh = await login(client, "super@todoscare.dev")
        medico = await login(client, "medico.a@todoscare.dev")
        paciente = await login(client, "paciente.a@todoscare.dev")

        # ── Estado / traza (Admin) ──
        r = await client.get("/integraciones/estado", headers=admin)
        est = r.json()
        tipos = {c["tipo"]: c["activo"] for c in est["conectores"]}
        check("admin ve 6 conectores", r.status_code == 200 and len(est["conectores"]) == 6)
        check("push viene deshabilitado en el seed", tipos.get("push") is False and tipos.get("whatsapp") is True)
        check("médico NO ve el estado de integraciones -> 403", (await client.get("/integraciones/estado", headers=medico)).status_code == 403)
        check("paciente NO ve el estado de integraciones -> 403", (await client.get("/integraciones/estado", headers=paciente)).status_code == 403)

        # ── WhatsApp / IA ──
        r = await client.post("/integraciones/whatsapp/mensaje", headers=paciente, json={"texto": "hola"})
        check("asistente responde a un saludo (intent=saludo)", r.status_code == 200 and r.json()["intent"] == "saludo")
        r = await client.post("/integraciones/whatsapp/mensaje", headers=paciente, json={"texto": "¿cuándo es mi próxima cita?"})
        check("asistente resuelve 'próxima cita' con respuesta real", r.status_code == 200 and r.json()["intent"] == "proxima_cita" and len(r.json()["reply"]) > 0)
        check("médico NO usa el asistente del paciente -> 403", (await client.post("/integraciones/whatsapp/mensaje", headers=medico, json={"texto": "hola"})).status_code == 403)

        # cita confirmada del seed (para la atención del médico)
        agenda = (await client.get("/medico/agenda", headers=medico)).json()
        cita_id = agenda[0]["id"]
        examenes_baseline = len((await client.get("/salud/examenes", headers=paciente)).json())

        # ── Pago: intent (paciente) + webhook (pasarela) -> ledger + CRM ──
        # Se reserva una cita nueva para el pago (la cita del seed ya tiene
        # ingresos de demo del CRM).
        clinics = (await client.get("/admin/clinicas", headers=superh)).json()
        clinic_a = next(c["id"] for c in clinics if c["razon_social"] == "Clínica Demo A")
        mg = next(s for s in (await client.get("/agenda/servicios", headers=paciente)).json() if s["nombre"] == "Médico general")
        slot = (await client.get("/agenda/disponibilidad", params={"service_id": mg["id"]}, headers=paciente)).json()[0]
        pago_cita = (await client.post("/agenda/reservar", headers=paciente, json={"service_id": mg["id"], "professional_id": slot["professional_id"], "inicio": slot["inicio"], "fin": slot["fin"]})).json()
        pago_cita_id = pago_cita["id"]
        ingresos_antes = (await client.get(f"/crm/clinicas/{clinic_a}", headers=superh)).json()["ingresos"]

        r = await client.post("/integraciones/pago/intent", headers=paciente, json={"appointment_id": pago_cita_id})
        check("paciente crea intent de pago -> 201 requiere_confirmacion", r.status_code == 201 and r.json()["estado"] == "requiere_confirmacion")
        r = await client.post("/integraciones/pago/webhook", headers=admin, json={"appointment_id": pago_cita_id})
        check("webhook de pago asienta ingreso+split -> 200 (monto 450 / split 270)", r.status_code == 200 and abs(r.json()["monto"] - 450) < 0.01 and abs(r.json()["split"] - 270) < 0.01)
        ingresos_desp = (await client.get(f"/crm/clinicas/{clinic_a}", headers=superh)).json()["ingresos"]
        check("CRM: el pago sube los ingresos de la clínica en 450", abs((ingresos_desp - ingresos_antes) - 450) < 0.01)
        check("webhook de pago idempotente (segunda vez) -> 409", (await client.post("/integraciones/pago/webhook", headers=admin, json={"appointment_id": pago_cita_id})).status_code == 409)

        # ── Médico crea una orden y una receta para probar lab/farmacia ──
        await client.post(f"/medico/citas/{cita_id}/atencion", headers=medico, json={"motivo": "Control", "evolucion": "Estable", "diagnostico": "Sano"})
        order_id = (await client.post(f"/medico/citas/{cita_id}/orden-examen", headers=medico, json={"tipo": "laboratorio"})).json()["id"]
        presc = (await client.post(f"/medico/citas/{cita_id}/prescripcion", headers=medico, json={"items": [{"medicamento": "Paracetamol 500mg", "cantidad": "10", "indicaciones": "c/8h"}]})).json()
        presc_id = presc["prescripcion"]["id"]

        # ── Laboratorio ──
        r = await client.post("/integraciones/lab/webhook", headers=admin, json={"order_id": order_id, "resultado": {"nombre": "Hemograma", "valor": "normal"}})
        check("webhook de laboratorio publica el resultado -> 200 disponible", r.status_code == 200 and r.json()["estado"] == "disponible")
        examenes_desp = len((await client.get("/salud/examenes", headers=paciente)).json())
        check("el paciente ve la nueva orden con resultado en Mi Salud", examenes_desp == examenes_baseline + 1)
        check("médico NO dispara webhooks de proveedor -> 403", (await client.post("/integraciones/lab/webhook", headers=medico, json={"order_id": order_id, "resultado": {}})).status_code == 403)

        # ── Farmacia ──
        r = await client.post("/integraciones/farmacia/webhook", headers=admin, json={"prescription_id": presc_id, "estado": "en_camino"})
        check("webhook de farmacia registra el estado -> 200 en_camino", r.status_code == 200 and r.json()["estado"] == "en_camino")
        check("estado de farmacia inválido -> 400", (await client.post("/integraciones/farmacia/webhook", headers=admin, json={"prescription_id": presc_id, "estado": "xxx"})).status_code == 400)

        # ── Mapas ──
        r = await client.get("/integraciones/mapas/sucursales", headers=paciente, params={"lat": 19.4326, "lng": -99.1332})
        suc = r.json()
        check("mapas: devuelve sucursales ordenadas por cercanía", r.status_code == 200 and len(suc) >= 1 and suc[0]["distancia_km"] is not None and suc[0]["distancia_km"] < 1)

        # ── Push: gate deshabilitado -> habilitar -> entregar ──
        r = await client.post("/integraciones/push/suscribir", headers=paciente, json={"endpoint": "https://push.example/sub/abc"})
        check("paciente se suscribe a push -> 201", r.status_code == 201 and r.json()["estado"] == "activa")
        check("enviar push con conector deshabilitado -> 409", (await client.post("/integraciones/push/enviar", headers=paciente, json={"titulo": "Hola", "cuerpo": "Prueba"})).status_code == 409)

        # el admin habilita el conector push de la clínica
        integ = (await client.get("/admin/integraciones", headers=admin)).json()
        push_id = next(i["id"] for i in integ if i["tipo"] == "push")
        await client.patch(f"/admin/integraciones/{push_id}", headers=admin, json={"activo": True})
        r = await client.post("/integraciones/push/enviar", headers=paciente, json={"titulo": "Recordatorio", "cuerpo": "Tu cita es mañana"})
        check("con push habilitado, enviar -> 200 con 1 entrega", r.status_code == 200 and r.json()["entregas"] == 1)
        notis = (await client.get("/integraciones/push/mis-notificaciones", headers=paciente)).json()
        check("el paciente ve su notificación en el buzón", len(notis) == 1 and notis[0]["titulo"] == "Recordatorio")

        # ── La traza registró la actividad de los conectores ──
        est2 = (await client.get("/integraciones/estado", headers=admin)).json()
        tipos_evento = {e["tipo"] for e in est2["eventos_recientes"]}
        check("la traza de integraciones registró pago, lab, farmacia, whatsapp y push", {"pago", "lab", "farmacia", "whatsapp", "push"} <= tipos_evento)

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
