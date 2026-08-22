"""Smoke test · IA real de lectura de exámenes (72.4).

Verifica que el conector conmutable usa el modelo cuando hay API key (la llamada
se monkeypatchea para no depender de la red), que la sugerencia refleja lo que
extrajo la IA, y que ante error o sin key cae al heurístico. Además prueba las
funciones puras de armado de bloque y parseo de respuesta.

Run: `python -m tests.test_ia_lectura_smoke`.
"""

import asyncio

import httpx

from app.core.config import settings
from app.integrations import ia_clinica
from app.main import app

PASSWORD = "Demo1234!"


async def login(client: httpx.AsyncClient, email: str) -> dict:
    r = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def subir_y_ultima_sugerencia(client, headers, nombre, contenido):
    await client.post("/salud/examenes/subir", headers=headers, files={"file": (nombre, contenido, "application/pdf")})
    pend = (await client.get("/ia/sugerencias", headers=headers, params={"estado": "pendiente"})).json()
    return pend[0] if pend else None


async def main() -> None:
    transport = httpx.ASGITransport(app=app)
    results: list[tuple[str, bool]] = []

    # ── funciones puras (sin red) ──
    b_txt = ia_clinica._bloque_documento(b"colesterol 240 mg/dl", "text/plain")
    results.append(("bloque de texto se arma", b_txt["type"] == "text" and "colesterol" in b_txt["text"]))
    b_pdf = ia_clinica._bloque_documento(b"%PDF-1.4 xxx", None)
    results.append(("PDF detectado por magic bytes", b_pdf["type"] == "document" and b_pdf["source"]["media_type"] == "application/pdf"))
    b_img = ia_clinica._bloque_documento(b"\x89PNG", "image/png")
    results.append(("imagen se arma como bloque image", b_img["type"] == "image"))
    parsed = ia_clinica._parse_respuesta('Aquí está: {"resumen": "Colesterol elevado", "hallazgos": {"colesterol_alto": true}, "proximo_control_meses": 99}')
    results.append(("parseo extrae JSON y acota meses a 24", parsed["resumen"] == "Colesterol elevado" and parsed["proximo_control_meses"] == 24))
    try:
        ia_clinica._parse_respuesta("sin json aquí")
        results.append(("respuesta sin JSON lanza error", False))
    except ValueError:
        results.append(("respuesta sin JSON lanza error", True))

    original_key = settings.anthropic_api_key
    original_fn = ia_clinica._analizar_con_ia
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        pac = await login(client, "paciente.a@todoscare.dev")

        # ── con "IA" activa (monkeypatch): la sugerencia usa lo que devolvió el modelo ──
        settings.anthropic_api_key = "test-key"

        async def fake_ia(nombre, contenido, content_type):
            return {"resumen": "Colesterol total elevado (240 mg/dl).", "hallazgos": {"colesterol_alto": True, "seguimiento_lipidico": True}, "proximo_control_meses": 4}

        ia_clinica._analizar_con_ia = fake_ia
        sug = await subir_y_ultima_sugerencia(client, pac, "informe.pdf", b"%PDF-1.4 lipidos")
        results.append(("IA activa: la sugerencia usa el resumen del modelo", sug is not None and "Colesterol" in sug["resumen"]))
        results.append(("IA activa: hallazgos del modelo presentes", sug is not None and sug["hallazgos"].get("colesterol_alto") is True))

        # ── la IA falla -> cae al heurístico (no rompe la subida) ──
        async def ia_rota(nombre, contenido, content_type):
            raise RuntimeError("modelo caído")

        ia_clinica._analizar_con_ia = ia_rota
        sug2 = await subir_y_ultima_sugerencia(client, pac, "electrocardiograma_ecg.pdf", b"%PDF ecg")
        results.append(("IA con error -> fallback heurístico (cardiovascular)", sug2 is not None and sug2["hallazgos"].get("seguimiento_cardiovascular") is True))

        # ── sin API key -> heurístico aunque haya contenido ──
        settings.anthropic_api_key = ""
        sug3 = await subir_y_ultima_sugerencia(client, pac, "glicemia_hba1c.pdf", b"%PDF gli")
        results.append(("sin key -> heurístico (glicemia)", sug3 is not None and sug3["hallazgos"].get("seguimiento_glicemia") is True))

    settings.anthropic_api_key = original_key
    ia_clinica._analizar_con_ia = original_fn

    print("\n=== IA real de lectura (72.4) · smoke ===")
    ok = True
    for name, passed in results:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
        ok = ok and passed
    print("=== OK ===" if ok else "=== FALLÓ ===")
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
