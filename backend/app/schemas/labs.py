import uuid

from pydantic import BaseModel, Field


# ---- laboratorios (57.1) ----
class LabIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=255)
    rut: str | None = Field(default=None, max_length=50)
    contacto: str | None = Field(default=None, max_length=255)


class LabUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=255)
    rut: str | None = Field(default=None, max_length=50)
    contacto: str | None = Field(default=None, max_length=255)
    activo: bool | None = None


class LabOut(BaseModel):
    id: uuid.UUID
    nombre: str
    rut: str | None
    contacto: str | None
    activo: bool


# ---- prestaciones del laboratorio: costo vs precio (57.3b) ----
class LabServiceIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=255)
    costo: float = Field(default=0, ge=0)
    precio: float = Field(default=0, ge=0)


class LabServiceUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=255)
    costo: float | None = Field(default=None, ge=0)
    precio: float | None = Field(default=None, ge=0)
    activo: bool | None = None


class LabServiceOut(BaseModel):
    id: uuid.UUID
    lab_id: uuid.UUID
    nombre: str
    costo: float
    precio: float
    margen: float   # precio - costo
    activo: bool
