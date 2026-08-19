import uuid
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base, TenantMixin


class DentalLab(Base, AuditMixin, TenantMixin):
    """Laboratorio dental con el que trabaja la clínica (57.1). Se le encargan
    trabajos (coronas, prótesis, férulas…) y se le llevan cuentas por pagar."""

    __tablename__ = "dental_labs"

    nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    rut: Mapped[str | None] = mapped_column(String(50))         # tax id del laboratorio
    contacto: Mapped[str | None] = mapped_column(String(255))   # email/teléfono/persona
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")


class LabService(Base, AuditMixin, TenantMixin):
    """Prestación que ofrece un laboratorio (57.3b). Distingue el `costo` —lo que
    la clínica le paga al laboratorio— del `precio` —lo que la clínica le cobra
    al paciente—; el margen es la diferencia. Cada laboratorio tiene su propia
    lista (el mismo trabajo puede costar distinto en cada uno)."""

    __tablename__ = "lab_services"

    lab_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("dental_labs.id"), nullable=False, index=True)
    nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    costo: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, server_default="0")   # lo que se paga al lab
    precio: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, server_default="0")  # lo que se cobra al paciente
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
