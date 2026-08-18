import uuid
from datetime import date, datetime, time

from pydantic import BaseModel, Field


# ---- inicio / KPIs ----
class ServicioVendido(BaseModel):
    nombre: str
    cantidad: int


class KpisOut(BaseModel):
    clinic_nombre: str
    citas_hoy: int
    ingresos_mes: float
    servicios_activos: int
    promos_activas: int
    mas_vendidos: list[ServicioVendido]


# ---- profesionales / agendas ----
class ProfesionalOut(BaseModel):
    id: uuid.UUID
    nombre: str
    # Perfil del profesional (54.1b) — opcionales para no romper consumidores previos.
    specialty_id: uuid.UUID | None = None
    specialty_nombre: str | None = None
    tipo_especialidad: str | None = None  # medica | dental
    duracion_min: int | None = None
    modalidad: str = "presencial"  # presencial | videoconsulta | ambas
    comision_pct: float | None = None  # % de comisión (0–1); None = % por defecto de la clínica
    activo: bool = True


class BranchOut(BaseModel):
    id: uuid.UUID
    nombre: str


class BloqueIn(BaseModel):
    professional_id: uuid.UUID
    branch_id: uuid.UUID
    inicio: datetime
    fin: datetime
    room_id: uuid.UUID | None = None  # recinto (sala/box) donde atiende
    reglas: dict | None = None


class BloqueUpdate(BaseModel):
    inicio: datetime | None = None
    fin: datetime | None = None
    room_id: uuid.UUID | None = None
    reglas: dict | None = None


class BloqueOut(BaseModel):
    id: uuid.UUID
    professional_id: uuid.UUID
    professional_nombre: str
    branch_nombre: str
    inicio: datetime
    fin: datetime
    room_id: uuid.UUID | None
    room_nombre: str | None
    reglas: dict | None


# ---- recintos (salas médicas / boxes dentales) ----
class RecintoIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    numero: int = Field(ge=1)
    tipo: str  # medica | dental
    branch_id: uuid.UUID | None = None


class RecintoUpdate(BaseModel):
    nombre: str | None = None
    numero: int | None = Field(default=None, ge=1)
    activo: bool | None = None


class RecintoOut(BaseModel):
    id: uuid.UUID
    nombre: str
    numero: int
    tipo: str
    activo: bool
    branch_id: uuid.UUID | None


# ---- catálogo ----
class ServicioIn(BaseModel):
    nombre: str = Field(min_length=1)
    specialty_id: uuid.UUID | None = None
    precio: float = Field(ge=0)
    duracion_min: int = Field(gt=0)
    afecto_iva: bool = True  # en Chile las prestaciones médicas/odontológicas van exentas (False)
    comisiona: bool = True    # ¿comisiona al profesional? (lab/insumos = False)


class ServicioUpdate(BaseModel):
    nombre: str | None = None
    precio: float | None = Field(default=None, ge=0)
    duracion_min: int | None = Field(default=None, gt=0)
    activo: bool | None = None
    afecto_iva: bool | None = None
    comisiona: bool | None = None


class ServicioAdminOut(BaseModel):
    id: uuid.UUID
    nombre: str
    precio: float
    duracion_min: int | None
    activo: bool
    specialty_nombre: str | None
    afecto_iva: bool
    comisiona: bool


# ---- promociones ----
class PromocionIn(BaseModel):
    nombre: str = Field(min_length=1)
    descuento: str | None = None
    vigencia_inicio: date | None = None
    vigencia_fin: date | None = None
    segmento: str | None = None
    estado: str = Field(default="Borrador", pattern="^(Activa|Borrador)$")


class PromocionUpdate(BaseModel):
    nombre: str | None = None
    descuento: str | None = None
    vigencia_inicio: date | None = None
    vigencia_fin: date | None = None
    segmento: str | None = None
    estado: str | None = Field(default=None, pattern="^(Activa|Borrador)$")


class PromocionOut(BaseModel):
    id: uuid.UUID
    nombre: str
    descuento: str | None
    vigencia_inicio: date | None
    vigencia_fin: date | None
    segmento: str | None
    estado: str


# ---- info empresa ----
class InfoEmpresaUpdate(BaseModel):
    razon_social: str | None = Field(default=None, min_length=1)
    responsable_sanitario: str | None = None


class InfoEmpresaOut(BaseModel):
    clinic_id: uuid.UUID
    razon_social: str
    responsable_sanitario: str | None
    pais: str
    sucursales: list[BranchOut]


# ---- funcionarios B2B ----
class FuncionarioIn(BaseModel):
    correo: str
    plan_id: uuid.UUID | None = None


class FuncionarioOut(BaseModel):
    id: uuid.UUID
    nombre: str
    correo: str
    estado: str


# ---- agenda de la clínica (vista gerencia) ----
class CitaAgendaOut(BaseModel):
    id: uuid.UUID
    inicio: datetime
    fin: datetime
    paciente_id: uuid.UUID
    paciente_nombre: str
    profesional_id: uuid.UUID
    profesional_nombre: str
    servicio_nombre: str | None
    estado: str
    monto: float | None          # facturado, o precio estimado del servicio
    facturado: bool              # ya hay ingreso asentado en el ledger para esta cita
    pagado: bool = False         # ya se registró un pago de caja ligado a esta cita (Tanda 2)


class AgendaDiaOut(BaseModel):
    fecha: date
    total: int
    por_estado: dict[str, int]
    citas: list[CitaAgendaOut]


class CambiarEstadoIn(BaseModel):
    estado: str


# ---- Tanda 4: pacientes (listado con deudas) ----
class PacienteListaOut(BaseModel):
    id: uuid.UUID
    nombre: str
    rut: str
    activo: bool
    n_tratamientos: int
    deuda: float


class PacienteEstadoIn(BaseModel):
    activo: bool


# ---- Tanda 4: panel de desempeño ----
class DesempenoProfesional(BaseModel):
    nombre: str
    atenciones: int
    ventas: float
    a_pagar: float
    pct: float | None


class DesempenoGrupo(BaseModel):
    grupo: str
    cantidad: int
    monto: float
    ticket_medio: float


class DesempenoOut(BaseModel):
    periodo: str
    ventas: float
    recaudado: float
    atenciones: int
    ticket_medio: float
    por_profesional: list[DesempenoProfesional]
    por_grupo: list[DesempenoGrupo]


# ---- especialidades (54) ----
class EspecialidadIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    tipo: str = Field(pattern="^(medica|dental)$")  # medica | dental
    icono: str | None = Field(default=None, max_length=10)


class EspecialidadUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=120)
    tipo: str | None = Field(default=None, pattern="^(medica|dental)$")
    icono: str | None = Field(default=None, max_length=10)
    activo: bool | None = None


class EspecialidadOut(BaseModel):
    id: uuid.UUID
    nombre: str
    tipo: str
    icono: str | None
    activo: bool


# ---- perfil del profesional (54.1b) ----
class PerfilProfesionalUpdate(BaseModel):
    specialty_id: uuid.UUID | None = None
    duracion_min: int | None = Field(default=None, gt=0)
    modalidad: str | None = Field(default=None, pattern="^(presencial|videoconsulta|ambas)$")
    color: str | None = Field(default=None, max_length=9)
    comision_pct: float | None = Field(default=None, ge=0, le=1)
    activo: bool | None = None


# ---- motivos de atención (54.9) ----
class MotivoIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    specialty_id: uuid.UUID | None = None


class MotivoUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=120)
    specialty_id: uuid.UUID | None = None
    activo: bool | None = None


class MotivoOut(BaseModel):
    id: uuid.UUID
    nombre: str
    specialty_id: uuid.UUID | None
    specialty_nombre: str | None
    activo: bool


# ---- estado del profesional (55) ----
class EstadoProfesionalIn(BaseModel):
    activo: bool


class RemanejoIn(BaseModel):
    destino_id: uuid.UUID  # profesional activo al que se reasignan las citas futuras


class RemanejoOut(BaseModel):
    origen_id: uuid.UUID
    destino_id: uuid.UUID
    destino_nombre: str
    movidas: int       # citas futuras reasignadas
    conflictos: int    # citas que no se pudieron mover (choque de horario/recinto en el destino)


# ---- horario semanal recurrente (52) ----
class HorarioIn(BaseModel):
    professional_id: uuid.UUID
    branch_id: uuid.UUID
    dia_semana: int = Field(ge=0, le=6)  # 0=lunes … 6=domingo
    hora_inicio: time
    hora_fin: time
    descanso_inicio: time | None = None
    descanso_fin: time | None = None
    modalidad: str = Field(default="presencial", pattern="^(presencial|videoconsulta|ambas)$")
    capacidad: int = Field(default=1, ge=1)
    room_id: uuid.UUID | None = None


class HorarioUpdate(BaseModel):
    hora_inicio: time | None = None
    hora_fin: time | None = None
    descanso_inicio: time | None = None
    descanso_fin: time | None = None
    modalidad: str | None = Field(default=None, pattern="^(presencial|videoconsulta|ambas)$")
    capacidad: int | None = Field(default=None, ge=1)
    room_id: uuid.UUID | None = None
    activo: bool | None = None


class HorarioOut(BaseModel):
    id: uuid.UUID
    professional_id: uuid.UUID
    professional_nombre: str
    branch_id: uuid.UUID
    branch_nombre: str
    room_id: uuid.UUID | None
    room_nombre: str | None
    dia_semana: int
    hora_inicio: time
    hora_fin: time
    descanso_inicio: time | None
    descanso_fin: time | None
    modalidad: str
    capacidad: int
    activo: bool


class GenerarBloquesIn(BaseModel):
    professional_id: uuid.UUID | None = None  # None = todos los profesionales de la clínica
    desde: date
    hasta: date


class GenerarBloquesOut(BaseModel):
    generados: int
    omitidos: int   # ya existía un bloque solapado (idempotente) o chocaba con recinto
    dias: int


# ---- bloqueos negativos de agenda (51 / 52.9) ----
class BloqueoIn(BaseModel):
    professional_id: uuid.UUID
    branch_id: uuid.UUID | None = None  # None = todas las sucursales
    inicio: datetime
    fin: datetime
    motivo: str | None = Field(default=None, max_length=160)


class BloqueoOut(BaseModel):
    id: uuid.UUID
    professional_id: uuid.UUID
    professional_nombre: str
    branch_id: uuid.UUID | None
    branch_nombre: str | None
    inicio: datetime
    fin: datetime
    motivo: str | None
    creado_por: str | None  # auditoría "creado por" (51.6)
