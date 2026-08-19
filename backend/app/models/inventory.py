import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base, TenantMixin


class Supplier(Base, AuditMixin, TenantMixin):
    """Proveedor de insumos (Medilink §inventario, 56.16). Se referencia en las
    entradas de stock y permite después las cuentas por pagar."""

    __tablename__ = "suppliers"

    nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    rut: Mapped[str | None] = mapped_column(String(50))         # tax id del proveedor
    contacto: Mapped[str | None] = mapped_column(String(255))   # email/teléfono/persona
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")


class CostCenter(Base, AuditMixin, TenantMixin):
    """Centro de costo (56.14). Clasifica los consumos de inventario por área
    (esterilización, box 1, laboratorio…) para reportar el gasto."""

    __tablename__ = "cost_centers"

    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")


class Warehouse(Base, AuditMixin, TenantMixin):
    """Bodega / almacén (56.2). Puede colgar de una sucursal o ser central
    (branch_id NULL). El stock vive por bodega (un mismo insumo puede tener
    existencias distintas en cada una)."""

    __tablename__ = "warehouses"

    branch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("branches.id"), index=True)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")


class InventoryItem(Base, AuditMixin, TenantMixin):
    """Insumo de inventario (guantes, anestesia, fresas…). Distinto del
    CatalogItem (prestaciones que se cobran): esto es lo que se consume y se
    controla en bodega. `stock_minimo` alimenta el semáforo de reposición
    (56.7). El proveedor y el centro de costo por defecto son sugerencias que
    heredan las entradas/salidas."""

    __tablename__ = "inventory_items"
    __table_args__ = (UniqueConstraint("clinic_id", "sku", name="uq_inventory_item_clinic_sku"),)

    nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    sku: Mapped[str | None] = mapped_column(String(60))          # código interno (opcional, único por clínica)
    unidad: Mapped[str] = mapped_column(String(20), nullable=False, server_default="unidad")  # unidad|caja|ml|g…
    stock_minimo: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0")
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("suppliers.id"), index=True)
    cost_center_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("cost_centers.id"), index=True)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")


class StockLot(Base, AuditMixin, TenantMixin):
    """Lote de un insumo en una bodega (56.9). Guarda la existencia real:
    `cantidad` es la fuente de verdad del stock (el kardex es la bitácora). Un
    lote puede llevar código y vencimiento para el control FEFO (primero el que
    vence antes). El stock de un ítem = suma de sus lotes."""

    __tablename__ = "stock_lots"

    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("inventory_items.id"), nullable=False, index=True)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouses.id"), nullable=False, index=True)
    lote: Mapped[str | None] = mapped_column(String(60))
    vencimiento: Mapped[date | None] = mapped_column(Date, index=True)
    cantidad: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0")


class StockMovement(Base, AuditMixin, TenantMixin):
    """Kardex: bitácora inmutable de todo movimiento de stock (56.11).

    `tipo` = entrada | salida | ajuste. `cantidad` va con signo (entrada +,
    salida -, ajuste el delta aplicado). `saldo` es el stock total del item
    tras el movimiento (para leer el kardex sin recomputar). Nunca se edita ni
    se borra: las correcciones son un nuevo ajuste."""

    __tablename__ = "stock_movements"

    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("inventory_items.id"), nullable=False, index=True)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouses.id"), nullable=False, index=True)
    lot_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("stock_lots.id"), index=True)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)  # entrada | salida | ajuste
    cantidad: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)  # con signo
    saldo: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)     # stock total del item tras el movimiento
    motivo: Mapped[str | None] = mapped_column(String(255))
    cost_center_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("cost_centers.id"), index=True)
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("suppliers.id"), index=True)
