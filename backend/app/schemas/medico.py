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


# ---- Tanda 3: signos vitales ----
class SignosVitalesIn(BaseModel):
    appointment_id: uuid.UUID | None = None
    presion_sistolica: int | None = None
    presion_diastolica: int | None = None
    fc_ppm: int | None = None
    fr_rpm: int | None = None
    spo2: int | None = None
    glicemia: int | None = None
    eva: int | None = None
    peso_kg: float | None = None
    talla_cm: float | None = None
    temperatura: float | None = None
    notas: str | None = None


class SignosVitalesOut(SignosVitalesIn):
    id: uuid.UUID
    fecha: datetime


# ---- Tanda 3: planes de tratamiento / presupuestos ----
class PlanItemIn(BaseModel):
    descripcion: str = Field(min_length=1)
    pieza: str | None = None
    cantidad: int = Field(default=1, ge=1)
    precio_unit: float = Field(default=0, ge=0)
    service_id: uuid.UUID | None = None


class PlanItemOut(PlanItemIn):
    id: uuid.UUID
    estado: str
    subtotal: float


class PlanIn(BaseModel):
    titulo: str = Field(min_length=1)
    notas: str | None = None
    items: list[PlanItemIn] = []


class PlanOut(BaseModel):
    id: uuid.UUID
    titulo: str
    estado: str
    notas: str | None
    total: float
    items: list[PlanItemOut]
    fecha: datetime


class PlanEstadoIn(BaseModel):
    estado: str


class PlanItemEstadoIn(BaseModel):
    estado: str
