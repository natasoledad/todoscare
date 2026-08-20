"""Smoke test · Diagnóstico CIE-10 (71.20).

Catálogo buscable + diagnósticos estructurados (principal/secundario) por
paciente atendido, con RBAC.

Run: `python -m tests.test_cie10_smoke`.
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
        paciente = await login(client, "paciente.a@todoscare.dev")

        # ── catálogo buscable ──
        r = await client.get("/medico/cie10?q=caries", headers=medico)
        hits = r.json()
        results.append(("buscar 'caries' -> resultados con código K02", r.status_code == 200 and any(h["codigo"].startswith("K02") for h in hits)))
        r = await client.get("/medico/cie10?q=K05.3", headers=medico)
        results.append(("buscar por código exacto K05.3", r.status_code == 200 and any(h["codigo"] == "K05.3" for h in r.json())))
        r = await client.get("/medico/cie10", headers=medico)
        results.append(("catálogo sin query devuelve lista", r.status_code == 200 and len(r.json()) > 0))

        # ── paciente atendido ──
        cita = next((c for c in (await client.get("/medico/agenda", headers=medico)).json() if "Camila" in c["paciente_nombre"]), None)
        pid = cita["patient_id"]

        # ── agregar principal + secundario ──
        r = await client.post(f"/medico/pacientes/{pid}/diagnosticos", headers=medico, json={"codigo": "K02.1", "tipo": "principal", "observacion": "Molar inferior"})
        dx = r.json()
        results.append(("agregar principal K02.1 -> 201 con descripción", r.status_code == 201 and dx["codigo"] == "K02.1" and "dentina" in dx["descripcion"].lower()))
        dx_id = dx["id"]
        r = await client.post(f"/medico/pacientes/{pid}/diagnosticos", headers=medico, json={"codigo": "K05.1", "tipo": "secundario"})
        results.append(("agregar secundario K05.1 -> 201", r.status_code == 201 and r.json()["tipo"] == "secundario"))

        # ── código inexistente -> 400 ──
        r = await client.post(f"/medico/pacientes/{pid}/diagnosticos", headers=medico, json={"codigo": "ZZ9.9", "tipo": "principal"})
        results.append(("código inexistente -> 400", r.status_code == 400))

        # ── listar ──
        r = await client.get(f"/medico/pacientes/{pid}/diagnosticos", headers=medico)
        results.append(("listar diagnósticos -> 2", r.status_code == 200 and len(r.json()) == 2))

        # ── RBAC: otro médico que no atiende no accede ──
        r = await client.get(f"/medico/pacientes/{pid}/diagnosticos", headers=otro)
        results.append(("médico que no atiende no ve diagnósticos", r.status_code in (403, 404)))
        r = await client.get("/medico/cie10", headers=paciente)
        results.append(("paciente no accede al catálogo médico", r.status_code in (401, 403)))

        # ── quitar ──
        r = await client.delete(f"/medico/diagnosticos/{dx_id}", headers=medico)
        results.append(("quitar diagnóstico -> 204", r.status_code == 204))
        r = await client.get(f"/medico/pacientes/{pid}/diagnosticos", headers=medico)
        results.append(("tras quitar queda 1", r.status_code == 200 and len(r.json()) == 1))

    print("\n=== Diagnóstico CIE-10 (71.20) · smoke ===")
    ok = True
    for name, passed in results:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
        ok = ok and passed
    print("=== OK ===" if ok else "=== FALLÓ ===")
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
