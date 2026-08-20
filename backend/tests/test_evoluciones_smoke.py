"""Smoke test · Evoluciones con doble firma + anulación auditada (70.6).

El tratante escribe y firma la evolución; un segundo profesional la co-firma;
la anulación no borra, marca anulada con motivo/quién/cuándo.

Run: `python -m tests.test_evoluciones_smoke`.
"""

import asyncio

import httpx

from app.main import app

PASSWORD = "Demo1234!"
FIRMA = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="


async def login(client: httpx.AsyncClient, email: str) -> dict:
    r = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def main() -> None:
    transport = httpx.ASGITransport(app=app)
    results: list[tuple[str, bool]] = []

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        medico = await login(client, "medico.a@todoscare.dev")      # tratante de Camila
        medico_b = await login(client, "medico.b@todoscare.dev")    # otro profesional de la misma clínica
        paciente = await login(client, "paciente.a@todoscare.dev")

        # el tratante registra su firma (para estampar la firma del tratante)
        await client.put("/medico/mi-firma", headers=medico, json={"firma": FIRMA})

        cita = next((c for c in (await client.get("/medico/agenda", headers=medico)).json() if "Camila" in c["paciente_nombre"]), None)
        pid = cita["patient_id"]

        # ── crear evolución (firma del tratante) ──
        r = await client.post(f"/medico/pacientes/{pid}/evoluciones", headers=medico, json={"texto": "Paciente evoluciona favorablemente."})
        e = r.json()
        results.append(("crear evolución -> 201 firmada por el tratante", r.status_code == 201 and e["firmado_at"] and e["autor_nombre"] and e["estado"] == "vigente"))
        results.append(("estampa la firma manuscrita del tratante", e["firma_tratante"] == FIRMA))
        eid = e["id"]

        # ── el autor NO puede co-firmar su propia evolución ──
        r = await client.post(f"/medico/evoluciones/{eid}/cofirmar", headers=medico)
        results.append(("autor no puede co-firmar su evolución -> 400", r.status_code == 400))

        # ── segundo profesional co-firma ──
        r = await client.post(f"/medico/evoluciones/{eid}/cofirmar", headers=medico_b)
        results.append(("co-firma de otro profesional -> 200", r.status_code == 200 and r.json()["cofirmado_at"] and r.json()["cofirmado_por_nombre"]))

        # ── no se puede co-firmar dos veces ──
        r = await client.post(f"/medico/evoluciones/{eid}/cofirmar", headers=medico_b)
        results.append(("doble co-firma -> 400", r.status_code == 400))

        # ── paciente no accede a las evoluciones del médico ──
        r = await client.get(f"/medico/pacientes/{pid}/evoluciones", headers=paciente)
        results.append(("paciente no lista evoluciones -> 401/403", r.status_code in (401, 403)))

        # ── anulación auditada ──
        r = await client.patch(f"/medico/evoluciones/{eid}/anular", headers=medico, json={"motivo": "Registrada en el paciente equivocado"})
        an = r.json()
        results.append(("anular -> estado anulada con motivo/quién", r.status_code == 200 and an["estado"] == "anulada" and an["motivo_anulacion"] and an["anulado_por_nombre"]))
        results.append(("la anulación conserva el texto (no borra)", an["texto"] == "Paciente evoluciona favorablemente."))

        # ── no se re-anula ──
        r = await client.patch(f"/medico/evoluciones/{eid}/anular", headers=medico, json={"motivo": "otra vez"})
        results.append(("re-anular -> 400", r.status_code == 400))

        # ── sigue listándose (anulada, no desaparece) + se puede escribir una nueva ──
        r = await client.post(f"/medico/pacientes/{pid}/evoluciones", headers=medico, json={"texto": "Corrección: evolución del paciente correcto."})
        results.append(("nueva evolución -> 201", r.status_code == 201))
        r = await client.get(f"/medico/pacientes/{pid}/evoluciones", headers=medico)
        lst = r.json()
        results.append(("listado incluye la anulada y la nueva (2)", len(lst) == 2 and any(x["estado"] == "anulada" for x in lst) and any(x["estado"] == "vigente" for x in lst)))

    print("\n=== Evoluciones doble firma + anulación (70.6) · smoke ===")
    ok = True
    for name, passed in results:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
        ok = ok and passed
    print("=== OK ===" if ok else "=== FALLÓ ===")
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
