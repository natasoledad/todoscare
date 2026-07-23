import uuid
from datetime import date, datetime

from pydantic import BaseModel


class AseguradoraKpis(BaseModel):
    insurer_nombre: str
    tipo: str
    afiliados: int
    autorizaciones_pendientes: int
    atenciones_mes: int
    por_liquidar: float


class ConvenioOut(BaseModel):
    agreement_id: uuid.UUID
    clinic_id: uuid.UUID
    clinica: str
    vigencia_inicio: date | None
    vigencia_fin: date | None
    vigente: bool
    aranceles: int


class ArancelOut(BaseModel):
    arancel_id: uuid.UUID
    service_id: uuid.UUID
    servicio: str
    cobertura_pct: float
    copago: float


class CrearArancelIn(BaseModel):
    service_id: uuid.UUID
    cobertura_pct: float
    copago: float = 0


class AfiliadoOut(BaseModel):
    affiliate_id: uuid.UUID
    patient_id: uuid.UUID | None
    nombre: str | None
    documento_identidad: str
    plan_cobertura: str | None
    vigencia_desde: date | None
    vigencia_hasta: date | None
    vigente: bool


class AltaAfiliadoIn(BaseModel):
    documento_identidad: str
    plan_cobertura: str | None = None
    vigencia_desde: date | None = None
    vigencia_hasta: date | None = None


class AutorizacionOut(BaseModel):
    authorization_id: uuid.UUID
    agreement_id: uuid.UUID
    patient_id: uuid.UUID
    paciente: str
    servicio: str
    clinica: str
    estado: str
    motivo_rechazo: str | None
    resuelto_en: datetime | None
    fecha: datetime


class ResolverIn(BaseModel):
    decision: str  # aprobar | rechazar | pedir_info
    motivo: str | None = None


class ResolverOut(BaseModel):
    authorization_id: uuid.UUID
    estado: str
    motivo_rechazo: str | None
    resuelto_en: datetime | None


class LiquidacionOut(BaseModel):
    settlement_id: uuid.UUID
    agreement_id: uuid.UUID
    clinica: str
    periodo: str
    monto: float
    estado: str
    pagado_at: datetime | None


class GenerarLiquidacionIn(BaseModel):
    periodo: str  # 'YYYY-MM'


class LiquidacionResultOut(BaseModel):
    settlement_id: uuid.UUID
    periodo: str
    monto: float
    estado: str


class PagoOut(BaseModel):
    settlement_id: uuid.UUID
    estado: str
    pagado_at: datetime | None


class RedOut(BaseModel):
    clinic_id: uuid.UUID
    clinica: str
    pais: str
    vigente: bool


class PrestacionAutorizada(BaseModel):
    servicio: str
    diagnostico: str | None


class FichaAfiliadoOut(BaseModel):
    patient_id: uuid.UUID
    nombre: str
    documento_identidad: str | None
    plan_cobertura: str | None
    prestaciones_autorizadas: list[PrestacionAutorizada]
