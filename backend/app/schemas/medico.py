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


class PlanResumen(BaseModel):
    total_bruto: float   # suma de los ítems
    descuento_pct: float
    descuento: float     # monto del descuento comercial
    total_neto: float    # total_bruto - descuento (presupuesto a cobrar)
    realizado: float     # ítems ya realizados
    abonado: float       # pagos de caja atribuidos al plan
    saldo: float         # total_neto - abonado
    progreso_pct: float  # realizado / total_bruto


class PlanOut(BaseModel):
    id: uuid.UUID
    titulo: str
    estado: str
    notas: str | None
    total: float
    descuento_pct: float
    items: list[PlanItemOut]
    resumen: PlanResumen
    fecha: datetime


class PlanUpdate(BaseModel):
    titulo: str | None = Field(default=None, min_length=1)
    notas: str | None = None
    descuento_pct: float | None = Field(default=None, ge=0, le=1)


class PlanEstadoIn(BaseModel):
    estado: str


class PlanItemEstadoIn(BaseModel):
    estado: str


# ---- Tanda 5: documentos clínicos ----
class DocumentoIn(BaseModel):
    tipo: str          # consentimiento | licencia | interconsulta | certificado | otro
    titulo: str = Field(min_length=1)
    contenido: str | None = None
    # Documentos por plantilla (64): si viene `template_id`, el contenido se
    # arma desde sus bloques rellenando `campos`; `requiere_firma` hereda de la
    # plantilla salvo que se especifique.
    template_id: uuid.UUID | None = None
    campos: dict | None = None
    requiere_firma: bool | None = None


class DocumentoOut(BaseModel):
    id: uuid.UUID
    tipo: str
    titulo: str
    contenido: str | None
    estado: str
    fecha: datetime
    requiere_firma: bool = False
    firmado_paciente: bool = False
    firmado_at: datetime | None = None
    firma_profesional: str | None = None  # firma manuscrita estampada (data URL PNG)


# ---- firma manuscrita del profesional (48) ----
class MiFirmaOut(BaseModel):
    firma: str | None = None
    especialidad: str | None = None


class MiFirmaIn(BaseModel):
    firma: str | None = None  # data URL PNG (o null para borrarla)


# ---- plantillas de documento (64.3) ----
class BloqueDoc(BaseModel):
    tipo: str  # parrafo | campo
    texto: str | None = None    # parrafo: texto fijo
    label: str | None = None    # campo: etiqueta
    clave: str | None = None    # campo: clave para `campos`


class PlantillaDocIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=255)
    tipo: str = Field(pattern="^(consentimiento|certificado|otro)$")
    bloques: list[BloqueDoc] = []
    requiere_firma: bool = False


class PlantillaDocUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=255)
    tipo: str | None = Field(default=None, pattern="^(consentimiento|certificado|otro)$")
    bloques: list[BloqueDoc] | None = None
    requiere_firma: bool | None = None
    activo: bool | None = None


class PlantillaDocOut(BaseModel):
    id: uuid.UUID
    nombre: str
    tipo: str
    bloques: list[BloqueDoc]
    requiere_firma: bool
    activo: bool


# ---- Tanda 5: periodontograma ----
class PeriodontogramaIn(BaseModel):
    datos: dict          # { "1.6": {"ps": 3, "sangrado": true}, ... }
    notas: str | None = None


class PeriodontogramaOut(BaseModel):
    id: uuid.UUID
    datos: dict
    notas: str | None
    fecha: datetime
    tomas_anteriores: int


# ---- timeline clínico unificado (70.1) ----
class TimelineEvento(BaseModel):
    tipo: str            # prontuario | prescripcion | orden_examen | plan | periodontograma | documento | signos
    fecha: datetime
    titulo: str
    resumen: str | None
    icono: str
    estado: str | None = None
