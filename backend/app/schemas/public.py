import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# ---- agenda online pública (60) ----
class ServicioPublicoOut(BaseModel):
    id: uuid.UUID
    nombre: str
    especialidad: str | None
    icono: str | None
    precio: float
    duracion_min: int


class SucursalPublicaOut(BaseModel):
    id: uuid.UUID
    nombre: str
    direccion: str | None


class ClinicaPublicaOut(BaseModel):
    slug: str
    nombre: str            # razón social
    habilitada: bool
    mensaje: str | None
    servicios: list[ServicioPublicoOut]
    sucursales: list[SucursalPublicaOut]


class SlotPublicoOut(BaseModel):
    professional_id: uuid.UUID
    profesional_nombre: str
    inicio: datetime
    fin: datetime


class ReservaPublicaIn(BaseModel):
    service_id: uuid.UUID
    professional_id: uuid.UUID
    inicio: datetime
    fin: datetime
    nombre: str = Field(min_length=2, max_length=255)
    rut: str | None = Field(default=None, max_length=50)
    telefono: str | None = Field(default=None, max_length=40)
    email: str | None = Field(default=None, max_length=255)
    notas: str | None = Field(default=None, max_length=500)


class ReservaPublicaOut(BaseModel):
    codigo: str
    estado: str
    inicio: datetime
    fin: datetime
    servicio_nombre: str | None
    profesional_nombre: str
    prepago_requerido: bool = False
    prepago_monto: float = 0
    prepagado: bool = False


class PrepagoPublicoOut(BaseModel):
    codigo: str
    prepagado: bool
    monto: float
    ref: str | None


class SolicitudEstadoOut(BaseModel):
    codigo: str
    estado: str
    inicio: datetime
    fin: datetime
