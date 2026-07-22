import uuid

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base, TenantMixin


class Plan(Base, AuditMixin):
    """Platform-wide (Super-Admin managed) — individual, empresa, or público
    plans, the latter split into 3 activable esferas (Spec Admin §6.3)."""

    __tablename__ = "plans"

    tipo: Mapped[str] = mapped_column(String(20), nullable=False)  # individual | empresa | publico
    esfera: Mapped[str | None] = mapped_column(String(20))  # federal | estatal | municipal (solo si tipo=publico)
    nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    precio: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    servicios: Mapped[dict | None] = mapped_column(JSONB)


class Subscription(Base, AuditMixin):
    """Not TenantMixin: the owner is exactly one of clinic/company/patient,
    and a patient's plan isn't necessarily scoped to a single clinic."""

    __tablename__ = "subscriptions"

    plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("plans.id"), nullable=False, index=True)
    clinic_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("clinics.id"))
    company_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"))
    patient_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"))
    estado: Mapped[str] = mapped_column(String(20), nullable=False, server_default="activa")
    periodo: Mapped[str | None] = mapped_column(String(20))  # e.g. "2026-07"


class Company(Base, AuditMixin, TenantMixin):
    """B2B contratante managed under the clinic that sells it the plan
    (Spec Empresa Cliente §1 callout — open question on multi-clinic B2B)."""

    __tablename__ = "companies"

    razon_social: Mapped[str] = mapped_column(String(255), nullable=False)


class CompanyEmployee(Base, AuditMixin, TenantMixin):
    __tablename__ = "company_employees"

    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True)
    plan_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("plans.id"))
    estado: Mapped[str] = mapped_column(String(20), nullable=False, server_default="activo")  # activo | baja


class LedgerEntry(Base, AuditMixin, TenantMixin):
    """INSERT-only. Locked down further at the DB level (app role has no
    UPDATE/DELETE grant on this table — see the initial migration) so
    immutability holds even against a bug or a compromised app role."""

    __tablename__ = "ledger_entries"

    tipo: Mapped[str] = mapped_column(String(50), nullable=False)  # ingreso | egreso | split | cashback_emitido | ...
    monto: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    moneda: Mapped[str] = mapped_column(String(3), nullable=False, server_default="CLP")
    ref: Mapped[str | None] = mapped_column(String(255))


class PaymentSplit(Base, AuditMixin, TenantMixin):
    __tablename__ = "payment_splits"

    ledger_entry_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ledger_entries.id"), nullable=False, index=True)
    beneficiario_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    monto: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    regla: Mapped[dict | None] = mapped_column(JSONB)
