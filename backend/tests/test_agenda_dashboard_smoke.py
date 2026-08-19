"""Smoke test del dashboard de conversión de la agenda online (60.12).

Registra visitas a la página pública, genera solicitudes y confirma una;
el dashboard reporta el embudo visitas→solicitudes→confirmadas y sus tasas.

Run: `python -m tests.test_agenda_dashboard_smoke`.
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
        await client.put("/empresa/agenda-online/config", headers=emp, json={"slug": SLUG, "habilitada": True, "anticipacion_horas": 2, "ventana_dias": 60})

        # dashboard inicial (sin actividad)
        d0 = (await client.get("/empresa/agenda-online/dashboard", headers=emp)).json()
        check("Dashboard arranca en cero", d0["visitas"] == 0 and d0["solicitudes"] == 0)

        # 3 visitas a la página pública
        for _ in range(3):
            r = await client.get(f"/public/reservas/{SLUG}")
            assert r.status_code == 200
        d1 = (await client.get("/empresa/agenda-online/dashboard", headers=emp)).json()
        check("Registra 3 visitas", d1["visitas"] == 3)

        # crear un bloque futuro y hacer 1 solicitud
        prof = (await client.get("/empresa/profesionales", headers=emp)).json()[0]
        branch = (await client.get("/empresa/sucursales", headers=emp)).json()[0]
        base = (datetime.now(timezone.utc) + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
        await client.post("/empresa/agendas", headers=emp, json={"professional_id": prof["id"], "branch_id": branch["id"], "inicio": base.isoformat(), "fin": (base + timedelta(hours=3)).isoformat()})
        data = (await client.get(f"/public/reservas/{SLUG}")).json()  # visita #4
        service = data["servicios"][0]
        slots = [s for s in (await client.get(f"/public/reservas/{SLUG}/disponibilidad", params={"service_id": service["id"]})).json() if s["professional_id"] == prof["id"] and s["inicio"] >= base.isoformat()]
        rv = await client.post(f"/public/reservas/{SLUG}", json={"service_id": service["id"], "professional_id": prof["id"], "inicio": slots[0]["inicio"], "fin": slots[0]["fin"], "nombre": "Camila Rodríguez", "rut": CAMILA_RUT})
        check("Solicitud creada", rv.status_code == 201)

        d2 = (await client.get("/empresa/agenda-online/dashboard", headers=emp)).json()
        check("Dashboard: 4 visitas, 1 solicitud, 1 pendiente", d2["visitas"] == 4 and d2["solicitudes"] == 1 and d2["pendientes"] == 1)
        check("Tasa de conversión = 1/4 = 0.25", abs(d2["tasa_conversion"] - 0.25) < 1e-6)
        check("Tasa de confirmación = 0 (nada confirmado aún)", d2["tasa_confirmacion"] == 0)

        # confirmar la solicitud
        pend = (await client.get("/empresa/solicitudes", headers=emp, params={"estado": "pendiente"})).json()
        req = next(s for s in pend if s["codigo"] == rv.json()["codigo"])
        await client.post(f"/empresa/solicitudes/{req['id']}/confirmar", headers=emp)

        d3 = (await client.get("/empresa/agenda-online/dashboard", headers=emp)).json()
        check("Dashboard tras confirmar: 1 confirmada", d3["confirmadas"] == 1)
        check("Tasa de confirmación = 1/1 = 1.0", abs(d3["tasa_confirmacion"] - 1.0) < 1e-6)

        # RBAC
        medico = await login(client, "medico.a@todoscare.dev")
        r = await client.get("/empresa/agenda-online/dashboard", headers=medico)
        check("Médico NO ve el dashboard -> 403", r.status_code == 403)

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
