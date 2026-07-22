"""Fase 2 smoke test: exercises every Rol Paciente endpoint end-to-end
against the real app + real Postgres — registro, onboarding, agenda
(including the double-booking rejection and cancel-frees-the-slot fix),
salud (exámenes, upload, dental, hospitalizaciones, QR emergencia +
audited access log), farmacia, and billetera. Also checks a couple of
cross-patient isolation cases. Run with:
`python -m tests.test_paciente_smoke`
"""

import asyncio
import io

import httpx

from app.main import app

PASSWORD = "Demo1234!"


async def main() -> None:
    transport = httpx.ASGITransport(app=app)
    results: list[tuple[str, bool]] = []

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # ---- registro ----
        r = await client.get("/clinics/public")
        clinic = r.json()[0]
        r = await client.get("/tyc/latest", params={"pais": clinic["pais"]})
        tyc_id = r.json()["id"]

        r = await client.post(
            "/patients/register",
            json={
                "nombre": "Beto Smoke",
                "rut": "11.111.111-1",
                "telefono": "+52 55 0000 0000",
                "direccion": "Calle Smoke 1",
                "correo": "beto.smoke@test.com",
                "password": "Passw0rd!",
                "clinic_id": clinic["id"],
                "tyc_version_id": tyc_id,
            },
        )
        results.append(("registro -> 201", r.status_code == 201))
        token = r.json()["access_token"]
        h = {"Authorization": f"Bearer {token}"}

        r = await client.get("/patients/me", headers=h)
        results.append(("me tras registro: Bronce/100pts/no onboarded", r.json()["nivel"] == "Bronce" and r.json()["wallet"]["puntos"] == 100 and not r.json()["onboarding_completado"]))

        # duplicate email -> 409
        r_dup = await client.post(
            "/patients/register",
            json={
                "nombre": "Beto Dup", "rut": "22.222.222-2", "telefono": "+52 55 1111 1111", "direccion": "Otra calle 2",
                "correo": "beto.smoke@test.com", "password": "Passw0rd!",
                "clinic_id": clinic["id"], "tyc_version_id": tyc_id,
            },
        )
        results.append(("registro duplicado -> 409", r_dup.status_code == 409))

        # ---- onboarding ----
        r = await client.post(
            "/patients/onboarding",
            headers=h,
            json={"answers": {"motivo": "Prevención", "seguro": "No"}, "dependents": [{"nombre": "Hijo 1"}, {"nombre": "Hijo 2"}]},
        )
        me = r.json()
        results.append(("onboarding -> 200, Plata, 2 dependientes", r.status_code == 200 and me["nivel"] == "Plata" and len(me["dependents"]) == 2))

        # ---- agenda ----
        r = await client.get("/agenda/servicios", headers=h)
        servicios = r.json()
        results.append(("agenda/servicios -> 7 servicios", len(servicios) == 7))
        cardio = next(s for s in servicios if s["nombre"] == "Cardiología")

        r = await client.get("/agenda/disponibilidad", params={"service_id": cardio["id"]}, headers=h)
        slots = r.json()
        results.append(("agenda/disponibilidad -> slots disponibles", len(slots) > 0))
        slot = slots[0]

        r = await client.post("/agenda/reservar", headers=h, json={"service_id": cardio["id"], "professional_id": slot["professional_id"], "inicio": slot["inicio"], "fin": slot["fin"]})
        results.append(("reservar -> 201", r.status_code == 201))
        cita_id = r.json()["id"]

        r_conflict = await client.post("/agenda/reservar", headers=h, json={"service_id": cardio["id"], "professional_id": slot["professional_id"], "inicio": slot["inicio"], "fin": slot["fin"]})
        results.append(("doble-reserva mismo slot -> 409", r_conflict.status_code == 409))

        r = await client.get("/agenda/mias", headers=h)
        results.append(("agenda/mias incluye la cita", any(c["id"] == cita_id for c in r.json())))

        r = await client.patch(f"/agenda/{cita_id}/cancelar", headers=h)
        results.append(("cancelar -> estado cancelada", r.json()["estado"] == "cancelada"))

        r_rebook = await client.post("/agenda/reservar", headers=h, json={"service_id": cardio["id"], "professional_id": slot["professional_id"], "inicio": slot["inicio"], "fin": slot["fin"]})
        results.append(("re-reservar el mismo slot tras cancelar -> 201", r_rebook.status_code == 201))

        # ---- salud ----
        r = await client.get("/salud/examenes", headers=h)
        results.append(("salud/examenes -> lista vacía para paciente nuevo", r.status_code == 200 and r.json() == []))

        files = {"file": ("resultado.pdf", io.BytesIO(b"contenido-falso-pdf"), "application/pdf")}
        r = await client.post("/salud/examenes/subir", headers=h, files=files)
        results.append(("subir examen -> 201, listo", r.status_code == 201 and r.json()["estado"] == "listo"))

        r = await client.get("/salud/examenes", headers=h)
        results.append(("salud/examenes ahora tiene 1", len(r.json()) == 1))

        r = await client.get("/salud/dental", headers=h)
        results.append(("salud/dental -> 200", r.status_code == 200))

        r = await client.get("/salud/hospitalizaciones", headers=h)
        results.append(("salud/hospitalizaciones -> lista vacía (paciente nuevo)", r.status_code == 200 and r.json() == []))

        r = await client.get("/salud/qr", headers=h)
        results.append(("salud/qr get-or-create -> 200 con token", r.status_code == 200 and len(r.json()["token"]) > 10))
        qr_token = r.json()["token"]

        # médico login para resolver el QR
        r = await client.post("/auth/login", json={"email": "medico.a@todoscare.dev", "password": PASSWORD})
        medico_token = r.json()["access_token"]
        medico_h = {"Authorization": f"Bearer {medico_token}"}

        r = await client.get(f"/salud/qr/resolver/{qr_token}", headers=medico_h)
        results.append(("médico resuelve QR -> 200", r.status_code == 200 and r.json()["patient_nombre"] == "Beto Smoke"))

        # paciente (no médico) NO puede resolver un QR ajeno
        r_denied = await client.get(f"/salud/qr/resolver/{qr_token}", headers=h)
        results.append(("paciente NO puede resolver QR (solo médico) -> 403", r_denied.status_code == 403))

        r = await client.get("/salud/qr/mis-accesos", headers=h)
        results.append(("qr/mis-accesos registra el acceso del médico", len(r.json()) == 1 and r.json()[0]["profesional_nombre"] == "Dra. Nátaly"))

        # ---- farmacia (paciente.a semilla SÍ tiene receta vigente) ----
        r = await client.post("/auth/login", json={"email": "paciente.a@todoscare.dev", "password": PASSWORD})
        camila_token = r.json()["access_token"]
        camila_h = {"Authorization": f"Bearer {camila_token}"}
        r = await client.get("/farmacia/medicamentos", headers=camila_h)
        results.append(("farmacia/medicamentos -> 2 medicamentos (seed)", r.status_code == 200 and len(r.json()) == 2))

        r = await client.get("/farmacia/medicamentos", headers=h)
        results.append(("farmacia/medicamentos paciente nuevo -> vacío", r.json() == []))

        # ---- billetera ----
        # 100 (registro) + 200 (onboarding) + 25*2 (2 dependientes) + 20 (examen subido) = 370
        r = await client.get("/billetera", headers=h)
        results.append(("billetera balance -> 370 pts (100+200+50+20)", r.json()["puntos"] == 370))

        r = await client.post("/billetera/canjear-puntos", headers=h, json={"puntos": 100})
        results.append(("canjear 100 pts -> +10 cashback", r.status_code == 200 and r.json()["puntos"] == 270 and abs(r.json()["cashback"] - 10.0) < 0.01))

        r_over = await client.post("/billetera/pagar-cashback", headers=h, json={"monto": 9999})
        results.append(("pagar con cashback insuficiente -> 400", r_over.status_code == 400))

        r = await client.post("/billetera/pagar-cashback", headers=h, json={"monto": 5})
        results.append(("pagar 5 de cashback -> ok", r.status_code == 200 and abs(r.json()["cashback"] - 5.0) < 0.01))

        r = await client.get("/billetera/movimientos", headers=h)
        results.append(("movimientos tiene >= 5 entradas", len(r.json()) >= 5))

        # ---- aislamiento entre pacientes ----
        r = await client.get("/agenda/mias", headers=camila_h)
        citas_camila = {c["id"] for c in r.json()}
        results.append(("Camila no ve la cita de Beto", cita_id not in citas_camila))

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
