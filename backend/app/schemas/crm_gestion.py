import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


# ---- Tareas de gestión ----
class TareaIn(BaseModel):
    titulo: str = Field(min_length=1)
    descripcion: str | None = None
    patient_id: uuid.UUID | None = None
    vencimiento: date | None = None


class TareaUpdate(BaseModel):
    estado: str | None = None
    titulo: str | None = None
    descripcion: str | None = None
    vencimiento: date | None = None


class TareaOut(BaseModel):
    id: uuid.UUID
    titulo: str
    descripcion: str | None
    patient_id: uuid.UUID | None
    estado: str
    vencimiento: date | None
    fecha: datetime


# ---- Encuestas de satisfacción ----
class EncuestaIn(BaseModel):
    patient_id: uuid.UUID | None = None
    paciente_nombre: str | None = None
    appointment_id: uuid.UUID | None = None


class ResponderEncuestaIn(BaseModel):
    score: int = Field(ge=0, le=10)
    comentario: str | None = None


class EncuestaOut(BaseModel):
    id: uuid.UUID
    paciente_nombre: str | None
    estado: str
    score: int | None
    comentario: str | None
    fecha: datetime
    respondida_at: datetime | None


class EncuestaResumen(BaseModel):
    enviadas: int
    respondidas: int
    tasa_respuesta: float       # %
    promedio: float | None      # score medio
    nps: int | None             # -100..100


# ---- Plantillas de mensaje ----
class PlantillaIn(BaseModel):
    nombre: str = Field(min_length=1)
    canal: str = "email"        # email | whatsapp
    asunto: str | None = None
    cuerpo: str = Field(min_length=1)


class PlantillaUpdate(BaseModel):
    nombre: str | None = None
    canal: str | None = None
    asunto: str | None = None
    cuerpo: str | None = None


class PlantillaOut(BaseModel):
    id: uuid.UUID
    nombre: str
    canal: str
    asunto: str | None
    cuerpo: str
