import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base, TenantMixin

NIVELES = ("Bronce", "Plata", "Oro", "Diamante")


class Patient(Base, AuditMixin, TenantMixin):
    """The clinic where the patient registered. Spec Paciente §2.1: only 5
    fields are mandatory at signup; everything else is the optional,
    gamified ficha clínica (§2.2), modeled across patient/clinical/wallet."""

    __tablename__ = "patients"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True)
    rut: Mapped[str] = mapped_column(String(50), nullable=False)
    direccion: Mapped[str] = mapped_column(String(500), nullable=False)
    nivel: Mapped[str] = mapped_column(String(20), nullable=False, server_default="Bronce")
    puntos: Mapped[int] = mapped_column(nullable=False, server_default="0")
    cashback: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, server_default="0")


class Dependent(Base, AuditMixin, TenantMixin):
    """Menores de 18 vinculados a la cuenta del paciente (Spec Paciente §2.2)."""

    __tablename__ = "dependents"

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True)
    nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    fecha_nac: Mapped[date | None] = mapped_column(Date)
    parentesco: Mapped[str | None] = mapped_column(String(50))


class TycVersion(Base, AuditMixin):
    """Platform-wide, per-country T&C — not tenant-scoped (Spec Admin §6.2)."""

    __tablename__ = "tyc_versions"

    pais: Mapped[str] = mapped_column(String(2), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    contenido: Mapped[str] = mapped_column(Text, nullable=False)
    publicado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TycAcceptance(Base, AuditMixin):
    """One row per (patient, version) — re-acceptance is mandatory on every
    new published version (Spec Paciente §9, Spec Admin §6.2)."""

    __tablename__ = "tyc_acceptances"

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True)
    tyc_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tyc_versions.id"), nullable=False, index=True)
    aceptado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
