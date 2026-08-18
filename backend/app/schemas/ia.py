import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


# ---- sugerencias de la IA clínica (72) ----
class SugerenciaIAOut(BaseModel):
    id: uuid.UUID
    resumen: str
    hallazgos: dict
    proximo_control: date | None
    estado: str
    examen_nombre: str | None
    fecha: datetime


class FichaAplicadaOut(BaseModel):
    aplicada: bool
    ficha: dict
    proximo_control: date | None


# ---- recordatorios (72) ----
class RecordatorioOut(BaseModel):
    tipo: str            # cita | control
    titulo: str
    fecha: datetime | None
    mensaje: str


# ---- chatbot IA (72) ----
class ChatIn(BaseModel):
    texto: str = Field(min_length=1, max_length=500)


class ChatOut(BaseModel):
    intent: str
    reply: str
    accion: str | None = None  # p.ej. "agendar" cuando ofrece reservar


class AgendarIAIn(BaseModel):
    service_id: uuid.UUID


class AgendarIAOut(BaseModel):
    agendada: bool
    appointment_id: uuid.UUID | None
    servicio_nombre: str | None
    inicio: datetime | None
    fin: datetime | None
    mensaje: str
