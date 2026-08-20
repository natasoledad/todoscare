"""Smoke test · Periodontograma completo (70.5).

Registro por pieza con hasta 6 sitios (mv/v/dv/mp/p/dp), profundidad de sondaje,
recesión y sangrado por sitio, más movilidad y furca; con validación, histórico
de tomas, catálogo, compatibilidad hacia atrás y RBAC.

Run: `python -m tests.test_periodontograma_smoke`.
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
        paciente = await login(client, "paciente.a@todoscare.dev")

        # ── catálogo ──
        r = await client.get("/medico/periodontograma/catalogo", headers=medico)
        cat = r.json()
        results.append(("catálogo: 6 sitios y ps_max 15", r.status_code == 200 and len(cat["sitios"]) == 6 and cat["ps_max"] == 15))

        cita = next((c for c in (await client.get("/medico/agenda", headers=medico)).json() if "Camila" in c["paciente_nombre"]), None)
        pid = cita["patient_id"]

        # ── toma completa (sitios + movilidad + furca) ──
        datos = {
            "1.6": {"movilidad": 1, "furca": 0, "sitios": {
                "mv": {"ps": 4, "rec": 1, "sangrado": True}, "v": {"ps": 3}, "dv": {"ps": 5, "sangrado": True},
            }},
            "2.1": {"ps": 2, "sangrado": False},   # compat: shape simple
        }
        r = await client.post(f"/medico/pacientes/{pid}/periodontograma", headers=medico, json={"datos": datos, "notas": "Sondaje completo"})
        out = r.json()
        results.append(("guardar toma completa -> 201", r.status_code == 201))
        results.append(("sitio mv de la 1.6 con ps+rec+sangrado", out["datos"]["1.6"]["sitios"]["mv"] == {"ps": 4, "rec": 1, "sangrado": True}))
        results.append(("movilidad de la 1.6 registrada", out["datos"]["1.6"]["movilidad"] == 1))
        results.append(("compat: pieza 2.1 con shape simple", out["datos"]["2.1"]["ps"] == 2))

        # ── histórico ──
        r = await client.post(f"/medico/pacientes/{pid}/periodontograma", headers=medico, json={"datos": {"1.6": {"ps": 3}}})
        results.append(("segunda toma incrementa histórico", r.status_code == 201 and r.json()["tomas_anteriores"] == 1))
        r = await client.get(f"/medico/pacientes/{pid}/periodontograma", headers=medico)
        results.append(("GET devuelve la última toma", r.status_code == 200 and r.json()["tomas_anteriores"] == 1))

        # ── validaciones ──
        r = await client.post(f"/medico/pacientes/{pid}/periodontograma", headers=medico, json={"datos": {"9.9": {"ps": 3}}})
        results.append(("pieza FDI inválida -> 400", r.status_code == 400))
        r = await client.post(f"/medico/pacientes/{pid}/periodontograma", headers=medico, json={"datos": {"1.6": {"sitios": {"xx": {"ps": 3}}}}})
        results.append(("sitio inválido -> 400", r.status_code == 400))
        r = await client.post(f"/medico/pacientes/{pid}/periodontograma", headers=medico, json={"datos": {"1.6": {"sitios": {"mv": {"ps": 99}}}}})
        results.append(("profundidad fuera de rango -> 400", r.status_code == 400))
        r = await client.post(f"/medico/pacientes/{pid}/periodontograma", headers=medico, json={"datos": {"1.6": {"movilidad": 5}}})
        results.append(("movilidad fuera de rango -> 400", r.status_code == 400))

        # ── RBAC ──
        r = await client.post(f"/medico/pacientes/{pid}/periodontograma", headers=paciente, json={"datos": {"1.6": {"ps": 3}}})
        results.append(("paciente no registra periodontograma", r.status_code in (401, 403)))

    print("\n=== Periodontograma completo (70.5) · smoke ===")
    ok = True
    for name, passed in results:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
        ok = ok and passed
    print("=== OK ===" if ok else "=== FALLÓ ===")
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
