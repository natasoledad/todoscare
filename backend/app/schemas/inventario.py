import uuid
from datetime import date, datetime

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
    stock_actual: float          # suma de lotes (56.11)
    estado: str                  # semáforo: ok | bajo | sin_stock (56.7)
    supplier_id: uuid.UUID | None
    supplier_nombre: str | None
    cost_center_id: uuid.UUID | None
    cost_center_nombre: str | None
    activo: bool


# ---- movimientos de stock (56.9 · 56.11) ----
class EntradaIn(BaseModel):
    warehouse_id: uuid.UUID
    cantidad: float = Field(gt=0)
    lote: str | None = Field(default=None, max_length=60)
    vencimiento: date | None = None
    supplier_id: uuid.UUID | None = None
    cost_center_id: uuid.UUID | None = None
    motivo: str | None = Field(default=None, max_length=255)


class SalidaIn(BaseModel):
    warehouse_id: uuid.UUID
    cantidad: float = Field(gt=0)
    cost_center_id: uuid.UUID | None = None
    motivo: str | None = Field(default=None, max_length=255)


class AjusteIn(BaseModel):
    lot_id: uuid.UUID
    cantidad_nueva: float = Field(ge=0)
    motivo: str | None = Field(default=None, max_length=255)


class LoteOut(BaseModel):
    id: uuid.UUID
    warehouse_id: uuid.UUID
    warehouse_nombre: str | None
    item_id: uuid.UUID
    item_nombre: str | None
    lote: str | None
    vencimiento: date | None
    cantidad: float
    estado: str  # vigente | por_vencer | vencido | sin_vencimiento


class MovimientoStockOut(BaseModel):
    id: uuid.UUID
    tipo: str
    cantidad: float
    saldo: float
    warehouse_nombre: str | None
    motivo: str | None
    cost_center_nombre: str | None
    supplier_nombre: str | None
    fecha: datetime


class StockPorBodega(BaseModel):
    warehouse_id: uuid.UUID
    warehouse_nombre: str | None
    cantidad: float


class StockOut(BaseModel):
    item_id: uuid.UUID
    stock_actual: float
    stock_minimo: float
    estado: str
    por_bodega: list[StockPorBodega]


class AlertasOut(BaseModel):
    bajo_minimo: list[ItemOut]
    lotes_por_vencer: list[LoteOut]
    lotes_vencidos: list[LoteOut]
