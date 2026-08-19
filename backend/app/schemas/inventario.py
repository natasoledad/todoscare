import uuid

from pydantic import BaseModel, Field


# ---- proveedores (56.16) ----
class ProveedorIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=255)
    rut: str | None = Field(default=None, max_length=50)
    contacto: str | None = Field(default=None, max_length=255)


class ProveedorUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=255)
    rut: str | None = Field(default=None, max_length=50)
    contacto: str | None = Field(default=None, max_length=255)
    activo: bool | None = None


class ProveedorOut(BaseModel):
    id: uuid.UUID
    nombre: str
    rut: str | None
    contacto: str | None
    activo: bool


# ---- centros de costo (56.14) ----
class CentroCostoIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)


class CentroCostoUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=120)
    activo: bool | None = None


class CentroCostoOut(BaseModel):
    id: uuid.UUID
    nombre: str
    activo: bool


# ---- bodegas (56.2) ----
class BodegaIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    branch_id: uuid.UUID | None = None


class BodegaUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=120)
    branch_id: uuid.UUID | None = None
    activo: bool | None = None


class BodegaOut(BaseModel):
    id: uuid.UUID
    nombre: str
    branch_id: uuid.UUID | None
    branch_nombre: str | None
    activo: bool


# ---- ítems de insumo (56.7 stock mínimo) ----
class ItemIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=255)
    sku: str | None = Field(default=None, max_length=60)
    unidad: str = Field(default="unidad", max_length=20)
    stock_minimo: float = Field(default=0, ge=0)
    supplier_id: uuid.UUID | None = None
    cost_center_id: uuid.UUID | None = None


class ItemUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=255)
    sku: str | None = Field(default=None, max_length=60)
    unidad: str | None = Field(default=None, max_length=20)
    stock_minimo: float | None = Field(default=None, ge=0)
    supplier_id: uuid.UUID | None = None
    cost_center_id: uuid.UUID | None = None
    activo: bool | None = None


class ItemOut(BaseModel):
    id: uuid.UUID
    nombre: str
    sku: str | None
    unidad: str
    stock_minimo: float
    supplier_id: uuid.UUID | None
    supplier_nombre: str | None
    cost_center_id: uuid.UUID | None
    cost_center_nombre: str | None
    activo: bool
