"""Smoke test de medios de pago configurables (66).

Contra la BD seedeada con `app.seed`, en el portal Empresa:
  · CRUD del catálogo con propiedades (retención %, facturable, devolución, cuotas).
  · Validación de retención fuera de rango.
  · RBAC: un médico no administra medios de pago.

Run: `python -m tests.test_medios_pago_smoke`.
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

        r = await client.post("/empresa/medios-pago", headers=emp, json={"nombre": "Crédito", "retencion_pct": 0.02, "facturable": True, "acepta_cuotas": True})
        check("Medio: alta -> 201", r.status_code == 201)
        m = r.json() if r.status_code == 201 else {}
        check("Medio: guarda retención y cuotas", abs(m.get("retencion_pct", 0) - 0.02) < 0.0001 and m.get("acepta_cuotas") is True and m.get("facturable") is True)
        mid = m.get("id")

        bad = await client.post("/empresa/medios-pago", headers=emp, json={"nombre": "Malo", "retencion_pct": 1.5})
        check("Medio: retención > 1 -> 422", bad.status_code == 422)

        lst = (await client.get("/empresa/medios-pago", headers=emp)).json()
        check("Medio: aparece en el listado", any(x["id"] == mid for x in lst))

        re = await client.patch(f"/empresa/medios-pago/{mid}", headers=emp, json={"permite_devolucion": True, "activo": False})
        check("Medio: edición -> 200", re.status_code == 200 and re.json().get("permite_devolucion") is True and re.json().get("activo") is False)

        rdel = await client.delete(f"/empresa/medios-pago/{mid}", headers=emp)
        check("Medio: baja -> 204", rdel.status_code == 204)
        lst2 = (await client.get("/empresa/medios-pago", headers=emp)).json()
        check("Medio: ya no aparece tras la baja", not any(x["id"] == mid for x in lst2))

        med = await login(client, "medico.a@todoscare.dev")
        r403 = await client.post("/empresa/medios-pago", headers=med, json={"nombre": "X"})
        check("RBAC: médico NO administra medios de pago -> 403", r403.status_code == 403)

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
