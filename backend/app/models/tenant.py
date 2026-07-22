import uuid

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base, TenantMixin


class Clinic(Base, AuditMixin):
    """The tenant root. Everything else hangs off clinic_id — this table itself
    does not (a clinic can't belong to a clinic)."""

    __tablename__ = "clinics"

    razon_social: Mapped[str] = mapped_column(String(255), nullable=False)
    responsable_sanitario: Mapped[str | None] = mapped_column(String(255))
    pais: Mapped[str] = mapped_column(String(2), nullable=False)  # CL, BR, CO, MX
    plan_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("plans.id"))
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")


class Branch(Base, AuditMixin, TenantMixin):
    __tablename__ = "branches"

    nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    direccion: Mapped[str | None] = mapped_column(String(500))
    geo: Mapped[dict | None] = mapped_column(JSONB)  # {"lat": ..., "lng": ...}
    horario: Mapped[dict | None] = mapped_column(JSONB)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
