"""Smoke test · Editar usuario (48).

Verifica PATCH /admin/usuarios/{id}: nombre, teléfono, correo (con unicidad),
contraseña (re-login con la nueva) y estado activo/inactivo.

Run: `python -m tests.test_editar_usuario_smoke`.
"""

import asyncio

import httpx

from app.main import app

PASSWORD = "Demo1234!"


async def login(client: httpx.AsyncClient, email: str, password: str = PASSWORD):
    return await client.post("/auth/login", json={"email": email, "password": password})


async def main() -> None:
    transport = httpx.ASGITransport(app=app)
    results: list[tuple[str, bool]] = []

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await login(client, "admin.a@todoscare.dev")
        admin = {"Authorization": f"Bearer {r.json()['access_token']}"}

        r = await client.get("/admin/usuarios", headers=admin)
        emp = next(u for u in r.json() if u["email"] == "empresa.a@todoscare.dev")
        uid = emp["id"]

        # ── nombre + teléfono ──
        r = await client.patch(f"/admin/usuarios/{uid}", headers=admin, json={"nombre": "Portal A (editado)", "telefono": "+56 9 1234 5678"})
        results.append(("editar nombre+teléfono -> 200", r.status_code == 200 and r.json()["nombre"] == "Portal A (editado)"))
        r = await client.get("/admin/usuarios", headers=admin)
        emp2 = next(u for u in r.json() if u["id"] == uid)
        results.append(("cambios persistidos (nombre+teléfono)", emp2["nombre"] == "Portal A (editado)" and emp2["telefono"] == "+56 9 1234 5678"))

        # ── correo duplicado -> 409 ──
        r = await client.patch(f"/admin/usuarios/{uid}", headers=admin, json={"correo": "admin.a@todoscare.dev"})
        results.append(("correo duplicado -> 409", r.status_code == 409))

        # ── correo nuevo -> re-login con el nuevo correo ──
        r = await client.patch(f"/admin/usuarios/{uid}", headers=admin, json={"correo": "portal.a@todoscare.dev"})
        results.append(("cambiar correo -> 200", r.status_code == 200))
        r = await login(client, "portal.a@todoscare.dev")
        results.append(("login con el nuevo correo -> 200", r.status_code == 200))

        # ── contraseña -> re-login con la nueva, la vieja falla ──
        r = await client.patch(f"/admin/usuarios/{uid}", headers=admin, json={"password": "NuevaClave99!"})
        results.append(("cambiar contraseña -> 200", r.status_code == 200))
        r = await login(client, "portal.a@todoscare.dev", "NuevaClave99!")
        results.append(("login con la nueva contraseña -> 200", r.status_code == 200))
        r = await login(client, "portal.a@todoscare.dev", PASSWORD)
        results.append(("login con la contraseña vieja -> falla", r.status_code >= 400))

        # ── desactivar -> el login queda bloqueado ──
        r = await client.patch(f"/admin/usuarios/{uid}", headers=admin, json={"activo": False})
        results.append(("desactivar usuario -> 200", r.status_code == 200 and r.json()["activo"] is False))
        r = await login(client, "portal.a@todoscare.dev", "NuevaClave99!")
        results.append(("usuario inactivo no puede iniciar sesión", r.status_code >= 400))

        # ── reactivar ──
        r = await client.patch(f"/admin/usuarios/{uid}", headers=admin, json={"activo": True})
        r = await login(client, "portal.a@todoscare.dev", "NuevaClave99!")
        results.append(("reactivar y volver a iniciar sesión -> 200", r.status_code == 200))

        # ── usuario inexistente -> 404 ──
        r = await client.patch("/admin/usuarios/00000000-0000-0000-0000-000000000000", headers=admin, json={"nombre": "Inexistente"})
        results.append(("usuario inexistente -> 404", r.status_code == 404))

    print("\n=== Editar usuario (48) · smoke ===")
    ok = True
    for name, passed in results:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
        ok = ok and passed
    print("=== OK ===" if ok else "=== FALLÓ ===")
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
