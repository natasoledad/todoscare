"""Ingesta y búsqueda de la base de conocimiento (RAG, 72).

Extrae texto (PDF/plano), lo trocea, calcula embeddings locales y guarda los
fragmentos con su vector en Postgres. La búsqueda por similitud (coseno) se
resuelve en la app sobre los fragmentos de la clínica.
"""

import io
import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations import embeddings
from app.models.knowledge import KnowledgeChunk, KnowledgeSource

_MAX_CHARS = 700  # tamaño objetivo por fragmento


def extraer_texto_pdf(contenido: bytes) -> str:
    """Extrae el texto de un PDF. Requiere pypdf."""
    from pypdf import PdfReader

    lector = PdfReader(io.BytesIO(contenido))
    partes = []
    for pagina in lector.pages:
        try:
            partes.append(pagina.extract_text() or "")
        except Exception:  # noqa: BLE001 — una página ilegible no debe abortar todo
            continue
    return "\n\n".join(partes)


def trocear(texto: str) -> list[str]:
    """Parte el texto en fragmentos de ~700 caracteres respetando párrafos."""
    texto = re.sub(r"[ \t]+", " ", (texto or "").strip())
    if not texto:
        return []
    parrafos = [p.strip() for p in re.split(r"\n\s*\n", texto) if p.strip()]
    chunks: list[str] = []
    actual = ""
    for p in parrafos:
        # un párrafo enorme se corta por oraciones
        piezas = re.split(r"(?<=[.!?])\s+", p) if len(p) > _MAX_CHARS else [p]
        for pieza in piezas:
            if len(actual) + len(pieza) + 1 <= _MAX_CHARS:
                actual = f"{actual} {pieza}".strip()
            else:
                if actual:
                    chunks.append(actual)
                actual = pieza[:_MAX_CHARS] if len(pieza) > _MAX_CHARS else pieza
    if actual:
        chunks.append(actual)
    return chunks


async def ingerir(
    db: AsyncSession, *, clinic_id: uuid.UUID, created_by: uuid.UUID | None,
    nombre: str, texto: str, tipo: str, archivo_url: str | None = None,
) -> KnowledgeSource:
    chunks = trocear(texto)
    source = KnowledgeSource(
        clinic_id=clinic_id, created_by=created_by, nombre=nombre, tipo=tipo,
        archivo_url=archivo_url, estado="listo" if chunks else "error", n_chunks=len(chunks),
    )
    db.add(source)
    await db.flush()
    vectores = embeddings.embed(chunks)
    for i, (texto_chunk, vec) in enumerate(zip(chunks, vectores)):
        db.add(KnowledgeChunk(clinic_id=clinic_id, source_id=source.id, orden=i, texto=texto_chunk, embedding=vec))
    return source


async def buscar(
    db: AsyncSession, clinic_id: uuid.UUID, consulta: str, k: int = 4, umbral: float = 0.10,
) -> list[tuple[float, KnowledgeChunk, KnowledgeSource]]:
    """Devuelve los k fragmentos más relevantes (score, chunk, fuente) de las
    fuentes activas de la clínica, por encima de un umbral mínimo."""
    qv = embeddings.embed([consulta])[0]
    rows = (
        await db.execute(
            select(KnowledgeChunk, KnowledgeSource)
            .join(KnowledgeSource, KnowledgeSource.id == KnowledgeChunk.source_id)
            .where(
                KnowledgeChunk.clinic_id == clinic_id,
                KnowledgeChunk.deleted_at.is_(None),
                KnowledgeSource.deleted_at.is_(None),
                KnowledgeSource.activo.is_(True),
            )
        )
    ).all()
    calificados = [(embeddings.coseno(qv, ch.embedding), ch, src) for ch, src in rows]
    calificados.sort(key=lambda x: x[0], reverse=True)
    return [t for t in calificados[:k] if t[0] >= umbral]
