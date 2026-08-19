"""Smoke test del prepago al agendar (61.7).

Con prepago exigido por la clínica, la solicitud pública nace 'requiere
prepago'; sin el pago (hookpoint simulado) el personal no puede confirmarla;
tras prepagar, se confirma normalmente.

Run: `python -m tests.test_prepago_smoke`.
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


async def reservar(client, prof, service, base) -> dict:
    slots = [s for s in (await client.get(f"/public/reservas/{SLUG}/disponibilidad", params={"service_id": service["id"]})).json()
             if s["professional_id"] == prof["id"] and s["inicio"] >= base.isoformat()]
    return slots[0]


async def main() -> None:
    results: list[tuple[str, bool]] = []

    def check(name: str, ok: bool) -> None:
        results.append((name, ok))

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        emp = await login(client, "empresa.a@todoscare.dev")
        cfg = await client.put("/empresa/agenda-online/config", headers=emp, json={
            "slug": SLUG, "habilitada": True, "anticipacion_horas": 2, "ventana_dias": 60,
            "requiere_prepago": True, "monto_prepago": 5000,
        })
        check("Config con prepago -> 200", cfg.status_code == 200 and cfg.json()["requiere_prepago"] and cfg.json()["monto_prepago"] == 5000)

        prof = (await client.get("/empresa/profesionales", headers=emp)).json()[0]
        branch = (await client.get("/empresa/sucursales", headers=emp)).json()[0]
        base = (datetime.now(timezone.utc) + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
        await client.post("/empresa/agendas", headers=emp, json={"professional_id": prof["id"], "branch_id": branch["id"], "inicio": base.isoformat(), "fin": (base + timedelta(hours=4)).isoformat()})
        data = (await client.get(f"/public/reservas/{SLUG}")).json()
        service = data["servicios"][0]

        slot = await reservar(client, prof, service, base)
        rv = await client.post(f"/public/reservas/{SLUG}", json={"service_id": service["id"], "professional_id": prof["id"], "inicio": slot["inicio"], "fin": slot["fin"], "nombre": "Camila Rodríguez", "rut": CAMILA_RUT})
        check("Reserva nace requiriendo prepago (5000, no pagado)", rv.status_code == 201 and rv.json()["prepago_requerido"] and rv.json()["prepago_monto"] == 5000 and rv.json()["prepagado"] is False)
        codigo = rv.json()["codigo"]

        # el personal ve la solicitud con prepago pendiente
        pend = (await client.get("/empresa/solicitudes", headers=emp, params={"estado": "pendiente"})).json()
        req = next(s for s in pend if s["codigo"] == codigo)
        check("La solicitud muestra prepago requerido y no pagado", req["prepago_requerido"] and not req["prepagado"])

        # confirmar sin prepago -> 409
        bad = await client.post(f"/empresa/solicitudes/{req['id']}/confirmar", headers=emp)
        check("Confirmar sin prepago -> 409", bad.status_code == 409)

        # prepago (hookpoint público simulado)
        pp = await client.post(f"/public/reservas/{SLUG}/prepago/{codigo}")
        check("Prepago -> 200 pagado con referencia", pp.status_code == 200 and pp.json()["prepagado"] and pp.json()["ref"])
        # prepagar dos veces -> 400
        pp2 = await client.post(f"/public/reservas/{SLUG}/prepago/{codigo}")
        check("Prepagar dos veces -> 400", pp2.status_code == 400)

        # ahora sí confirma
        ok = await client.post(f"/empresa/solicitudes/{req['id']}/confirmar", headers=emp)
        check("Confirmar tras prepago -> 200 con cita", ok.status_code == 200 and ok.json()["appointment_id"])

        # sin prepago requerido: prepagar una reserva normal -> 400
        await client.put("/empresa/agenda-online/config", headers=emp, json={"requiere_prepago": False})
        slot2 = await reservar(client, prof, service, base)
        rv2 = await client.post(f"/public/reservas/{SLUG}", json={"service_id": service["id"], "professional_id": prof["id"], "inicio": slot2["inicio"], "fin": slot2["fin"], "nombre": "Otro", "rut": "9.999.999-9"})
        check("Reserva sin prepago no lo requiere", rv2.json()["prepago_requerido"] is False)
        bad2 = await client.post(f"/public/reservas/{SLUG}/prepago/{rv2.json()['codigo']}")
        check("Prepagar una reserva sin prepago -> 400", bad2.status_code == 400)

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
