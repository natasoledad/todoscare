import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class FuenteOut(BaseModel):
    id: uuid.UUID
    nombre: str
    tipo: str
    estado: str
    n_chunks: int
    activo: bool
    fecha: datetime


class TextoIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=255)
    texto: str = Field(min_length=1)


class FuenteUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=255)
    activo: bool | None = None


class BuscarIn(BaseModel):
    consulta: str = Field(min_length=1)
    k: int = Field(default=4, ge=1, le=10)


class FragmentoOut(BaseModel):
    fuente: str
    texto: str
    score: float


class BuscarOut(BaseModel):
    resultados: list[FragmentoOut]
