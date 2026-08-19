"""Smoke test de reportería / BI (68).

Biblioteca de reportes (68.14), KPIs de agenda —ocupación, no-show (68.8/
68.10) y tiempo de espera (68.12)— y export a CSV UTF-8 (68.17).

Run: `python -m tests.test_reportes_smoke`.
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
        emp = await login(client, "empresa.a@todoscare.dev")
        pac = await login(client, "paciente.a@todoscare.dev")

        # biblioteca de reportes
        bib = (await client.get("/empresa/reportes", headers=emp)).json()
        check("Biblioteca tiene reportes", len(bib) >= 4 and any(r["categoria"] == "Agenda" for r in bib))

        # tomar una cita de hoy y pasarla por sala de espera -> atención (tiempo de espera)
        agenda = (await client.get("/empresa/agenda", headers=emp)).json()
        citas = agenda["citas"]
        check("Hay citas hoy en la agenda", len(citas) >= 1)
        c0 = citas[0]["id"]
        await client.patch(f"/empresa/citas/{c0}/estado", headers=emp, json={"estado": "en_sala_espera"})
        await client.patch(f"/empresa/citas/{c0}/estado", headers=emp, json={"estado": "en_atencion"})

        # crear una segunda cita (como paciente) y marcarla no-show
        servicios = (await client.get("/agenda/servicios", headers=pac)).json()
        cardio = next(s for s in servicios if s["nombre"] == "Cardiología")
        slots = (await client.get("/agenda/disponibilidad", params={"service_id": cardio["id"]}, headers=pac)).json()
        rv = await client.post("/agenda/reservar", headers=pac, json={"service_id": cardio["id"], "professional_id": slots[0]["professional_id"], "inicio": slots[0]["inicio"], "fin": slots[0]["fin"]})
        nueva = rv.json()["id"]
        r = await client.patch(f"/empresa/citas/{nueva}/estado", headers=emp, json={"estado": "no_show"})
        check("Marcar no-show -> 200", r.status_code == 200)

        # KPIs de agenda
        kpis = (await client.get("/empresa/reportes/agenda-kpis", headers=emp)).json()
        check("KPIs: total de citas > 0", kpis["total_citas"] >= 1)
        check("KPIs: al menos 1 no-show y tasa > 0", kpis["no_shows"] >= 1 and kpis["no_show_pct"] > 0)
        check("KPIs: ocupación > 0", kpis["ocupacion_pct"] > 0)
        check("KPIs: al menos una atención con espera medida", kpis["atendidas_con_espera"] >= 1)

        # export CSV agenda
        r = await client.get("/empresa/reportes/agenda/export", headers=emp)
        check("Export agenda -> 200 text/csv", r.status_code == 200 and "text/csv" in r.headers.get("content-type", ""))
        check("CSV con BOM y cabecera", r.text.startswith("﻿") and "Paciente" in r.text)
        check("CSV adjunto con filename", "attachment" in r.headers.get("content-disposition", ""))

        # export CSV no_show (solo inasistencias)
        r = await client.get("/empresa/reportes/no_show/export", headers=emp)
        check("Export no_show -> 200", r.status_code == 200 and "no_show" in r.headers.get("content-disposition", ""))

        # export finanzas
        r = await client.get("/empresa/reportes/gastos/export", headers=emp)
        check("Export gastos -> 200 con cabecera Monto", r.status_code == 200 and "Monto" in r.text)

        # reporte inexistente -> 404
        r = await client.get("/empresa/reportes/inexistente/export", headers=emp)
        check("Reporte inexistente -> 404", r.status_code == 404)

        # RBAC
        medico = await login(client, "medico.a@todoscare.dev")
        r = await client.get("/empresa/reportes/agenda-kpis", headers=medico)
        check("Médico NO ve reportes -> 403", r.status_code == 403)

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
