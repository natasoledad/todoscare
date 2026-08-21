"""Smoke test · GES + campos demográficos chilenos (69.14 · 69.17).

Previsión (Fonasa/Isapre), tramo, nacionalidad, comuna y GES del paciente,
editables por el tratante y visibles en la ficha, con validación y RBAC.

Run: `python -m tests.test_datos_cl_smoke`.
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
        medico = await login(client, "medico.a@todoscare.dev")
        otro = await login(client, "medico.b@todoscare.dev")   # no atiende a Camila

        cita = next((c for c in (await client.get("/medico/agenda", headers=medico)).json() if "Camila" in c["paciente_nombre"]), None)
        pid = cita["patient_id"]

        # ── vacío al inicio ──
        r = await client.get(f"/medico/pacientes/{pid}/ficha", headers=medico)
        results.append(("ficha trae bloque datos_cl", r.status_code == 200 and "datos_cl" in r.json() and r.json()["datos_cl"]["ges"] is False))

        # ── setear Fonasa + tramo + comuna + GES ──
        r = await client.patch(f"/medico/pacientes/{pid}/datos-cl", headers=medico, json={
            "prevision": "fonasa", "tramo_fonasa": "b", "nacionalidad": "Chilena", "comuna": "Providencia",
            "ges": True, "ges_detalle": "Diabetes Mellitus tipo 2",
        })
        d = r.json()
        results.append(("guardar datos -> 200", r.status_code == 200))
        results.append(("previsión Fonasa guardada", d["prevision"] == "fonasa"))
        results.append(("tramo normalizado a mayúscula (B)", d["tramo_fonasa"] == "B"))
        results.append(("GES activo con patología", d["ges"] is True and "Diabetes" in d["ges_detalle"]))

        # ── refleja en la ficha ──
        r = await client.get(f"/medico/pacientes/{pid}/ficha", headers=medico)
        dc = r.json()["datos_cl"]
        results.append(("la ficha refleja comuna y GES", dc["comuna"] == "Providencia" and dc["ges"] is True))

        # ── validaciones ──
        r = await client.patch(f"/medico/pacientes/{pid}/datos-cl", headers=medico, json={"prevision": "otra"})
        results.append(("previsión inválida -> 400", r.status_code == 400))
        r = await client.patch(f"/medico/pacientes/{pid}/datos-cl", headers=medico, json={"tramo_fonasa": "Z"})
        results.append(("tramo inválido -> 400", r.status_code == 400))

        # ── cambiar a Isapre con nombre ──
        r = await client.patch(f"/medico/pacientes/{pid}/datos-cl", headers=medico, json={"prevision": "isapre", "prevision_nombre": "Cruz Blanca"})
        results.append(("cambiar a Isapre con nombre", r.status_code == 200 and r.json()["prevision"] == "isapre" and r.json()["prevision_nombre"] == "Cruz Blanca"))

        # ── RBAC: otro médico que no atiende ──
        r = await client.patch(f"/medico/pacientes/{pid}/datos-cl", headers=otro, json={"comuna": "X"})
        results.append(("médico que no atiende no edita -> 403/404", r.status_code in (403, 404)))

    print("\n=== GES + campos chilenos (69.14 · 69.17) · smoke ===")
    ok = True
    for name, passed in results:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
        ok = ok and passed
    print("=== OK ===" if ok else "=== FALLÓ ===")
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
