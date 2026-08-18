"""Smoke test de la agenda online pública (punto 60).

Flujo completo sin login: la clínica publica su agenda en /reservar/<slug>, un
paciente ve disponibilidad y deja una solicitud de hora; el personal (empresa)
la confirma —materializando la cita cuando el RUT corresponde a un paciente
registrado— o la rechaza.

Run: `python -m tests.test_agenda_online_smoke`.
"""

import asyncio
from datetime import datetime, timedelta, timezone

import httpx

from app.main import app

PASSWORD = "Demo1234!"
SLUG = "clinica-demo-a"
CAMILA_RUT = "18.245.301-K"


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
        emp = await login(client, "empresa.a@todoscare.dev")

        # La empresa habilita/afina la agenda online y confirma el slug.
        cfg = await client.put("/empresa/agenda-online/config", headers=emp, json={"slug": SLUG, "habilitada": True, "anticipacion_horas": 2, "ventana_dias": 60})
        check("Config agenda online -> 200", cfg.status_code == 200)
        check("Config expone la URL pública", cfg.json().get("reservable_url") == f"/reservar/{SLUG}")

        # Un bloque de disponibilidad futuro (mañana 10–13 UTC) para reservar.
        prof = (await client.get("/empresa/profesionales", headers=emp)).json()[0]
        branch = (await client.get("/empresa/sucursales", headers=emp)).json()[0]
        base = (datetime.now(timezone.utc) + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
        blk = await client.post("/empresa/agendas", headers=emp, json={
            "professional_id": prof["id"], "branch_id": branch["id"],
            "inicio": base.isoformat(), "fin": (base + timedelta(hours=3)).isoformat(),
        })
        check("Bloque futuro creado -> 201", blk.status_code == 201)

        # ---- vista pública (sin auth) ----
        pub = await client.get(f"/public/reservas/{SLUG}")
        check("Página pública -> 200", pub.status_code == 200)
        data = pub.json()
        check("Página pública habilitada con servicios", data["habilitada"] and len(data["servicios"]) > 0)
        service = data["servicios"][0]

        nope = await client.get("/public/reservas/no-existe")
        check("Slug inexistente -> 404", nope.status_code == 404)

        disp = await client.get(f"/public/reservas/{SLUG}/disponibilidad", params={"service_id": service["id"]})
        check("Disponibilidad -> 200", disp.status_code == 200)
        slots = [s for s in disp.json() if s["professional_id"] == prof["id"] and s["inicio"] >= base.isoformat()]
        check("Hay slots futuros para el profesional", len(slots) > 0)
        slot = slots[0]

        # ---- solicitud pública ----
        rv = await client.post(f"/public/reservas/{SLUG}", json={
            "service_id": service["id"], "professional_id": prof["id"],
            "inicio": slot["inicio"], "fin": slot["fin"],
            "nombre": "Camila Rodríguez", "rut": CAMILA_RUT, "telefono": "+56 9 1234 5678",
        })
        check("Reserva pública -> 201 pendiente", rv.status_code == 201 and rv.json()["estado"] == "pendiente")
        codigo = rv.json()["codigo"]

        est = await client.get(f"/public/reservas/{SLUG}/estado/{codigo}")
        check("Estado por código -> pendiente", est.status_code == 200 and est.json()["estado"] == "pendiente")

        # el mismo hueco ya no se ofrece / no se puede volver a pedir
        dup = await client.post(f"/public/reservas/{SLUG}", json={
            "service_id": service["id"], "professional_id": prof["id"],
            "inicio": slot["inicio"], "fin": slot["fin"], "nombre": "Otro Paciente",
        })
        check("Reservar el mismo hueco -> 409", dup.status_code == 409)

        # ---- gestión por el personal ----
        pend = (await client.get("/empresa/solicitudes", headers=emp, params={"estado": "pendiente"})).json()
        mine = next((s for s in pend if s["codigo"] == codigo), None)
        check("La solicitud aparece pendiente en el panel", mine is not None)

        conf = await client.post(f"/empresa/solicitudes/{mine['id']}/confirmar", headers=emp)
        check("Confirmar (RUT de paciente registrado) -> 200 + cita", conf.status_code == 200 and conf.json()["estado"] == "confirmada" and conf.json()["appointment_id"])

        est2 = await client.get(f"/public/reservas/{SLUG}/estado/{codigo}")
        check("Estado tras confirmar -> confirmada", est2.json()["estado"] == "confirmada")

        # una segunda solicitud con RUT no registrado no se puede materializar
        slot2 = slots[1] if len(slots) > 1 else None
        if slot2:
            rv2 = await client.post(f"/public/reservas/{SLUG}", json={
                "service_id": service["id"], "professional_id": prof["id"],
                "inicio": slot2["inicio"], "fin": slot2["fin"], "nombre": "Desconocido Pérez", "rut": "9.999.999-9",
            })
            sid2 = (await client.get("/empresa/solicitudes", headers=emp, params={"estado": "pendiente"})).json()
            req2 = next(s for s in sid2 if s["codigo"] == rv2.json()["codigo"])
            bad = await client.post(f"/empresa/solicitudes/{req2['id']}/confirmar", headers=emp)
            check("Confirmar sin paciente registrado -> 409", bad.status_code == 409)
            rej = await client.post(f"/empresa/solicitudes/{req2['id']}/rechazar", headers=emp)
            check("Rechazar solicitud -> 200 rechazada", rej.status_code == 200 and rej.json()["estado"] == "rechazada")

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
