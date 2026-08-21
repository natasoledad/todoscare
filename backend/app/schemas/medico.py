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


# ---- odontograma (70.11): caras + diagnóstico/tratamiento ----
class OdontogramaCaraIn(BaseModel):
    dx: str | None = None          # diagnóstico en la cara (p. ej. caries)
    tx: str | None = None          # tratamiento en la cara (p. ej. obturación)
    tx_estado: str | None = None   # planificado | realizado


class OdontogramaPiezaIn(BaseModel):
    pieza: str | None = None       # estado de la pieza completa (ausente, corona, …)
    estado: str | None = None      # legacy: pendiente | tratada (compatibilidad)
    caras: dict[str, OdontogramaCaraIn] | None = None


class OdontogramaUpdateInput(BaseModel):
    piezas: dict[str, OdontogramaPiezaIn]


class MarcaCatalogo(BaseModel):
    codigo: str
    label: str


class OdontogramaCatalogoOut(BaseModel):
    caras: list[MarcaCatalogo]
    diagnosticos: list[MarcaCatalogo]
    tratamientos: list[MarcaCatalogo]
    pieza_estados: list[MarcaCatalogo]
    tx_estados: list[MarcaCatalogo]


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


# ---- financiamiento en cuotas (69.19) ----
class PlanCuotasIn(BaseModel):
    n_cuotas: int = Field(ge=1, le=60)
    primer_vencimiento: date
    periodicidad_dias: int = Field(default=30, ge=1, le=365)
    monto_total: float | None = None   # por defecto: total neto del plan


class CuotaOut(BaseModel):
    id: uuid.UUID
    numero: int
    monto: float
    vencimiento: date
    pagado: bool
    pagado_at: datetime | None = None


class CuotaUpdate(BaseModel):
    pagado: bool


class CuotasResumenOut(BaseModel):
    cuotas: list[CuotaOut]
    total: float
    pagado: float
    pendiente: float


# ---- presupuesto imprimible (69.11) ----
class PresupuestoOut(BaseModel):
    plan: PlanOut
    paciente_nombre: str
    paciente_rut: str | None = None
    profesional_nombre: str
    clinica_nombre: str | None = None
    clinica_logo: str | None = None
    cuotas: list[CuotaOut]


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


# ---- vademécum + plantillas de receta (71.21) ----
class VademecumOut(BaseModel):
    id: uuid.UUID
    nombre: str
    principio_activo: str | None = None
    presentacion: str | None = None
    forma: str | None = None


class RecetaItem(BaseModel):
    medicamento: str = Field(min_length=1)
    cantidad: str | None = None
    indicaciones: str | None = None


class RecetaPlantillaIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=160)
    items: list[RecetaItem] = Field(default_factory=list)


class RecetaPlantillaUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=160)
    items: list[RecetaItem] | None = None
    activo: bool | None = None


class RecetaPlantillaOut(BaseModel):
    id: uuid.UUID
    nombre: str
    items: list[RecetaItem]
    activo: bool


# ---- fichas clínicas por especialidad (71.7) ----
class CampoFicha(BaseModel):
    clave: str = Field(min_length=1, max_length=60)
    label: str = Field(min_length=1, max_length=120)
    tipo: str = "texto"                 # texto | area | numero | opcion | checkbox
    opciones: list[str] | None = None   # para tipo=opcion


class FichaEspIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=255)
    specialty_id: uuid.UUID | None = None
    campos: list[CampoFicha] = Field(default_factory=list)


class FichaEspUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=255)
    campos: list[CampoFicha] | None = None
    activo: bool | None = None


class FichaEspOut(BaseModel):
    id: uuid.UUID
    nombre: str
    specialty_id: uuid.UUID | None
    campos: list[CampoFicha]
    activo: bool


# ---- diagnóstico CIE-10 (71.20) ----
class Cie10Out(BaseModel):
    id: uuid.UUID
    codigo: str
    descripcion: str
    categoria: str | None = None


class DiagnosticoIn(BaseModel):
    codigo: str = Field(min_length=1)          # código CIE-10 (p. ej. "K02.1")
    tipo: str = "principal"                     # principal | secundario
    observacion: str | None = Field(default=None, max_length=500)
    record_id: uuid.UUID | None = None          # atención a la que se asocia (opcional)


class DiagnosticoOut(BaseModel):
    id: uuid.UUID
    codigo: str
    descripcion: str
    categoria: str | None = None
    tipo: str
    observacion: str | None = None
    fecha: datetime


# ---- evoluciones con doble firma + anulación (70.6) ----
class EvolucionIn(BaseModel):
    texto: str = Field(min_length=1)
    record_id: uuid.UUID | None = None


class AnularEvolucionIn(BaseModel):
    motivo: str = Field(min_length=3, max_length=500)


class EvolucionOut(BaseModel):
    id: uuid.UUID
    texto: str
    fecha: datetime
    autor_id: uuid.UUID
    autor_nombre: str
    firmado_at: datetime
    firma_tratante: str | None = None
    cofirmado_por_nombre: str | None = None
    cofirmado_at: datetime | None = None
    firma_cofirmante: str | None = None
    estado: str
    motivo_anulacion: str | None = None
    anulado_at: datetime | None = None
    anulado_por_nombre: str | None = None


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
# Periodontograma completo (70.5): hasta 6 sitios por pieza (mv/v/dv/mp/p/dp)
# con profundidad de sondaje (ps), recesión (rec) y sangrado; más movilidad y
# furca por pieza. Compatible hacia atrás con el shape simple {ps, sangrado}.
class PerioSitioIn(BaseModel):
    ps: int | None = None          # profundidad de sondaje (mm)
    rec: int | None = None         # recesión / margen gingival (mm; NIC = ps + rec)
    sangrado: bool | None = None   # sangrado al sondaje
    placa: bool | None = None
    supuracion: bool | None = None


class PerioPiezaIn(BaseModel):
    ps: int | None = None          # legacy: profundidad simple de la pieza
    sangrado: bool | None = None   # legacy: sangrado simple
    movilidad: int | None = None   # 0–3
    furca: int | None = None       # 0–3
    sitios: dict[str, PerioSitioIn] | None = None


class PeriodontogramaIn(BaseModel):
    datos: dict[str, PerioPiezaIn]
    notas: str | None = None


class PeriodontogramaOut(BaseModel):
    id: uuid.UUID
    datos: dict
    notas: str | None
    fecha: datetime
    tomas_anteriores: int


class PerioCatalogoOut(BaseModel):
    sitios: list[MarcaCatalogo]
    ps_max: int
    movilidad_max: int
    furca_max: int


# ---- timeline clínico unificado (70.1) ----
class TimelineEvento(BaseModel):
    tipo: str            # prontuario | prescripcion | orden_examen | plan | periodontograma | documento | signos
    fecha: datetime
    titulo: str
    resumen: str | None
    icono: str
    estado: str | None = None
