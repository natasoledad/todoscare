import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


# ---- agenda ----
class CitaMedicoOut(BaseModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    paciente_nombre: str
    servicio_nombre: str
    inicio: datetime
    fin: datetime
    estado: str
    atendida: bool  # ¿ya tiene un registro de prontuario?


# ---- ficha del paciente ----
class ExamenFichaOut(BaseModel):
    nombre: str
    fecha: datetime
    estado: str


class HospitalizacionFichaOut(BaseModel):
    motivo: str
    centro: str | None
    ingreso: date | None


class FichaPacienteOut(BaseModel):
    patient_id: uuid.UUID
    nombre: str
    rut: str
    nivel: str
    ficha: dict
    examenes: list[ExamenFichaOut]
    hospitalizaciones: list[HospitalizacionFichaOut]
    odontograma: dict


# ---- prontuario ----
class ProntuarioInput(BaseModel):
    motivo: str = Field(min_length=1)
    evolucion: str | None = None
    diagnostico: str | None = None
    contenido_extra: dict | None = None  # campos libres por especialidad


class EnmiendaInput(BaseModel):
    nota: str = Field(min_length=1)


class ProntuarioOut(BaseModel):
    id: uuid.UUID
    contenido: dict
    creado: datetime


# ---- prescripción ----
class PrescripcionItem(BaseModel):
    medicamento: str = Field(min_length=1)
    cantidad: str = ""
    indicaciones: str = ""


class PrescripcionInput(BaseModel):
    items: list[PrescripcionItem] = Field(min_length=1)
    confirmar_alertas: bool = False  # se debe poner True para firmar pese a alertas de alergia


class AlertaClinica(BaseModel):
    tipo: str  # "alergia"
    medicamento: str
    detalle: str


class PrescripcionOut(BaseModel):
    id: uuid.UUID
    items: list[dict]
    estado: str
    firmado_en: datetime | None


class PrescripcionResult(BaseModel):
    """Firma bloqueada por alertas -> prescripcion None + alertas llenas.
    Firma OK -> prescripcion llena + alertas vacías."""

    prescripcion: PrescripcionOut | None
    alertas: list[AlertaClinica]


# ---- órdenes de examen ----
class OrdenInput(BaseModel):
    tipo: str = Field(pattern="^(laboratorio|imagenes)$")


class OrdenOut(BaseModel):
    id: uuid.UUID
    tipo: str
    estado: str
    creada: datetime


# ---- odontograma ----
class OdontogramaUpdateInput(BaseModel):
    piezas: dict  # {"15": {"estado": "pendiente"}, ...}


# ---- cierre / liquidación ----
class CierreOut(BaseModel):
    cita_id: uuid.UUID
    estado: str
    split_monto: float | None


class LiquidacionOut(BaseModel):
    fecha: datetime
    monto: float
    base: float | None
    ref: str | None
