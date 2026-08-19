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


# ---- órdenes de trabajo (57.11 · 57.12) ----
from datetime import date, datetime  # noqa: E402


class LabOrderIn(BaseModel):
    lab_id: uuid.UUID
    descripcion: str = Field(min_length=1, max_length=255)
    lab_service_id: uuid.UUID | None = None
    patient_id: uuid.UUID | None = None
    treatment_plan_id: uuid.UUID | None = None
    pieza: str | None = Field(default=None, max_length=10)
    costo: float | None = Field(default=None, ge=0)   # si no viene y hay lab_service_id, se hereda
    precio: float | None = Field(default=None, ge=0)
    fecha_entrega: date | None = None
    notas: str | None = Field(default=None, max_length=500)


class LabOrderUpdate(BaseModel):
    descripcion: str | None = Field(default=None, min_length=1, max_length=255)
    pieza: str | None = Field(default=None, max_length=10)
    costo: float | None = Field(default=None, ge=0)
    precio: float | None = Field(default=None, ge=0)
    fecha_entrega: date | None = None
    notas: str | None = Field(default=None, max_length=500)


class LabOrderEstadoIn(BaseModel):
    estado: str  # en_proceso | en_revision | terminado | cancelado


class LabOrderOut(BaseModel):
    id: uuid.UUID
    lab_id: uuid.UUID
    lab_nombre: str | None
    descripcion: str
    pieza: str | None
    costo: float
    precio: float
    estado: str
    fecha_entrega: date | None
    pagado: bool
    patient_id: uuid.UUID | None
    paciente_nombre: str | None
    treatment_plan_id: uuid.UUID | None
    notas: str | None
    creada: datetime


class CuentaPorPagarOut(BaseModel):
    lab_id: uuid.UUID
    lab_nombre: str
    cantidad_ordenes: int
    total: float
