"""PR-AQ smoke test: copago chileno con seguros complementarios y cajas de
compensación, contra el app real + Postgres real.

  · Catálogo: la empresa crea/edita/desactiva coberturas complementarias
    (seguro_complementario | caja_compensacion).
  · Cascada: la calculadora lleva de precio → bono previsión → seguro
    complementario → CCAF → copago final, con tope y deducible, sin aportar
    nunca más que el copago vigente.
  · Caja: al cobrar el copago final se guarda el desglose de coberturas como
    traza en el pago.
  · RBAC: médico y paciente NO gestionan coberturas (403).

Run: `python -m tests.test_copago_smoke` (requiere la BD seedeada).
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

    def check(name: str, ok: bool) -> None:
        results.append((name, ok))

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        empresa = await login(client, "empresa.a@todoscare.dev")
        medico = await login(client, "medico.a@todoscare.dev")
        paciente = await login(client, "paciente.a@todoscare.dev")

        # ── Catálogo vacío al inicio ──
        r = await client.get("/empresa/copago/coberturas", headers=empresa)
        check("catálogo de coberturas accesible (empresa)", r.status_code == 200 and isinstance(r.json(), list))

        # ── Crear seguro complementario (50%, tope 10.000, deducible 2.000) ──
        r = await client.post("/empresa/copago/coberturas", headers=empresa, json={
            "tipo": "seguro_complementario", "nombre": "Consorcio Salud",
            "modalidad": "porcentaje", "valor": 0.5, "tope": 10000, "deducible": 2000,
        })
        check("crear seguro complementario -> 201", r.status_code == 201 and r.json()["tipo"] == "seguro_complementario")
        seguro_id = r.json()["id"]

        # ── Crear caja de compensación (monto fijo 3.000, permite cuotas) ──
        r = await client.post("/empresa/copago/coberturas", headers=empresa, json={
            "tipo": "caja_compensacion", "nombre": "CCAF Los Andes",
            "modalidad": "monto", "valor": 3000, "permite_cuotas": True,
        })
        check("crear caja de compensación (permite cuotas) -> 201", r.status_code == 201 and r.json()["permite_cuotas"] is True)
        caja_cobertura_id = r.json()["id"]

        # ── Validación: porcentaje > 1 -> 400 ──
        r = await client.post("/empresa/copago/coberturas", headers=empresa, json={
            "tipo": "seguro_complementario", "nombre": "Malo", "modalidad": "porcentaje", "valor": 1.5,
        })
        check("porcentaje > 1 rechazado -> 400/422", r.status_code in (400, 422))

        # ── Cascada completa: precio 50.000, Isapre 70% ──
        # bono 35.000 -> copago 15.000; seguro (15.000-2.000)*0.5=6.500;
        # CCAF 3.000 -> copago final 5.500.
        r = await client.post("/empresa/copago/calcular", headers=empresa, json={
            "precio": 50000, "prevision_pct": 0.7, "cobertura_ids": [seguro_id, caja_cobertura_id],
        })
        d = r.json()
        check("cascada: bono previsión 35.000 y copago inicial 15.000", r.status_code == 200 and d["bono_prevision"] == 35000 and d["copago_inicial"] == 15000)
        aportes = {a["tipo"]: a["aporte"] for a in d["aportes"]}
        check("cascada: seguro complementario aporta 6.500", aportes.get("seguro_complementario") == 6500)
        check("cascada: caja de compensación aporta 3.000", aportes.get("caja_compensacion") == 3000)
        check("cascada: copago final 5.500 y permite cuotas", d["copago_final"] == 5500 and d["permite_cuotas"] is True)

        # ── Bono previsional fijo tiene prioridad sobre el % ──
        r = await client.post("/empresa/copago/calcular", headers=empresa, json={
            "precio": 20000, "prevision_bono": 12000, "cobertura_ids": [],
        })
        check("bono previsional fijo -> copago 8.000", r.status_code == 200 and r.json()["copago_final"] == 8000)

        # ── Una capa nunca aporta más que el copago vigente ──
        # precio 2.000, sin previsión -> copago 2.000; CCAF monto fijo 3.000 se
        # recorta al copago (2.000) -> copago final 0.
        r = await client.post("/empresa/copago/calcular", headers=empresa, json={
            "precio": 2000, "prevision_pct": 0.0, "cobertura_ids": [caja_cobertura_id],
        })
        d2 = r.json()
        check("capa no aporta más que el copago (CCAF 3.000 se recorta a 2.000)", d2["copago_final"] == 0 and d2["aportes"][1]["aporte"] == 2000)

        # ── Editar: desactivar el seguro y excluirlo de la cascada ──
        r = await client.patch(f"/empresa/copago/coberturas/{seguro_id}", headers=empresa, json={"activo": False})
        check("desactivar cobertura -> activo=False", r.status_code == 200 and r.json()["activo"] is False)
        r = await client.post("/empresa/copago/calcular", headers=empresa, json={
            "precio": 50000, "prevision_pct": 0.7, "cobertura_ids": [seguro_id, caja_cobertura_id],
        })
        # seguro inactivo se ignora -> solo CCAF 3.000 sobre 15.000 -> 12.000
        check("cascada ignora la cobertura inactiva -> copago 12.000", r.json()["copago_final"] == 12000)

        # ── Caja: cobrar el copago final guardando el desglose ──
        mi = (await client.get("/empresa/cajas/mi-caja", headers=empresa)).json()
        if mi is None:
            mi = (await client.post("/empresa/cajas", headers=empresa, json={"abono_inicial": 0})).json()
        caja_id = mi["id"]
        desglose = [
            {"tipo": "prevision", "nombre": "Bono Isapre", "aporte": 35000},
            {"tipo": "caja_compensacion", "nombre": "CCAF Los Andes", "aporte": 3000},
        ]
        r = await client.post(f"/empresa/cajas/{caja_id}/movimientos", headers=empresa, json={
            "tipo": "pago", "medio": "debito", "monto": 12000, "glosa": "Copago consulta",
            "coberturas_aplicadas": desglose,
        })
        check("registrar copago en caja con desglose -> 201", r.status_code == 201 and r.json()["monto"] == 12000)

        # ── RBAC ──
        check("médico NO gestiona coberturas -> 403", (await client.get("/empresa/copago/coberturas", headers=medico)).status_code == 403)
        check("paciente NO gestiona coberturas -> 403", (await client.get("/empresa/copago/coberturas", headers=paciente)).status_code == 403)

    print()
    failed = 0
    for name, ok in results:
        st = "PASS" if ok else "FAIL"
        if not ok:
            failed += 1
        print(f"  [{st}] {name}")
    print()
    if failed:
        print(f"{failed} check(s) FAILED")
        raise SystemExit(1)
    print(f"All {len(results)} checks passed.")


if __name__ == "__main__":
    asyncio.run(main())
