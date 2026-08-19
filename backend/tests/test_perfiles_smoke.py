"""Smoke test · Perfiles de acceso reutilizables (48).

Verifica end-to-end contra el app real + Postgres real:
  - los 12 perfiles base quedan sembrados por clínica;
  - un perfil autoritativo (allowlist) restringe al usuario a lo listado —
    concede lo que incluye (200) y niega lo que no (403)— sin tocar su rol;
  - un override fino por usuario (PR-X) gana sobre el perfil;
  - un perfil `sin_restriccion` (Gerencia) no limita: rige la matriz del rol;
  - al quitar el perfil, el usuario vuelve al comportamiento de su rol;
  - aislamiento por clínica: un admin no ve los perfiles de otra clínica;
  - CRUD de perfiles (crear, asignar, consultar, quitar, eliminar).

Run: `python -m tests.test_perfiles_smoke`.
"""

import asyncio

import httpx

from app.main import app

PASSWORD = "Demo1234!"

PERFILES_ESPERADOS = {
    "Recepción", "TENS", "TONS", "Médico", "Dentista", "Líder",
    "Coordinación", "Gerencia", "Reportería", "CallCenter",
    "Administrativo", "Administrador de Cuenta",
}


async def login(client: httpx.AsyncClient, email: str) -> dict:
    r = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def main() -> None:
    transport = httpx.ASGITransport(app=app)
    results: list[tuple[str, bool]] = []

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        admin = await login(client, "admin.a@todoscare.dev")      # clinic_admin @ Clínica Demo A
        admin_b = await login(client, "admin.b@todoscare.dev")    # clinic_admin @ Clínica Demo B
        empresa = await login(client, "empresa.a@todoscare.dev")  # empresa @ Clínica Demo A

        # ── contexto: user_id + clinic_id de empresa_a ──
        r = await client.get("/admin/usuarios", headers=admin)
        assert r.status_code == 200, r.text
        emp = next(u for u in r.json() if u["email"] == "empresa.a@todoscare.dev")
        empresa_id = emp["id"]
        clinic_id = emp["roles"][0]["clinic_id"]

        # ── 1) los 12 perfiles base sembrados en la clínica ──
        r = await client.get("/admin/perfiles", headers=admin)
        nombres = {p["nombre"] for p in r.json()}
        results.append(("perfiles: 12 base sembrados", r.status_code == 200 and PERFILES_ESPERADOS <= nombres))
        gerencia = next(p for p in r.json() if p["nombre"] == "Gerencia")
        results.append(("perfil Gerencia es sin_restriccion", gerencia["sin_restriccion"] is True))
        recepcion = next(p for p in r.json() if p["nombre"] == "Recepción")
        results.append(("perfil Recepción trae casillas (allowlist)", len(recepcion["permisos"]) > 0))

        # ── 2) aislamiento por clínica: admin_b no ve perfiles de clínica A ──
        r = await client.get("/admin/perfiles", headers=admin_b)
        ids_b = {p["clinic_id"] for p in r.json()}
        results.append(("aislamiento: admin B no ve perfiles de clínica A", clinic_id not in ids_b))

        # ── 3) baseline sin perfil: empresa puede ver agenda y catálogo (matriz) ──
        r_ag = await client.get("/empresa/pacientes", headers=empresa)
        r_cat = await client.get("/empresa/aranceles", headers=empresa)
        results.append(("baseline empresa: agenda 200 + catálogo 200", r_ag.status_code == 200 and r_cat.status_code == 200))

        # ── 4) crear un perfil autoritativo restrictivo (solo agenda/ver) ──
        r = await client.post("/admin/perfiles", headers=admin, json={
            "clinic_id": clinic_id, "nombre": "Solo Agenda (test)", "base_role": "empresa",
            "sin_restriccion": False, "permisos": [{"resource": "clinic_agendas", "action": "ver"}],
        })
        results.append(("crear perfil restrictivo -> 201", r.status_code == 201))
        perfil_id = r.json()["id"]

        # nombre duplicado en la misma clínica -> 409
        r = await client.post("/admin/perfiles", headers=admin, json={
            "clinic_id": clinic_id, "nombre": "Solo Agenda (test)", "base_role": "empresa",
            "sin_restriccion": False, "permisos": [],
        })
        results.append(("perfil duplicado -> 409", r.status_code == 409))

        # recurso inválido -> 400
        r = await client.post("/admin/perfiles", headers=admin, json={
            "clinic_id": clinic_id, "nombre": "Malo (test)", "base_role": "empresa",
            "sin_restriccion": False, "permisos": [{"resource": "no_existe", "action": "ver"}],
        })
        results.append(("recurso inválido en perfil -> 400", r.status_code == 400))

        # ── 5) asignar el perfil restrictivo a empresa_a ──
        r = await client.put(f"/admin/usuarios/{empresa_id}/perfil", headers=admin, json={
            "clinic_id": clinic_id, "profile_id": perfil_id,
        })
        results.append(("asignar perfil -> 200", r.status_code == 200))

        r = await client.get(f"/admin/usuarios/{empresa_id}/perfil", headers=admin)
        results.append(("consultar perfil asignado", r.status_code == 200 and any(p["profile_id"] == perfil_id for p in r.json())))

        # ── 6) el perfil restringe: agenda/ver concedido, catálogo/ver negado ──
        r_ag = await client.get("/empresa/pacientes", headers=empresa)
        r_cat = await client.get("/empresa/aranceles", headers=empresa)
        results.append(("con perfil: agenda 200 (en allowlist)", r_ag.status_code == 200))
        results.append(("con perfil: catálogo 403 (fuera de allowlist)", r_cat.status_code == 403))

        # ── 7) override fino gana sobre el perfil: conceder catálogo/ver ──
        r = await client.put(f"/admin/usuarios/{empresa_id}/permisos", headers=admin, json={
            "clinic_id": clinic_id, "resource": "catalogo_precios", "action": "ver", "allow": True,
        })
        override_id = r.json()["id"]
        r_cat = await client.get("/empresa/aranceles", headers=empresa)
        results.append(("override concede catálogo/ver -> 200 (gana al perfil)", r_cat.status_code == 200))

        # quitar el override -> vuelve a regir el perfil (403)
        await client.delete(f"/admin/usuarios/{empresa_id}/permisos/{override_id}", headers=admin)
        r_cat = await client.get("/empresa/aranceles", headers=empresa)
        results.append(("sin override: catálogo 403 de nuevo (rige perfil)", r_cat.status_code == 403))

        # ── 8) perfil sin_restriccion (Gerencia): no limita, rige la matriz ──
        r = await client.put(f"/admin/usuarios/{empresa_id}/perfil", headers=admin, json={
            "clinic_id": clinic_id, "profile_id": gerencia["id"],
        })
        r_cat = await client.get("/empresa/aranceles", headers=empresa)
        results.append(("perfil sin_restriccion: catálogo 200 (matriz)", r_cat.status_code == 200))

        # ── 9) quitar el perfil: vuelve al comportamiento del rol ──
        r = await client.delete(f"/admin/usuarios/{empresa_id}/perfil/{clinic_id}", headers=admin)
        r_cat = await client.get("/empresa/aranceles", headers=empresa)
        results.append(("quitar perfil -> 204 y catálogo 200 (rol)", r.status_code == 204 and r_cat.status_code == 200))

        # ── 10) editar y eliminar el perfil de prueba ──
        r = await client.patch(f"/admin/perfiles/{perfil_id}", headers=admin, json={"activo": False})
        results.append(("editar perfil (desactivar) -> 200", r.status_code == 200 and r.json()["activo"] is False))
        r = await client.delete(f"/admin/perfiles/{perfil_id}", headers=admin)
        results.append(("eliminar perfil -> 204", r.status_code == 204))

    print("\n=== Perfiles de acceso (48) · smoke ===")
    ok = True
    for name, passed in results:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
        ok = ok and passed
    print("=== OK ===" if ok else "=== FALLÓ ===")
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
