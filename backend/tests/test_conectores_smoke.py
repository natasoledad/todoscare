"""PR-AP smoke test: marco de conectores del Bloque D (SII, I-Med, Klap, Pix,
WhatsApp, Meta, TikTok, Google Empresas, agenda de terceros, teléfono IP,
correo), contra el app real + Postgres real.

  · Catálogo: el Administrador ve los 11 conectores fusionados con el estado
    por clínica (activo, configurado, qué claves están cargadas).
  · Credenciales: se guardan cifradas y NUNCA se devuelve el valor secreto,
    solo la lista de claves configuradas. Campos desconocidos -> 400.
  · Activación: el conector se enciende/apaga por clínica.
  · Prueba: apagado o sin credenciales avisa; encendido y configurado deja
    un evento en la traza (transporte real pendiente).
  · Traza: el Administrador ve los eventos del conector.
  · RBAC: médico y paciente NO gobiernan conectores (403).

Run: `python -m tests.test_conectores_smoke` (requiere la BD seedeada).
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
        admin = await login(client, "admin.a@todoscare.dev")
        superh = await login(client, "super@todoscare.dev")
        medico = await login(client, "medico.a@todoscare.dev")
        paciente = await login(client, "paciente.a@todoscare.dev")

        clinics = (await client.get("/admin/clinicas", headers=superh)).json()
        clinic_a = next(c["id"] for c in clinics if c["razon_social"] == "Clínica Demo A")

        # ── Catálogo (Admin) ──
        r = await client.get("/admin/conectores", headers=admin, params={"clinic_id": clinic_a})
        cat = r.json()
        tipos = {c["tipo"] for c in cat}
        esperados = {"sii", "imed", "klap", "pix", "whatsapp", "meta", "tiktok", "google_business", "agenda_terceros", "telefono_ip", "email"}
        check("admin ve el catálogo completo de conectores (11)", r.status_code == 200 and esperados <= tipos)
        tk = next(c for c in cat if c["tipo"] == "tiktok")
        check("cada conector expone sus campos con marca de secreto", any(f["secreto"] for f in tk["campos"]) and any(not f["secreto"] for f in tk["campos"]))
        check("un conector nuevo viene inactivo y sin configurar", tk["activo"] is False and tk["configurado"] is False and tk["campos_configurados"] == [])

        # ── RBAC ──
        check("médico NO ve el catálogo de conectores -> 403", (await client.get("/admin/conectores", headers=medico, params={"clinic_id": clinic_a})).status_code == 403)
        check("paciente NO ve el catálogo de conectores -> 403", (await client.get("/admin/conectores", headers=paciente, params={"clinic_id": clinic_a})).status_code == 403)

        # ── Prueba antes de configurar: apagado avisa ──
        r = await client.post("/admin/conectores/tiktok/probar", headers=admin, json={"clinic_id": clinic_a})
        check("probar conector apagado -> ok=False avisa que está desactivado", r.status_code == 200 and r.json()["ok"] is False and "desactiv" in r.json()["mensaje"].lower())

        # ── Configurar credenciales (parciales) + activar ──
        r = await client.put(
            "/admin/conectores/tiktok",
            headers=admin,
            json={"clinic_id": clinic_a, "activo": True, "credenciales": {"advertiser_id": "55123", "access_token": "secreto-abc"}},
        )
        out = r.json()
        check("guardar credenciales + activar -> 200 activo y configurado", r.status_code == 200 and out["activo"] is True and out["configurado"] is True)
        check("solo se devuelven las claves configuradas, nunca el valor", set(out["campos_configurados"]) == {"advertiser_id", "access_token"} and "secreto-abc" not in str(out))

        # ── Campo desconocido -> 400 ──
        r = await client.put("/admin/conectores/tiktok", headers=admin, json={"clinic_id": clinic_a, "credenciales": {"inexistente": "x"}})
        check("credencial con clave no válida -> 400", r.status_code == 400)

        # ── Conector desconocido -> 404 ──
        check("configurar conector inexistente -> 404", (await client.put("/admin/conectores/pokemon", headers=admin, json={"clinic_id": clinic_a})).status_code == 404)

        # ── Prueba con credenciales incompletas (falta plantilla es opcional; probamos SII sin nada) ──
        await client.put("/admin/conectores/sii", headers=admin, json={"clinic_id": clinic_a, "activo": True})
        r = await client.post("/admin/conectores/sii/probar", headers=admin, json={"clinic_id": clinic_a})
        check("probar activo pero sin credenciales -> ok=False lista lo que falta", r.status_code == 200 and r.json()["ok"] is False and "falta" in r.json()["mensaje"].lower())

        # ── Prueba OK (activo + configurado) deja traza ──
        r = await client.post("/admin/conectores/tiktok/probar", headers=admin, json={"clinic_id": clinic_a})
        check("probar activo + configurado -> ok=True simulado", r.status_code == 200 and r.json()["ok"] is True and r.json()["simulado"] is True)

        r = await client.get("/admin/conectores/tiktok/traza", headers=admin, params={"clinic_id": clinic_a})
        traza = r.json()
        check("la traza registró el evento de la prueba", r.status_code == 200 and len(traza) >= 1 and traza[0]["ref"] == "prueba" and traza[0]["direccion"] == "outbound")

        # ── Persiste el estado: re-leer el catálogo ──
        cat2 = (await client.get("/admin/conectores", headers=admin, params={"clinic_id": clinic_a})).json()
        tk2 = next(c for c in cat2 if c["tipo"] == "tiktok")
        check("el estado persiste (tiktok activo y configurado al releer)", tk2["activo"] is True and set(tk2["campos_configurados"]) == {"advertiser_id", "access_token"})

        # ── Actualización parcial: borrar una credencial enviando vacío ──
        r = await client.put("/admin/conectores/tiktok", headers=admin, json={"clinic_id": clinic_a, "credenciales": {"access_token": ""}})
        check("enviar credencial vacía la elimina (queda solo advertiser_id)", r.status_code == 200 and r.json()["campos_configurados"] == ["advertiser_id"])

        # ── Desactivar ──
        r = await client.put("/admin/conectores/tiktok", headers=admin, json={"clinic_id": clinic_a, "activo": False})
        check("desactivar conector -> activo=False (credenciales conservadas)", r.status_code == 200 and r.json()["activo"] is False and r.json()["configurado"] is True)

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
