"""Tanda 4 smoke test: listado de pacientes con deudas + panel de desempeño,
contra el app real + Postgres real.

Cubre: listar pacientes con nº de tratamientos y deuda (calculada del ledger
vs. cobros de caja); habilitar/deshabilitar paciente y su filtro; el panel de
desempeño (ventas, por profesional con monto a pagar, por grupo de servicio con
ticket medio); y aislamiento por rol. Run: `python -m tests.test_desempeno_smoke`.
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
    period = datetime.now(timezone.utc).strftime("%Y-%m")

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        empresa = await login(client, "empresa.a@todoscare.dev")
        medico = await login(client, "medico.a@todoscare.dev")

        # ---- listado de pacientes con deuda ----
        r = await client.get("/empresa/pacientes", headers=empresa)
        results.append(("listar pacientes -> 200", r.status_code == 200))
        camila = next((p for p in r.json() if "Camila" in p["nombre"]), None)
        results.append(("aparece Camila en el listado", camila is not None))
        results.append(("trae nº de tratamientos y deuda", camila is not None and "n_tratamientos" in camila and "deuda" in camila))
        results.append(("Camila tiene deuda > 0 (facturada por el seed, sin cobros)", bool(camila and camila["deuda"] > 0)))
        pid = camila["id"]

        # ---- habilitar / deshabilitar ----
        r = await client.patch(f"/empresa/pacientes/{pid}/estado", headers=empresa, json={"activo": False})
        results.append(("deshabilitar paciente -> 200 activo=false", r.status_code == 200 and r.json()["activo"] is False))

        r = await client.get("/empresa/pacientes?activo=false", headers=empresa)
        results.append(("el filtro activo=false lo incluye", any(p["id"] == pid for p in r.json())))
        r = await client.get("/empresa/pacientes?activo=true", headers=empresa)
        results.append(("el filtro activo=true lo excluye", all(p["id"] != pid for p in r.json())))

        r = await client.patch(f"/empresa/pacientes/{pid}/estado", headers=empresa, json={"activo": True})
        results.append(("re-habilitar paciente -> 200 activo=true", r.status_code == 200 and r.json()["activo"] is True))

        # ---- generar una atención cerrada (ingreso + split) para el panel ----
        r = await client.get("/medico/agenda", headers=medico)
        cita = next((c for c in r.json() if "Camila" in c["paciente_nombre"]), None)
        if cita and cita["estado"] not in ("completada", "cancelada", "no_show"):
            await client.post(f"/medico/citas/{cita['id']}/cerrar", headers=medico)

        # ---- panel de desempeño ----
        r = await client.get(f"/empresa/desempeno?period={period}", headers=empresa)
        results.append(("panel de desempeño -> 200", r.status_code == 200))
        d = r.json()
        results.append(("ventas del período > 0", d["ventas"] > 0))
        results.append(("hay desglose por profesional", len(d["por_profesional"]) >= 1))
        prof = next((p for p in d["por_profesional"] if "Nátaly" in p["nombre"] or "Nataly" in p["nombre"]), d["por_profesional"][0] if d["por_profesional"] else None)
        results.append(("el profesional tiene monto a pagar > 0 (split)", bool(prof and prof["a_pagar"] > 0)))
        results.append(("el profesional tiene ventas > 0", bool(prof and prof["ventas"] > 0)))
        results.append(("hay desglose por grupo de servicio", len(d["por_grupo"]) >= 1))
        results.append(("el ticket medio se calcula (>0)", d["ticket_medio"] > 0))

        # ---- aislamiento por rol ----
        r = await client.get("/empresa/pacientes", headers=medico)
        results.append(("médico NO lista pacientes de empresa -> 403", r.status_code == 403))

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
