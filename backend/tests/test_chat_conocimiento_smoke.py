"""Smoke test · Chat con la base de conocimiento (RAG, 72).

El paciente pregunta y el asistente responde con el material de la clínica
(citando fuentes, con guardrails). Generador conmutable: extractivo sin key,
modelo cuando hay key (monkeypatch). Si no hay material relevante, responde
seguro sin inventar.

Run: `python -m tests.test_chat_conocimiento_smoke`.
"""

import asyncio

import httpx

from app.core.config import settings
from app.integrations import asistente
from app.main import app

PASSWORD = "Demo1234!"

DOC = (
    "Preparación para una limpieza dental (profilaxis): cepíllate los dientes antes de venir. "
    "El procedimiento dura aproximadamente 40 minutos, no requiere anestesia y no genera molestias. "
    "Después de la limpieza puedes comer normalmente."
)


async def login(client: httpx.AsyncClient, email: str) -> dict:
    r = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def main() -> None:
    transport = httpx.ASGITransport(app=app)
    results: list[tuple[str, bool]] = []

    original_key = settings.anthropic_api_key
    original_fn = asistente._generar_con_ia
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        empresa = await login(client, "empresa.a@todoscare.dev")
        pac = await login(client, "paciente.a@todoscare.dev")

        # cargar material a la base de conocimiento de la clínica
        await client.post("/empresa/conocimiento/texto", headers=empresa, json={"nombre": "Guía de profilaxis", "texto": DOC})

        # ── sin key: respuesta extractiva citando fuente + disclaimer ──
        settings.anthropic_api_key = ""
        r = await client.post("/ia/consultar", headers=pac, json={"pregunta": "¿cuánto dura una limpieza dental?"})
        out = r.json()
        results.append(("consultar -> 200", r.status_code == 200))
        results.append(("respuesta usa el material (40 minutos)", "40 minutos" in out["respuesta"]))
        results.append(("cita la fuente cargada", "Guía de profilaxis" in out["fuentes"]))
        results.append(("incluye el disclaimer clínico", "no reemplaza la evaluación de un profesional" in out["respuesta"]))
        results.append(("sin key -> uso_ia False", out["uso_ia"] is False))

        # ── sin material relevante: respuesta segura, sin inventar ──
        r = await client.post("/ia/consultar", headers=pac, json={"pregunta": "¿cuál es la capital de Francia?"})
        out = r.json()
        results.append(("pregunta fuera de tema -> respuesta segura sin fuentes", out["fuentes"] == [] and "No encuentro esa información" in out["respuesta"]))

        # ── con key (monkeypatch del modelo): usa la IA ──
        settings.anthropic_api_key = "test-key"

        async def fake_gen(pregunta, contexto):
            return "La limpieza dental dura unos 40 minutos y no necesita anestesia."

        asistente._generar_con_ia = fake_gen
        r = await client.post("/ia/consultar", headers=pac, json={"pregunta": "¿duele la limpieza?"})
        out = r.json()
        results.append(("con key -> uso_ia True y respuesta del modelo", out["uso_ia"] is True and "40 minutos" in out["respuesta"]))

        # ── si el modelo falla -> cae a extractivo (no rompe) ──
        async def gen_rota(pregunta, contexto):
            raise RuntimeError("modelo caído")

        asistente._generar_con_ia = gen_rota
        r = await client.post("/ia/consultar", headers=pac, json={"pregunta": "¿cuánto dura la limpieza?"})
        results.append(("modelo caído -> fallback extractivo (200 con material)", r.status_code == 200 and "40 minutos" in r.json()["respuesta"]))

        # ── preview de la empresa ──
        settings.anthropic_api_key = ""
        r = await client.post("/empresa/conocimiento/consultar", headers=empresa, json={"pregunta": "¿necesito anestesia para la limpieza?"})
        results.append(("preview empresa responde con material", r.status_code == 200 and "anestesia" in r.json()["respuesta"].lower()))

    settings.anthropic_api_key = original_key
    asistente._generar_con_ia = original_fn

    print("\n=== Chat con base de conocimiento (72) · smoke ===")
    ok = True
    for name, passed in results:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
        ok = ok and passed
    print("=== OK ===" if ok else "=== FALLÓ ===")
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
