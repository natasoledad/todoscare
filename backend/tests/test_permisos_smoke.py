"""Smoke test de permisos personalizados (48).

Overrides finos sobre el RBAC fijo: conceder a un usuario un permiso que su
rol no tiene, y revocar uno que sí tiene, sin cambiar el rol. El comportamiento
por defecto (sin overrides) no cambia.

Run: `python -m tests.test_permisos_smoke`.
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
        admin = await login(client, "admin.a@todoscare.dev")
        medico = await login(client, "medico.a@todoscare.dev")
        empresa = await login(client, "empresa.a@todoscare.dev")

        usuarios = (await client.get("/admin/usuarios", headers=admin)).json()
        med = next(u for u in usuarios if u["email"] == "medico.a@todoscare.dev")
        emp = next(u for u in usuarios if u["email"] == "empresa.a@todoscare.dev")
        clinic_id = med["roles"][0]["clinic_id"]

        cat = (await client.get("/admin/permisos/catalogo", headers=admin)).json()
        check("Catálogo trae recursos y acciones", "inventario" in cat["resources"] and "ver" in cat["actions"])

        # sin override: el médico no ve inventario
        r = await client.get("/empresa/inventario/proveedores", headers=medico)
        check("Médico sin permiso de inventario -> 403", r.status_code == 403)

        # conceder inventario.ver al médico (48.3)
        r = await client.put(f"/admin/usuarios/{med['id']}/permisos", headers=admin, json={"clinic_id": clinic_id, "resource": "inventario", "action": "ver", "allow": True})
        check("Conceder override -> 200", r.status_code == 200)
        ov_id = r.json()["id"]

        r = await client.get("/empresa/inventario/proveedores", headers=medico)
        check("Con override, el médico YA ve inventario -> 200", r.status_code == 200)

        lst = (await client.get(f"/admin/usuarios/{med['id']}/permisos", headers=admin)).json()
        check("El override aparece listado", any(o["id"] == ov_id and o["allow"] for o in lst))

        # revocar el override -> vuelve a 403
        r = await client.delete(f"/admin/usuarios/{med['id']}/permisos/{ov_id}", headers=admin)
        check("Eliminar override -> 204", r.status_code == 204)
        r = await client.get("/empresa/inventario/proveedores", headers=medico)
        check("Sin override otra vez -> 403", r.status_code == 403)

        # revocar a la empresa un permiso que SÍ tiene (deny gana) (48.4)
        r = await client.put(f"/admin/usuarios/{emp['id']}/permisos", headers=admin, json={"clinic_id": clinic_id, "resource": "cajas", "action": "crear", "allow": False})
        check("Deny override -> 200", r.status_code == 200)
        deny_id = r.json()["id"]
        r = await client.post("/empresa/cajas", headers=empresa, json={"abono_inicial": 0})
        check("Con deny, la empresa NO abre caja -> 403", r.status_code == 403)

        # quitar el deny -> la empresa vuelve a poder abrir caja
        await client.delete(f"/admin/usuarios/{emp['id']}/permisos/{deny_id}", headers=admin)
        r = await client.post("/empresa/cajas", headers=empresa, json={"abono_inicial": 0})
        check("Sin deny, la empresa abre caja -> 201", r.status_code == 201)

        # validaciones
        r = await client.put(f"/admin/usuarios/{med['id']}/permisos", headers=admin, json={"clinic_id": clinic_id, "resource": "inventado", "action": "ver", "allow": True})
        check("Recurso inválido -> 400", r.status_code == 400)

        # RBAC: la empresa no gestiona permisos
        r = await client.put(f"/admin/usuarios/{med['id']}/permisos", headers=empresa, json={"clinic_id": clinic_id, "resource": "inventario", "action": "ver", "allow": True})
        check("Empresa NO gestiona permisos -> 403", r.status_code == 403)

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
