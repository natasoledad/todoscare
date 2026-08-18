import uuid
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base, TenantMixin


class Arancel(Base, AuditMixin, TenantMixin):
    """Tabla de precios (punto 62). Una clínica puede tener varias: la base, una
    'particular', una por convenio/empresa… De cada arancel cuelgan categorías y,
    dentro de ellas, las prestaciones con su precio. Coexiste con el catálogo de
    servicios (`CatalogItem`), que sigue gobernando lo agendable; el arancel es la
    lista de precios para cotizar/cobrar."""

    __tablename__ = "price_tariffs"

    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False, server_default="particular")  # base | particular | empresa
    es_base: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")  # el arancel base del que heredan los demás
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")


class ArancelCategoria(Base, AuditMixin, TenantMixin):
    """Categoría dentro de un arancel (Cirugía, Odontopediatría, Insumos…)."""

    __tablename__ = "price_tariff_categories"

    arancel_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("price_tariffs.id"), nullable=False, index=True)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    orden: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")


class ArancelItem(Base, AuditMixin, TenantMixin):
    """Prestación con precio dentro de un arancel/categoría (62.5).

      · `codigo`            código humano definido por la clínica (CB01, MJCS10…).
      · `precio`            precio final que se cobra al paciente.
      · `precio_referencia` valor referencial (ej. Fonasa) para comparar (62.16).
      · `permite_descuento` ¿aplica descuento comercial? (62.6).
      · `comisiona`         ¿comisiona al profesional? (62.7 / 57.10)."""

    __tablename__ = "price_tariff_items"

    arancel_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("price_tariffs.id"), nullable=False, index=True)
    categoria_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("price_tariff_categories.id"), index=True)
    codigo: Mapped[str | None] = mapped_column(String(40))
    nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    precio: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, server_default="0")
    precio_referencia: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    permite_descuento: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    comisiona: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
