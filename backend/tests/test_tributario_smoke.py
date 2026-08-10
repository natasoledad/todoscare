"""Tanda 7 smoke test: documentos tributarios electrónicos, contra el app real
+ Postgres real. Verifica que la plataforma emite el documento que corresponde
al país de la clínica, con el impuesto y el órgano correctos:

  · Chile (SII): boleta electrónica (39, IVA incluido) y factura (33, IVA por
    fuera); anulación vía nota de crédito (61) que referencia el folio original.
  · Brasil: NFS-e (serviço → município, ISS) y NF-e (mercadoria → SEFAZ
    estadual, ICMS); cancelamento de la NFS-e.
  · El conector gobierna por clínica (una clínica sin el conector habilitado
    rechaza la emisión) y el aislamiento multi-tenant impide ver documentos de
    otra clínica. RBAC: el admin observa pero no emite.
  · La caja emite el documento en la misma transacción del pago (folio en la
    boleta del movimiento).

Run: `python -m tests.test_tributario_smoke` (requiere la BD seedeada).
"""

import asyncio

import httpx

from app.main import app

PASSWORD = "Demo1234!"


async def login(client: httpx.AsyncClient, email: str, password: str = PASSWORD) -> dict:
    r = await client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def main() -> None:
    transport = httpx.ASGITransport(app=app)
    results: list[tuple[str, bool]] = []

    def check(name: str, ok: bool) -> None:
        results.append((name, ok))

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        empresa_cl = await login(client, "empresa.b@todoscare.dev")
        empresa_br = await login(client, "empresa.c@todoscare.dev")
        empresa_mx = await login(client, "empresa.a@todoscare.dev")
        admin_cl = await login(client, "admin.b@todoscare.dev")

        # ───────────────────────── CHILE / SII ─────────────────────────
        tipos = (await client.get("/tributario/tipos", headers=empresa_cl)).json()
        check("CL: país=CL, conector habilitado, tipos incluyen boleta y factura",
              tipos["pais"] == "CL" and tipos["habilitado"] and "boleta_electronica" in tipos["tipos"])

        emisor = (await client.get("/tributario/emisor", headers=empresa_cl)).json()
        check("CL: emisor fiscal cargado con RUT", emisor and emisor["tax_id"] == "76.123.456-7")

        # Boleta electrónica (39): precio con IVA incluido -> neto se despeja.
        r = await client.post("/tributario/documentos", headers=empresa_cl, json={
            "tipo_documento": "boleta_electronica",
            "items": [{"descripcion": "Consulta general", "cantidad": 1, "precio_unitario": 11900}],
        })
        boleta = r.json()
        check("CL: emite boleta 39 -> 201 aceptado por el SII",
              r.status_code == 201 and boleta["estado"] == "aceptado" and boleta["organo"] == "SII" and boleta["jurisdiccion"] == "federal")
        check("CL: boleta calcula IVA 19% sobre precio bruto (neto 10000, IVA 1900, total 11900)",
              boleta["neto"] == 10000 and boleta["impuesto"] == 1900 and boleta["total"] == 11900)
        check("CL: boleta con folio, TED (sello) y XML con TipoDTE 39",
              boleta["folio"] >= 1 and bool(boleta["sello"]) and "<TipoDTE>39</TipoDTE>" in (boleta["xml"] or ""))

        # Factura electrónica (33): precio neto -> IVA por fuera.
        r = await client.post("/tributario/documentos", headers=empresa_cl, json={
            "tipo_documento": "factura_electronica",
            "receptor": {"tax_id": "77.888.999-0", "nombre": "Empresa Cliente Ltda"},
            "items": [{"descripcion": "Plan salud mensual", "cantidad": 1, "precio_unitario": 10000}],
        })
        factura = r.json()
        check("CL: factura 33 agrega IVA por fuera (neto 10000, IVA 1900, total 11900)",
              r.status_code == 201 and factura["neto"] == 10000 and factura["impuesto"] == 1900 and factura["total"] == 11900 and factura["codigo"] == "33")

        # Anulación -> nota de crédito (61) que referencia la boleta.
        r = await client.post(f"/tributario/documentos/{boleta['id']}/anular", headers=empresa_cl, json={"motivo": "Devolución al paciente"})
        nc = r.json()
        check("CL: anular boleta emite nota de crédito 61 que referencia el folio original",
              r.status_code == 200 and nc["codigo"] == "61" and nc["referencia_id"] == boleta["id"])
        check("CL: la nota de crédito reproduce el total anulado (11900)", nc["total"] == 11900)
        est = (await client.get(f"/tributario/documentos/{boleta['id']}/estado", headers=empresa_cl)).json()
        check("CL: la boleta original queda anulada", est["estado"] == "anulado")

        # ───────────────────────── BRASIL / NF ─────────────────────────
        tipos_br = (await client.get("/tributario/tipos", headers=empresa_br)).json()
        check("BR: país=BR, tipos incluyen nfse y nfe", tipos_br["pais"] == "BR" and "nfse" in tipos_br["tipos"] and "nfe" in tipos_br["tipos"])

        # NFS-e (serviço) -> município, ISS 5%.
        r = await client.post("/tributario/documentos", headers=empresa_br, json={
            "tipo_documento": "nfse", "serie": "RPS",
            "items": [{"descripcion": "Consulta médica", "cantidad": 1, "precio_unitario": 200}],
        })
        nfse = r.json()
        check("BR: emite NFS-e -> competência municipal (prefeitura), moeda BRL",
              r.status_code == 201 and nfse["jurisdiccion"] == "municipal" and "Prefeitura" in nfse["organo"] and nfse["moneda"] == "BRL")
        check("BR: NFS-e calcula ISS 5% (base 200, ISS 10) y trae protocolo + código de verificação",
              nfse["impuesto"] == 10.0 and nfse["impuesto_detalle"]["tipo"] == "ISS" and bool(nfse["track_id"]) and bool(nfse["sello"]))

        # NF-e (mercadoria) -> SEFAZ estadual, ICMS 18%.
        r = await client.post("/tributario/documentos", headers=empresa_br, json={
            "tipo_documento": "nfe", "serie": "1",
            "items": [{"descripcion": "Insumo odontológico", "cantidad": 1, "precio_unitario": 200}],
        })
        nfe = r.json()
        check("BR: emite NF-e -> competência estadual (SEFAZ), modelo 55, ICMS 18% (36)",
              r.status_code == 201 and nfe["jurisdiccion"] == "estatal" and nfe["organo"].startswith("SEFAZ") and nfe["codigo"] == "55" and nfe["impuesto"] == 36.0)

        # Cancelamento de la NFS-e.
        r = await client.post(f"/tributario/documentos/{nfse['id']}/anular", headers=empresa_br, json={"motivo": "Erro de emissão"})
        cancel = r.json()
        check("BR: cancelamento marca a NFS-e anulada com protocolo de cancelamento",
              r.status_code == 200 and cancel["estado"] == "anulado" and "cancelamento_protocolo" in (cancel["impuesto_detalle"] or {}))

        # ───────────────────── gate del conector ─────────────────────
        r = await client.post("/tributario/documentos", headers=empresa_mx, json={
            "tipo_documento": "boleta_electronica",
            "items": [{"descripcion": "x", "cantidad": 1, "precio_unitario": 1000}],
        })
        check("Gate: una clínica sin el conector habilitado rechaza la emisión (409)", r.status_code == 409)

        # ───────────────────── aislamiento multi-tenant ─────────────────────
        r = await client.get(f"/tributario/documentos/{factura['id']}", headers=empresa_br)
        check("Aislamiento: empresa BR no puede ver un documento de la clínica CL (404)", r.status_code == 404)

        docs_cl = (await client.get("/tributario/documentos", headers=empresa_cl)).json()
        ids_cl = {d["id"] for d in docs_cl}
        check("Aislamiento: la lista de la clínica CL contiene sus documentos y no los de BR",
              boleta["id"] in ids_cl and nfse["id"] not in ids_cl)

        # ───────────────────── RBAC: admin observa, no emite ─────────────────────
        r = await client.get("/tributario/documentos", headers=admin_cl)
        check("RBAC: el clinic_admin puede listar los documentos de su clínica (VER)", r.status_code == 200)
        r = await client.post("/tributario/documentos", headers=admin_cl, json={
            "tipo_documento": "boleta_electronica",
            "items": [{"descripcion": "x", "cantidad": 1, "precio_unitario": 1000}],
        })
        check("RBAC: el clinic_admin NO puede emitir (sin CREAR) -> 403", r.status_code == 403)

        # ───────────────────── caja emite en la misma transacción ─────────────────────
        caja = (await client.post("/empresa/cajas", headers=empresa_cl, json={"abono_inicial": 0})).json()
        r = await client.post(f"/empresa/cajas/{caja['id']}/movimientos", headers=empresa_cl, json={
            "tipo": "pago", "medio": "efectivo", "monto": 23800, "glosa": "Consulta",
            "emitir_boleta": True,
        })
        mov = r.json()
        check("Caja: registrar un pago con emitir_boleta emite el documento y guarda el folio",
              r.status_code == 201 and mov["tax_document_id"] is not None and "boleta_electronica" in (mov["boleta"] or ""))
        if mov.get("tax_document_id"):
            doc = (await client.get(f"/tributario/documentos/{mov['tax_document_id']}", headers=empresa_cl)).json()
            check("Caja: el documento emitido desde caja quedó ligado al pago (cash_payment_id)",
                  doc["total"] == 23800 and doc["neto"] == 20000 and doc["impuesto"] == 3800)

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
