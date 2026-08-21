import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text
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
    # Agenda online pública (60): `slug` es la dirección pública sin login
    # (higia.cl/reservar/<slug>). `agenda_online` guarda la configuración de la
    # reserva online en un blob flexible, con defaults en el router:
    #   {habilitada, anticipacion_horas, ventana_dias, mensaje}
    slug: Mapped[str | None] = mapped_column(String(80), unique=True)
    agenda_online: Mapped[dict | None] = mapped_column(JSONB)
    # Logo de la clínica (65.1): imagen (data URL) que se estampa en documentos
    # y presupuestos imprimibles.
    logo: Mapped[str | None] = mapped_column(Text)


class Branch(Base, AuditMixin, TenantMixin):
    __tablename__ = "branches"

    nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    direccion: Mapped[str | None] = mapped_column(String(500))
    geo: Mapped[dict | None] = mapped_column(JSONB)  # {"lat": ..., "lng": ...}
    horario: Mapped[dict | None] = mapped_column(JSONB)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
