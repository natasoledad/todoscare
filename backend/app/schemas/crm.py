import uuid
from datetime import datetime

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
