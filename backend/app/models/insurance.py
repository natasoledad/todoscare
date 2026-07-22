import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base, TenantMixin


class Insurer(Base, AuditMixin):
    """Global entity — an insurer/lab/pharmacy works across many clinics,
    so it isn't tenant-scoped itself (Spec Aseguradora §2)."""

    __tablename__ = "insurers"

    nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    pais: Mapped[str] = mapped_column(String(2), nullable=False)
    tipo: Mapped[str] = mapped_column(String(30), nullable=False)  # seguro | isapre | eps | lab | farmacia
    contacto: Mapped[str | None] = mapped_column(String(255))


class Affiliate(Base, AuditMixin):
    """Padrón del asegurador. patient_id is nullable — an affiliate may not
    be matched to a platform patient yet (Spec Aseguradora §2/§7)."""

    __tablename__ = "affiliates"

    insurer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("insurers.id"), nullable=False, index=True)
    patient_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"))
    documento_identidad: Mapped[str] = mapped_column(String(50), nullable=False)
    plan_cobertura: Mapped[str | None] = mapped_column(String(255))
    vigencia_desde: Mapped[date | None] = mapped_column(Date)
    vigencia_hasta: Mapped[date | None] = mapped_column(Date)


class Agreement(Base, AuditMixin, TenantMixin):
    """A convenio is between one insurer and one clinic — tenant-scoped from
    the clinic side (Spec Empresa/Aseguradora §5.3)."""

    __tablename__ = "agreements"

    insurer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("insurers.id"), nullable=False, index=True)
    vigencia_inicio: Mapped[date | None] = mapped_column(Date)
    vigencia_fin: Mapped[date | None] = mapped_column(Date)


class AgreementProfessional(Base, AuditMixin, TenantMixin):
    """Red: which professionals at the clinic are actually in-network for a
    given agreement (coverage can vary by professional)."""

    __tablename__ = "agreement_professionals"

    agreement_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agreements.id"), nullable=False, index=True)
    professional_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)


class Arancel(Base, AuditMixin, TenantMixin):
    __tablename__ = "aranceles"

    agreement_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agreements.id"), nullable=False, index=True)
    service_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("catalog_items.id"), nullable=False, index=True)
    cobertura_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)  # % covered by insurer
    copago: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, server_default="0")


class Authorization(Base, AuditMixin, TenantMixin):
    __tablename__ = "authorizations"

    agreement_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agreements.id"), nullable=False, index=True)
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True)
    service_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("catalog_items.id"))
    estado: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pendiente")
    # pendiente | aprobada | rechazada | pendiente_info
    motivo_rechazo: Mapped[str | None] = mapped_column(String(500))
    resuelto_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Settlement(Base, AuditMixin, TenantMixin):
    __tablename__ = "settlements"

    agreement_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agreements.id"), nullable=False, index=True)
    periodo: Mapped[str] = mapped_column(String(20), nullable=False)  # e.g. "2026-07"
    monto: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pendiente")  # pendiente | pagado
