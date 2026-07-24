import uuid
from datetime import date, datetime

from pydantic import BaseModel


class ClinicFilaCRM(BaseModel):
    clinic_id: uuid.UUID
    razon_social: str
    pais: str
    ingresos: float
    margen: float | None  # None => sin base para calcularlo (ingresos = 0)
    variacion: float | None  # None => sin mes anterior comparable
    pacientes: int


class ConsolidadoOut(BaseModel):
    alcance: str  # plataforma | clínica
    period: str  # 'YYYY-MM'
    ingresos_totales: float
    variacion: float | None
    n_clinicas: int
    n_pacientes: int
    clinicas: list[ClinicFilaCRM]


class IngresoServicio(BaseModel):
    servicio: str
    monto: float


class MarketingKpis(BaseModel):
    gasto_marketing: float
    nuevos_pacientes: int
    cac: float | None  # costo de adquisición de cliente
    ltv: float | None  # valor de vida (ARPU histórico como proxy)
    ltv_cac_ratio: float | None  # retorno de la inversión en captación
    roas: float | None  # ingresos del período / gasto de marketing


class DetalleClinicaOut(BaseModel):
    clinic_id: uuid.UUID
    razon_social: str
    pais: str
    period: str
    ingresos: float
    variacion: float | None
    margen: float | None
    ticket_promedio: float
    n_atenciones: int
    cuentas_por_cobrar: float
    ocupacion: float  # 0..1
    por_liquidar: float
    marketing: MarketingKpis
    ingresos_por_servicio: list[IngresoServicio]


class LiquidacionOut(BaseModel):
    split_id: uuid.UUID
    clinic_id: uuid.UUID
    razon_social: str
    prestador: str
    monto: float
    fecha: datetime
    estado: str


class ConciliarOut(BaseModel):
    split_id: uuid.UUID
    estado: str
    conciliado_at: datetime | None


class AsientoExportOut(BaseModel):
    fecha: datetime
    clinica: str
    tipo: str
    monto: float
    moneda: str
    ref: str | None


# ── Marketing digital: campañas ──
class CampanaOut(BaseModel):
    id: uuid.UUID
    clinic_id: uuid.UUID
    nombre: str
    canal: str
    estado: str
    presupuesto: float
    gasto: float
    leads: int
    conversiones: int
    fecha_inicio: date | None
    fecha_fin: date | None
    cpl: float | None  # costo por lead
    cac: float | None  # costo por adquisición (gasto / conversiones)
    conversion_rate: float | None
    presupuesto_usado: float | None  # 0..1


class CampanasResumen(BaseModel):
    campanas: int
    activas: int
    inversion: float
    gasto: float
    leads: int
    conversiones: int
    cac_promedio: float | None
    conversion_rate: float | None


class CampanasOut(BaseModel):
    resumen: CampanasResumen
    items: list[CampanaOut]


class CrearCampanaIn(BaseModel):
    clinic_id: uuid.UUID | None = None  # requerido para super_admin; la empresa usa la suya
    nombre: str
    canal: str
    presupuesto: float = 0
    gasto: float = 0
    leads: int = 0
    conversiones: int = 0
    fecha_inicio: date | None = None
    fecha_fin: date | None = None


class ActualizarCampanaIn(BaseModel):
    estado: str | None = None
    leads: int | None = None
    conversiones: int | None = None
    gasto_adicional: float | None = None
