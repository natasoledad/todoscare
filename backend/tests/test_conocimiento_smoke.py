"""Smoke test · Base de conocimiento RAG (72).

La empresa sube texto/PDF; se trocea y vectoriza dentro de Postgres; la búsqueda
por similitud recupera el fragmento relevante. Con RBAC y borrado.

Run: `python -m tests.test_conocimiento_smoke`.
"""

import asyncio

import httpx

from app.integrations import embeddings
from app.main import app

PASSWORD = "Demo1234!"

DOC = (
    "Política de agendamiento de la clínica.\n\n"
    "El horario de atención es de lunes a viernes de 9 a 18 horas. "
    "Para reservar una hora dental debes traer tu carnet de identidad. "
    "Las cancelaciones se avisan con 24 horas de anticipación.\n\n"
    "Preparación para una limpieza dental: cepillarse los dientes antes de la cita. "
    "El procedimiento de profilaxis dura aproximadamente 40 minutos y no requiere anestesia.\n\n"
    "Estacionamiento: la clínica cuenta con estacionamiento gratuito para pacientes en el subterráneo."
)


async def login(client: httpx.AsyncClient, email: str) -> dict:
    r = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def main() -> None:
    transport = httpx.ASGITransport(app=app)
    results: list[tuple[str, bool]] = []

    # ── funciones puras ──
    v = embeddings.embed_local("limpieza dental profilaxis")
    results.append(("embedding local tiene dimensión fija", len(v) == embeddings.DIM))
    results.append(("vector normalizado (norma ~1)", abs(sum(x * x for x in v) ** 0.5 - 1.0) < 1e-6))
    a = embeddings.embed_local("horario de atención de la clínica")
    b = embeddings.embed_local("horario de atención de la clínica")
    c = embeddings.embed_local("estacionamiento gratuito subterráneo")
    results.append(("coseno: idénticos > distintos", embeddings.coseno(a, b) > embeddings.coseno(a, c)))

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        empresa = await login(client, "empresa.a@todoscare.dev")
        paciente = await login(client, "paciente.a@todoscare.dev")

        # ── subir texto ──
        r = await client.post("/empresa/conocimiento/texto", headers=empresa, json={"nombre": "Guía de la clínica", "texto": DOC})
        fuente = r.json()
        results.append(("subir texto -> 201 con chunks", r.status_code == 201 and fuente["n_chunks"] >= 1 and fuente["estado"] == "listo"))
        sid = fuente["id"]

        r = await client.get("/empresa/conocimiento", headers=empresa)
        results.append(("listar fuentes incluye la nueva", any(f["id"] == sid for f in r.json())))

        # ── búsqueda recupera el fragmento correcto ──
        r = await client.post("/empresa/conocimiento/buscar", headers=empresa, json={"consulta": "¿cuánto dura la limpieza dental?"})
        res = r.json()["resultados"]
        results.append(("búsqueda devuelve resultados", len(res) > 0))
        results.append(("el fragmento top habla de profilaxis/limpieza", "profilaxis" in res[0]["texto"].lower() or "limpieza" in res[0]["texto"].lower()))

        r = await client.post("/empresa/conocimiento/buscar", headers=empresa, json={"consulta": "¿hay estacionamiento?"})
        res = r.json()["resultados"]
        results.append(("consulta de estacionamiento recupera ese fragmento", len(res) > 0 and "estacionamiento" in res[0]["texto"].lower()))

        # ── PDF sin texto -> 400 ──
        r = await client.post("/empresa/conocimiento/pdf", headers=empresa, files={"file": ("x.pdf", b"no soy un pdf", "application/pdf")})
        results.append(("PDF ilegible -> 400", r.status_code == 400))

        # ── desactivar fuente: deja de recuperarse ──
        await client.patch(f"/empresa/conocimiento/{sid}", headers=empresa, json={"activo": False})
        r = await client.post("/empresa/conocimiento/buscar", headers=empresa, json={"consulta": "limpieza dental"})
        results.append(("fuente inactiva no se recupera", len(r.json()["resultados"]) == 0))

        # ── RBAC + borrado ──
        r = await client.post("/empresa/conocimiento/texto", headers=paciente, json={"nombre": "x", "texto": "y"})
        results.append(("paciente no sube a la base de conocimiento", r.status_code in (401, 403)))
        r = await client.delete(f"/empresa/conocimiento/{sid}", headers=empresa)
        results.append(("borrar fuente -> 204", r.status_code == 204))

    print("\n=== Base de conocimiento RAG (72) · smoke ===")
    ok = True
    for name, passed in results:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
        ok = ok and passed
    print("=== OK ===" if ok else "=== FALLÓ ===")
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
