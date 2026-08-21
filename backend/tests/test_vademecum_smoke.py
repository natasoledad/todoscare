"""Smoke test · Vademécum + plantillas de receta (71.21).

Catálogo de medicamentos buscable + plantillas de receta reutilizables, con RBAC.

Run: `python -m tests.test_vademecum_smoke`.
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

        # ── vademécum buscable ──
        r = await client.get("/medico/vademecum?q=amox", headers=medico)
        results.append(("buscar 'amox' -> Amoxicilina", r.status_code == 200 and any("Amoxicilina" in m["nombre"] for m in r.json())))
        r = await client.get("/medico/vademecum?q=paracetamol", headers=medico)
        results.append(("buscar por principio activo", r.status_code == 200 and any(m["principio_activo"] == "Paracetamol" for m in r.json())))
        r = await client.get("/medico/vademecum", headers=medico)
        results.append(("catálogo sin query devuelve lista", r.status_code == 200 and len(r.json()) > 0))

        # ── plantillas de receta ──
        items = [
            {"medicamento": "Amoxicilina 500 mg", "cantidad": "21 comp", "indicaciones": "1 cada 8 h por 7 días"},
            {"medicamento": "Ibuprofeno 400 mg", "cantidad": "20 comp", "indicaciones": "1 cada 8 h con dolor"},
        ]
        r = await client.post("/medico/recetas-plantilla", headers=medico, json={"nombre": "Post-extracción", "items": items})
        t = r.json()
        results.append(("crear plantilla -> 201 con 2 ítems", r.status_code == 201 and len(t["items"]) == 2))
        tid = t["id"]

        r = await client.get("/medico/recetas-plantilla", headers=medico)
        results.append(("listar plantillas incluye la nueva", any(x["id"] == tid for x in r.json())))

        r = await client.patch(f"/medico/recetas-plantilla/{tid}", headers=medico, json={"items": items[:1]})
        results.append(("editar plantilla -> 1 ítem", r.status_code == 200 and len(r.json()["items"]) == 1))

        # ── RBAC ──
        r = await client.get("/medico/vademecum", headers=paciente)
        results.append(("paciente no accede al vademécum", r.status_code in (401, 403)))

        r = await client.delete(f"/medico/recetas-plantilla/{tid}", headers=medico)
        results.append(("borrar plantilla -> 204", r.status_code == 204))

    print("\n=== Vademécum + recetas (71.21) · smoke ===")
    ok = True
    for name, passed in results:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
        ok = ok and passed
    print("=== OK ===" if ok else "=== FALLÓ ===")
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
