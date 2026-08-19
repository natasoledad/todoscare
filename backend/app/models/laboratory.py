import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String
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


class LabOrder(Base, AuditMixin, TenantMixin):
    """Orden de trabajo enviada a un laboratorio (57.11).

    Sigue un flujo de estados (solicitado -> en_proceso -> en_revision ->
    terminado, o cancelado). Puede nacer del plan de tratamiento del paciente
    (57.12: `treatment_plan_id` + `patient_id`), lo que enlaza el trabajo del
    lab con la ficha. `costo` es lo que se le pagará al laboratorio y alimenta
    las cuentas por pagar (57.6); `pagado` marca cuándo se saldó."""

    __tablename__ = "lab_orders"

    lab_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("dental_labs.id"), nullable=False, index=True)
    lab_service_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("lab_services.id"), index=True)
    patient_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), index=True)
    treatment_plan_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("treatment_plans.id"), index=True)
    professional_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    descripcion: Mapped[str] = mapped_column(String(255), nullable=False)
    pieza: Mapped[str | None] = mapped_column(String(10))  # notación FDI
    costo: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, server_default="0")   # a pagar al lab
    precio: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, server_default="0")  # a cobrar al paciente
    estado: Mapped[str] = mapped_column(String(20), nullable=False, server_default="solicitado")
    # solicitado | en_proceso | en_revision | terminado | cancelado
    fecha_entrega: Mapped[date | None] = mapped_column(Date)
    pagado: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    pagado_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notas: Mapped[str | None] = mapped_column(String(500))
