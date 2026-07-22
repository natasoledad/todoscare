import uuid
from datetime import datetime

from pydantic import BaseModel


class ServicioOut(BaseModel):
    id: uuid.UUID
    nombre: str
    icono: str | None
    precio: float
    duracion_min: int


class SlotOut(BaseModel):
    professional_id: uuid.UUID
    inicio: datetime
    fin: datetime


class ReservaInput(BaseModel):
    service_id: uuid.UUID
    professional_id: uuid.UUID
    inicio: datetime
    fin: datetime


class CitaOut(BaseModel):
    id: uuid.UUID
    servicio_nombre: str
    inicio: datetime
    fin: datetime
    estado: str
    ubicacion: str
