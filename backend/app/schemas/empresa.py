import uuid
from datetime import date, datetime

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


class BranchOut(BaseModel):
    id: uuid.UUID
    nombre: str


class BloqueIn(BaseModel):
    professional_id: uuid.UUID
    branch_id: uuid.UUID
    inicio: datetime
    fin: datetime
    reglas: dict | None = None


class BloqueUpdate(BaseModel):
    inicio: datetime | None = None
    fin: datetime | None = None
    reglas: dict | None = None


class BloqueOut(BaseModel):
    id: uuid.UUID
    professional_id: uuid.UUID
    professional_nombre: str
    branch_nombre: str
    inicio: datetime
    fin: datetime
    reglas: dict | None


# ---- catálogo ----
class ServicioIn(BaseModel):
    nombre: str = Field(min_length=1)
    specialty_id: uuid.UUID | None = None
    precio: float = Field(ge=0)
    duracion_min: int = Field(gt=0)


class ServicioUpdate(BaseModel):
    nombre: str | None = None
    precio: float | None = Field(default=None, ge=0)
    duracion_min: int | None = Field(default=None, gt=0)
    activo: bool | None = None


class ServicioAdminOut(BaseModel):
    id: uuid.UUID
    nombre: str
    precio: float
    duracion_min: int | None
    activo: bool
    specialty_nombre: str | None


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
