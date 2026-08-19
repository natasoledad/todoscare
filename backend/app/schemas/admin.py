import uuid
from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field


# ---- KPIs ----
class AdminKpis(BaseModel):
    alcance: str  # "plataforma" | "clínica"
    clinicas: int
    pacientes: int
    citas_hoy: int
    ingresos_mes: float


# ---- clínicas / sucursales ----
class ClinicOut(BaseModel):
    id: uuid.UUID
    razon_social: str
    responsable_sanitario: str | None
    pais: str
    activo: bool
    sucursales: int
    pacientes: int


class AltaClinicaIn(BaseModel):
    razon_social: str = Field(min_length=2)
    pais: str = Field(min_length=2, max_length=2)
    responsable_sanitario: str | None = None
    sucursal_nombre: str = Field(min_length=1)
    admin_nombre: str = Field(min_length=2)
    admin_correo: EmailStr
    admin_password: str = Field(min_length=8)


class AltaClinicaOut(BaseModel):
    clinic_id: uuid.UUID
    branch_id: uuid.UUID
    admin_user_id: uuid.UUID


class ClinicUpdate(BaseModel):
    razon_social: str | None = Field(default=None, min_length=2)
    responsable_sanitario: str | None = None


class SucursalIn(BaseModel):
    nombre: str = Field(min_length=1)
    direccion: str | None = None


class SucursalOut(BaseModel):
    id: uuid.UUID
    nombre: str
    direccion: str | None


# ---- usuarios / roles ----
class RoleAssignmentOut(BaseModel):
    id: uuid.UUID
    role: str
    clinic_id: uuid.UUID | None
    branch_id: uuid.UUID | None


class UsuarioOut(BaseModel):
    id: uuid.UUID
    nombre: str
    email: str
    telefono: str | None = None
    activo: bool
    roles: list[RoleAssignmentOut]


class CrearUsuarioIn(BaseModel):
    nombre: str = Field(min_length=2)
    correo: EmailStr
    password: str = Field(min_length=8)
    role: str
    clinic_id: uuid.UUID | None = None
    branch_id: uuid.UUID | None = None


class AsignarRolIn(BaseModel):
    role: str
    clinic_id: uuid.UUID | None = None
    branch_id: uuid.UUID | None = None


class UsuarioUpdate(BaseModel):
    """Edición de la cuenta del usuario (48): datos de identidad. La contraseña
    y el correo son opcionales; solo se tocan si vienen en el cuerpo."""

    nombre: str | None = Field(default=None, min_length=2)
    correo: EmailStr | None = None
    telefono: str | None = Field(default=None, max_length=50)
    password: str | None = Field(default=None, min_length=8)
    activo: bool | None = None


# ---- planes ----
class PlanIn(BaseModel):
    tipo: str = Field(pattern="^(individual|empresa|publico)$")
    esfera: str | None = Field(default=None, pattern="^(federal|estatal|municipal)$")
    nombre: str = Field(min_length=1)
    precio: float = Field(ge=0)
    servicios: dict | None = None


class PlanOut(BaseModel):
    id: uuid.UUID
    tipo: str
    esfera: str | None
    nombre: str
    precio: float


# ---- T&C ----
class TycOut(BaseModel):
    id: uuid.UUID
    pais: str
    version: str
    publicado_en: datetime


class PublicarTycIn(BaseModel):
    pais: str = Field(min_length=2, max_length=2)
    version: str = Field(min_length=1)
    contenido: str = Field(min_length=1)


# ---- finanzas ----
class FinanzasResumen(BaseModel):
    ingresos_mes: float
    split_profesionales: float
    cashback_emitido: float


class LedgerEntryOut(BaseModel):
    fecha: datetime
    tipo: str
    monto: float
    moneda: str
    ref: str | None


# ---- auditoría ----
class AuditOut(BaseModel):
    fecha: datetime
    actor: str | None
    accion: str
    recurso: str
    clinic_id: uuid.UUID | None


# ---- integraciones ----
class IntegracionOut(BaseModel):
    id: uuid.UUID
    tipo: str
    activo: bool


class IntegracionUpdate(BaseModel):
    activo: bool


# ---- permisos personalizados (48) ----
class PermisoOverrideIn(BaseModel):
    clinic_id: uuid.UUID
    resource: str
    action: str
    allow: bool = True


class PermisoOverrideOut(BaseModel):
    id: uuid.UUID
    clinic_id: uuid.UUID
    resource: str
    action: str
    allow: bool


class PermisoCatalogoOut(BaseModel):
    resources: list[str]
    actions: list[str]


# ---- perfiles de acceso reutilizables (48) ----
class PermisoItem(BaseModel):
    resource: str
    action: str


class PerfilAccesoIn(BaseModel):
    clinic_id: uuid.UUID
    nombre: str = Field(min_length=2, max_length=80)
    base_role: str  # empresa | medico | clinic_admin
    permisos: list[PermisoItem] = Field(default_factory=list)
    sin_restriccion: bool = False


class PerfilAccesoUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=80)
    permisos: list[PermisoItem] | None = None
    sin_restriccion: bool | None = None
    activo: bool | None = None


class PerfilAccesoOut(BaseModel):
    id: uuid.UUID
    clinic_id: uuid.UUID
    nombre: str
    base_role: str
    permisos: list[PermisoItem]
    sin_restriccion: bool
    activo: bool
    usuarios: int  # cuántos usuarios lo tienen asignado


class AsignarPerfilIn(BaseModel):
    clinic_id: uuid.UUID
    profile_id: uuid.UUID


class PerfilAsignadoOut(BaseModel):
    id: uuid.UUID  # id de la asignación (UserPermissionProfile)
    clinic_id: uuid.UUID
    profile_id: uuid.UUID
    profile_nombre: str
    base_role: str
