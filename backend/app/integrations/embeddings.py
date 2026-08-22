"""Embeddings de la base de conocimiento — conmutable, local por defecto.

Por defecto usa un embedding LOCAL y determinista (bolsa de palabras con
hashing y pesado sublineal, normalizado L2), sin dependencias pesadas ni
llamadas externas: los vectores viven en tu propio Postgres. La similitud
coseno se calcula en la app.

Es conmutable: si en el futuro se configura un proveedor externo de embeddings,
se reemplaza `embed()` sin tocar el resto (ingesta, almacenamiento, búsqueda).
"""

import math
import re
import unicodedata

DIM = 512


def _tokens(texto: str) -> list[str]:
    t = unicodedata.normalize("NFD", (texto or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")  # quita acentos
    palabras = re.findall(r"[a-z0-9]{2,}", t)
    # unigramas + bigramas (algo de contexto local)
    bigramas = [f"{palabras[i]}_{palabras[i + 1]}" for i in range(len(palabras) - 1)]
    return palabras + bigramas


def _bucket(token: str) -> int:
    h = 2166136261
    for ch in token:
        h = ((h ^ ord(ch)) * 16777619) & 0xFFFFFFFF
    return h % DIM


def embed_local(texto: str) -> list[float]:
    """Vector determinista, normalizado L2, de dimensión DIM."""
    vec = [0.0] * DIM
    for tok in _tokens(texto):
        vec[_bucket(tok)] += 1.0
    # tf sublineal para amortiguar términos muy repetidos
    vec = [math.log1p(v) for v in vec]
    norma = math.sqrt(sum(v * v for v in vec))
    if norma == 0:
        return vec
    return [v / norma for v in vec]


def embed(textos: list[str]) -> list[list[float]]:
    """Devuelve un vector por texto. Punto único conmutable a otro proveedor."""
    return [embed_local(t) for t in textos]


def coseno(a: list[float], b: list[float]) -> float:
    """Similitud coseno. Los vectores locales ya vienen normalizados, así que
    equivale al producto punto; se normaliza igual por robustez."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)
