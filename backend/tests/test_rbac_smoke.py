"""Fase 1 smoke test: proves the JWT -> TenantContext -> RBAC -> tenant
isolation chain actually works, end to end, against the real app object and
the real Postgres database (no mocks). No business endpoints exist yet (by
design — those land per-role in later phases), so this test mounts a
handful of throwaway diagnostic routes on `app` for the duration of the
test only, using the exact same `Depends(require(...))` mechanism a real
business route would use. Run with: `python -m tests.test_rbac_smoke`.
"""

import asyncio

import httpx
from fastapi import Depends

from app.main import app
from app.rbac.deps import require
from app.rbac.permissions import Action, Resource
from app.tenancy.context import TenantContext

PASSWORD = "Demo1234!"


@app.get("/_smoke/admin")
async def _smoke_admin(ctx: TenantContext = Depends(require(Resource.CLINICAS_SUCURSALES, Action.VER))):
    return {"ok": True, "email": ctx.email, "clinic_ids": [str(c) for c in (ctx.clinic_ids() or [])] or "ALL"}


@app.get("/_smoke/medico")
async def _smoke_medico(ctx: TenantContext = Depends(require(Resource.OWN_AGENDA, Action.VER))):
    return {"ok": True, "email": ctx.email}


@app.get("/_smoke/empresa")
async def _smoke_empresa(ctx: TenantContext = Depends(require(Resource.CLINIC_AGENDAS, Action.VER))):
    return {"ok": True, "email": ctx.email}


@app.get("/_smoke/paciente")
async def _smoke_paciente(ctx: TenantContext = Depends(require(Resource.OWN_APPOINTMENTS, Action.VER))):
    return {"ok": True, "email": ctx.email}


@app.get("/_smoke/aseguradora")
async def _smoke_aseguradora(ctx: TenantContext = Depends(require(Resource.CONVENIOS_ARANCELES, Action.VER))):
    return {"ok": True, "email": ctx.email}


@app.get("/_smoke/ledger-write")
async def _smoke_ledger_write(ctx: TenantContext = Depends(require(Resource.LEDGER_FINANCIERO, Action.EDITAR))):
    return {"ok": True}  # nobody should ever be able to hit this — ledger has no EDITAR grant anywhere


async def login(client: httpx.AsyncClient, email: str) -> str:
    r = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    return r.json()["access_token"]


async def main() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        results = []

        r = await client.post("/auth/login", json={"email": "admin.a@todoscare.dev", "password": "wrong"})
        results.append(("login wrong password -> 401", r.status_code == 401))

        tokens = {}
        for email in [
            "super@todoscare.dev",
            "admin.a@todoscare.dev",
            "admin.b@todoscare.dev",
            "medico.a@todoscare.dev",
            "empresa.a@todoscare.dev",
            "paciente.a@todoscare.dev",
            "aseguradora.x@todoscare.dev",
        ]:
            tokens[email] = await login(client, email)
        results.append(("all 7 demo users logged in", True))

        def auth(email: str) -> dict:
            return {"Authorization": f"Bearer {tokens[email]}"}

        r = await client.get("/_smoke/admin", headers=auth("admin.a@todoscare.dev"))
        results.append(("clinic_admin can view clinicas_sucursales", r.status_code == 200))

        r = await client.get("/_smoke/medico", headers=auth("medico.a@todoscare.dev"))
        results.append(("medico can view own_agenda", r.status_code == 200))

        r = await client.get("/_smoke/empresa", headers=auth("empresa.a@todoscare.dev"))
        results.append(("empresa can view clinic_agendas", r.status_code == 200))

        r = await client.get("/_smoke/paciente", headers=auth("paciente.a@todoscare.dev"))
        results.append(("paciente can view own_appointments", r.status_code == 200))

        r = await client.get("/_smoke/aseguradora", headers=auth("aseguradora.x@todoscare.dev"))
        results.append(("aseguradora can view convenios_aranceles", r.status_code == 200))

        r = await client.get("/_smoke/admin", headers=auth("paciente.a@todoscare.dev"))
        results.append(("paciente CANNOT view clinicas_sucursales -> 403", r.status_code == 403))

        r = await client.get("/_smoke/medico", headers=auth("empresa.a@todoscare.dev"))
        results.append(("empresa CANNOT view own_agenda (médico-only) -> 403", r.status_code == 403))

        r = await client.get("/_smoke/ledger-write", headers=auth("super@todoscare.dev"))
        results.append(("even super_admin CANNOT edit ledger_financiero -> 403", r.status_code == 403))

        r = await client.get("/_smoke/admin")
        results.append(("no token -> 401", r.status_code == 401))

        r = await client.get("/_smoke/admin", headers=auth("super@todoscare.dev"))
        results.append(("super_admin clinic_ids == ALL", r.json().get("clinic_ids") == "ALL"))

        r = await client.get("/_smoke/admin", headers=auth("admin.a@todoscare.dev"))
        body_a = r.json()
        results.append(
            ("clinic_admin.a clinic_ids has exactly 1 clinic (not ALL)", body_a["clinic_ids"] != "ALL" and len(body_a["clinic_ids"]) == 1)
        )

        r = await client.get("/_smoke/admin", headers=auth("admin.b@todoscare.dev"))
        body_b = r.json()
        results.append(("clinic_admin.b sees a DIFFERENT clinic_id than admin.a", body_b["clinic_ids"] != body_a["clinic_ids"]))

    print()
    failed = 0
    for name, ok in results:
        status = "PASS" if ok else "FAIL"
        if not ok:
            failed += 1
        print(f"  [{status}] {name}")
    print()
    if failed:
        print(f"{failed} check(s) FAILED")
        raise SystemExit(1)
    print(f"All {len(results)} checks passed.")


if __name__ == "__main__":
    asyncio.run(main())
