import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base, TenantMixin


class IntegrationConfig(Base, AuditMixin, TenantMixin):
    """Per-clinic integration credentials (Spec Admin §8). `credenciales`
    must be encrypted at the application layer before it ever reaches this
    column — the DB only stores ciphertext."""

    __tablename__ = "integration_configs"

    tipo: Mapped[str] = mapped_column(String(30), nullable=False)  # whatsapp | lab | farmacia | pago | aseguradora
    credenciales: Mapped[str | None] = mapped_column(Text)  # ciphertext
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")


class AuditLog(Base, AuditMixin):
    """Global, cross-tenant audit trail (Spec Admin §10). clinic_id is
    nullable because some actions (creating a clinic, publishing T&C) are
    platform-level and have no single tenant owner."""

    __tablename__ = "audit_logs"

    clinic_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("clinics.id"), index=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    accion: Mapped[str] = mapped_column(String(100), nullable=False)
    recurso: Mapped[str] = mapped_column(String(255), nullable=False)
    antes: Mapped[dict | None] = mapped_column(JSONB)
    despues: Mapped[dict | None] = mapped_column(JSONB)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
