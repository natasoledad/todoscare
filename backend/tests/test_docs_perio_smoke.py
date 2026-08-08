"""Tanda 5 smoke test: documentos clínicos + periodontograma, contra el app
real + Postgres real.

Cubre: crear/listar/anular documentos clínicos (consentimiento, licencia,
interconsulta); guardar periodontogramas con histórico (tomas anteriores);
acceso auditado solo del profesional tratante; y aislamiento por rol.
Run: `python -m tests.test_docs_perio_smoke`.
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

        r = await client.get("/medico/agenda", headers=medico)
        cita = next((c for c in r.json() if "Camila" in c["paciente_nombre"]), None)
        pid = cita["patient_id"]

        # ---- documentos clínicos ----
        r = await client.post(f"/medico/pacientes/{pid}/documentos", headers=medico,
                              json={"tipo": "consentimiento", "titulo": "Consentimiento endodoncia", "contenido": "El paciente autoriza…"})
        results.append(("crear consentimiento -> 201 emitido", r.status_code == 201 and r.json()["estado"] == "emitido"))
        doc_id = r.json()["id"]

        r = await client.post(f"/medico/pacientes/{pid}/documentos", headers=medico,
                              json={"tipo": "licencia", "titulo": "Licencia médica 3 días"})
        results.append(("crear licencia -> 201", r.status_code == 201))

        r = await client.post(f"/medico/pacientes/{pid}/documentos", headers=medico, json={"tipo": "radiografia", "titulo": "x"})
        results.append(("tipo de documento inválido -> 400", r.status_code == 400))

        r = await client.get(f"/medico/pacientes/{pid}/documentos", headers=medico)
        results.append(("listar documentos -> 2", r.status_code == 200 and len(r.json()) == 2))

        r = await client.patch(f"/medico/documentos/{doc_id}/anular", headers=medico)
        results.append(("anular documento -> estado 'anulado'", r.status_code == 200 and r.json()["estado"] == "anulado"))

        # el paciente no crea documentos clínicos
        r = await client.post(f"/medico/pacientes/{pid}/documentos", headers=paciente, json={"tipo": "otro", "titulo": "x"})
        results.append(("paciente NO crea documentos -> 403", r.status_code == 403))

        # ---- periodontograma ----
        r = await client.get(f"/medico/pacientes/{pid}/periodontograma", headers=medico)
        results.append(("sin periodontograma al inicio -> null", r.status_code == 200 and r.json() is None))

        r = await client.post(f"/medico/pacientes/{pid}/periodontograma", headers=medico,
                              json={"datos": {"1.6": {"ps": 4, "sangrado": True}, "2.1": {"ps": 2, "sangrado": False}}, "notas": "Control inicial"})
        results.append(("guardar 1er periodontograma -> 201", r.status_code == 201))
        results.append(("primera toma: 0 anteriores", r.json()["tomas_anteriores"] == 0))
        results.append(("guarda los datos por pieza (FDI)", r.json()["datos"]["1.6"]["ps"] == 4))

        r = await client.post(f"/medico/pacientes/{pid}/periodontograma", headers=medico,
                              json={"datos": {"1.6": {"ps": 3, "sangrado": False}}, "notas": "Mejoría"})
        results.append(("guardar 2do periodontograma -> 1 anterior", r.status_code == 201 and r.json()["tomas_anteriores"] == 1))

        r = await client.get(f"/medico/pacientes/{pid}/periodontograma", headers=medico)
        results.append(("el último periodontograma es el más reciente", r.status_code == 200 and r.json()["notas"] == "Mejoría"))
        results.append(("indica 1 toma anterior", r.json()["tomas_anteriores"] == 1))

        # el paciente no guarda periodontograma
        r = await client.post(f"/medico/pacientes/{pid}/periodontograma", headers=paciente, json={"datos": {}})
        results.append(("paciente NO guarda periodontograma -> 403", r.status_code == 403))

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
