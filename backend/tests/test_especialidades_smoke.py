"""Smoke test de especialidades + perfil del profesional + motivos (punto 54).

Ejercita, contra la BD real seedeada con `app.seed`, el portal Empresa:

  · Especialidades (54): alta con tipo dental/médica, nombre único (409),
    listado y deshabilitar (activo=false).
  · Perfil del profesional (54.1b): asignar especialidad + duración + modalidad
    a un médico de la clínica; se refleja en GET /empresa/profesionales.
    Un id que no es médico de la clínica -> 404.
  · Motivos de atención (54.9): alta, listado, edición y baja lógica.

Run: `python -m tests.test_especialidades_smoke`.
"""

import asyncio

import httpx
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.main import app
from app.models.identity import User
from app.models.tenant import Clinic

PASSWORD = "Demo1234!"


async def login(client: httpx.AsyncClient, email: str) -> dict:
    r = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def main() -> None:
    results: list[tuple[str, bool]] = []

    def check(name: str, ok: bool) -> None:
        results.append((name, ok))

    # Contexto: la clínica demo A y su médico A ya existen por el seed.
    async with AsyncSessionLocal() as db:
        clinic = (await db.execute(select(Clinic).where(Clinic.razon_social == "Clínica Demo A"))).scalar_one()
        med_a = (await db.execute(select(User).where(User.email == "medico.a@todoscare.dev"))).scalar_one()
        med_a_id = str(med_a.id)
        clinic  # noqa: B018 — solo para asegurar que existe

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        emp = await login(client, "empresa.a@todoscare.dev")

        # ───────── Especialidades (54) ─────────
        nombre = "Ortodoncia Smoke"
        r = await client.post("/empresa/especialidades", headers=emp, json={"nombre": nombre, "tipo": "dental", "icono": "🦷"})
        check("Especialidad: alta dental -> 201", r.status_code == 201)
        esp = r.json()
        check("Especialidad: tipo dental y activa por defecto", esp.get("tipo") == "dental" and esp.get("activo") is True)
        esp_id = esp["id"]

        r_dup = await client.post("/empresa/especialidades", headers=emp, json={"nombre": nombre, "tipo": "medica"})
        check("Especialidad: nombre duplicado -> 409", r_dup.status_code == 409)

        lst = (await client.get("/empresa/especialidades", headers=emp)).json()
        check("Especialidad: aparece en el listado", any(e["id"] == esp_id for e in lst))

        # ───────── Perfil del profesional (54.1b) ─────────
        r = await client.patch(
            f"/empresa/profesionales/{med_a_id}/perfil", headers=emp,
            json={"specialty_id": esp_id, "duracion_min": 20, "modalidad": "videoconsulta"},
        )
        check("Perfil: asignar especialidad+duración+modalidad -> 200", r.status_code == 200)
        perfil = r.json()
        check(
            "Perfil: devuelve especialidad/tipo/duración/modalidad correctos",
            perfil.get("specialty_nombre") == nombre and perfil.get("tipo_especialidad") == "dental"
            and perfil.get("duracion_min") == 20 and perfil.get("modalidad") == "videoconsulta",
        )

        # segunda edición del mismo profesional -> no crea perfil duplicado (unique clinic+user)
        r2 = await client.patch(f"/empresa/profesionales/{med_a_id}/perfil", headers=emp, json={"duracion_min": 30})
        check("Perfil: segunda edición (upsert idempotente) -> 200 y duración=30", r2.status_code == 200 and r2.json().get("duracion_min") == 30)

        # el listado de profesionales ahora trae el perfil
        profs = (await client.get("/empresa/profesionales", headers=emp)).json()
        me = next((p for p in profs if p["id"] == med_a_id), None)
        check(
            "Profesionales: el listado refleja el perfil del médico",
            me is not None and me["specialty_nombre"] == nombre and me["duracion_min"] == 30 and me["modalidad"] == "videoconsulta",
        )

        # un id que no es médico de la clínica -> 404
        import uuid as _uuid
        r404 = await client.patch(f"/empresa/profesionales/{_uuid.uuid4()}/perfil", headers=emp, json={"duracion_min": 15})
        check("Perfil: id que no es médico de la clínica -> 404", r404.status_code == 404)

        # ───────── Deshabilitar especialidad (54.4) ─────────
        rd = await client.patch(f"/empresa/especialidades/{esp_id}", headers=emp, json={"activo": False})
        check("Especialidad: deshabilitar (activo=false) -> 200", rd.status_code == 200 and rd.json().get("activo") is False)

        # ───────── Motivos de atención (54.9) ─────────
        rm = await client.post("/empresa/motivos", headers=emp, json={"nombre": "Control Smoke", "specialty_id": esp_id})
        check("Motivo: alta -> 201", rm.status_code == 201)
        motivo_id = rm.json()["id"]
        check("Motivo: trae el nombre de la especialidad", rm.json().get("specialty_nombre") == nombre)

        motivos = (await client.get("/empresa/motivos", headers=emp)).json()
        check("Motivo: aparece en el listado", any(m["id"] == motivo_id for m in motivos))

        re = await client.patch(f"/empresa/motivos/{motivo_id}", headers=emp, json={"nombre": "Control Smoke 2"})
        check("Motivo: edición -> 200 y nombre nuevo", re.status_code == 200 and re.json()["nombre"] == "Control Smoke 2")

        rdel = await client.delete(f"/empresa/motivos/{motivo_id}", headers=emp)
        check("Motivo: baja lógica -> 204", rdel.status_code == 204)
        motivos2 = (await client.get("/empresa/motivos", headers=emp)).json()
        check("Motivo: ya no aparece tras la baja", not any(m["id"] == motivo_id for m in motivos2))

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
