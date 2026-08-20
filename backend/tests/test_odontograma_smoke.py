"""Smoke test · Odontograma con caras y estados dx/tx (70.11).

Catálogo de marcas + registro por pieza con caras (V/L/M/D/O), diagnóstico y
tratamiento por cara, estado de la pieza completa, validación y RBAC.

Run: `python -m tests.test_odontograma_smoke`.
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
        r = await client.get("/medico/odontograma/catalogo", headers=medico)
        cat = r.json()
        results.append(("catálogo: 5 caras", r.status_code == 200 and len(cat["caras"]) == 5))
        results.append(("catálogo: dx, tx y estados de pieza", len(cat["diagnosticos"]) > 0 and len(cat["tratamientos"]) > 0 and len(cat["pieza_estados"]) > 0))

        cita = next((c for c in (await client.get("/medico/agenda", headers=medico)).json() if "Camila" in c["paciente_nombre"]), None)
        pid = cita["patient_id"]

        # ── guardar odontograma rico ──
        payload = {"piezas": {
            "16": {"caras": {"O": {"dx": "caries", "tx": "obturacion", "tx_estado": "planificado"}}},
            "21": {"pieza": "ausente"},
            "11": {"caras": {"V": {"dx": "mancha"}}},
            "17": {},  # vacía: no debe persistirse
        }}
        r = await client.put(f"/medico/pacientes/{pid}/odontograma", headers=medico, json=payload)
        piezas = r.json()["piezas"]
        results.append(("guardar -> 200", r.status_code == 200))
        results.append(("cara O de la 16 con dx+tx+estado", piezas.get("16", {}).get("caras", {}).get("O") == {"dx": "caries", "tx": "obturacion", "tx_estado": "planificado"}))
        results.append(("pieza 21 completa = ausente", piezas.get("21", {}).get("pieza") == "ausente"))
        results.append(("pieza vacía 17 no se persiste", "17" not in piezas))

        # ── persistencia vía ficha ──
        ficha = (await client.get(f"/medico/pacientes/{pid}/ficha", headers=medico)).json()
        results.append(("ficha refleja el odontograma", ficha["odontograma"].get("11", {}).get("caras", {}).get("V", {}).get("dx") == "mancha"))

        # ── validaciones ──
        r = await client.put(f"/medico/pacientes/{pid}/odontograma", headers=medico, json={"piezas": {"99": {"pieza": "sano"}}})
        results.append(("pieza FDI inválida -> 400", r.status_code == 400))
        r = await client.put(f"/medico/pacientes/{pid}/odontograma", headers=medico, json={"piezas": {"16": {"caras": {"X": {"dx": "caries"}}}}})
        results.append(("cara inválida -> 400", r.status_code == 400))
        r = await client.put(f"/medico/pacientes/{pid}/odontograma", headers=medico, json={"piezas": {"16": {"caras": {"O": {"dx": "inexistente"}}}}})
        results.append(("diagnóstico inválido -> 400", r.status_code == 400))

        # ── compatibilidad legacy {estado} ──
        r = await client.put(f"/medico/pacientes/{pid}/odontograma", headers=medico, json={"piezas": {"15": {"estado": "tratada"}}})
        results.append(("legacy {estado: tratada} -> 200", r.status_code == 200 and r.json()["piezas"].get("15", {}).get("estado") == "tratada"))

        # ── RBAC ──
        r = await client.put(f"/medico/pacientes/{pid}/odontograma", headers=paciente, json={"piezas": {"16": {"pieza": "sano"}}})
        results.append(("paciente no edita el odontograma", r.status_code in (401, 403)))

    print("\n=== Odontograma (70.11) · smoke ===")
    ok = True
    for name, passed in results:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
        ok = ok and passed
    print("=== OK ===" if ok else "=== FALLÓ ===")
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
