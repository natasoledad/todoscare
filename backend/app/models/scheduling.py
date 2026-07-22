import uuid
from typing import Any

from sqlalchemy import ForeignKey, String, text
from sqlalchemy.dialects.postgresql import JSONB, TSTZRANGE, UUID, ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base, TenantMixin


class AvailabilityBlock(Base, AuditMixin, TenantMixin):
    """A professional's open slots at a branch — the source patients see
    when picking a horario (Spec Empresa Cliente §5.1)."""

    __tablename__ = "availability_blocks"

    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("branches.id"), nullable=False, index=True)
    professional_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    specialty_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("specialties.id"))
    rango: Mapped[Any] = mapped_column(TSTZRANGE, nullable=False)
    reglas: Mapped[dict | None] = mapped_column(JSONB)  # cupos, telemedicina, buffers, excepciones


class Appointment(Base, AuditMixin, TenantMixin):
    """The booking itself. The EXCLUDE constraint is the actual anti
    double-booking guarantee — enforced by Postgres, not application code
    (Kaizen note from the original backend doc: "o banco de dados impede
    double-booking... antes que a API precise processar erros complexos").

    Requires the btree_gist extension (uuid equality inside a GiST index).
    """

    __tablename__ = "appointments"
    __table_args__ = (
        ExcludeConstraint(
            ("professional_id", "="),
            ("slot", "&&"),
            where=text("deleted_at IS NULL"),
            using="gist",
            name="appointments_no_overlap",
        ),
    )

    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("branches.id"), nullable=False, index=True)
    professional_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True)
    service_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("catalog_items.id"))
    slot: Mapped[Any] = mapped_column(TSTZRANGE, nullable=False)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, server_default="confirmada")
    # confirmada | completada | cancelada | no_show
