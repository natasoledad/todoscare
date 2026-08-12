import uuid
from typing import Any

from sqlalchemy import ForeignKey, String, text
from sqlalchemy.dialects.postgresql import JSONB, TSTZRANGE, UUID, ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base, TenantMixin


class AvailabilityBlock(Base, AuditMixin, TenantMixin):
    """A professional's open slots at a branch — the source patients see
    when picking a horario (Spec Empresa Cliente §5.1).

    When tied to a `room_id`, the EXCLUDE constraint below stops two
    professionals from being scheduled into the same recinto (sala/box) at
    overlapping times — the room is a finite resource, enforced by Postgres,
    not by app code."""

    __tablename__ = "availability_blocks"
    __table_args__ = (
        ExcludeConstraint(
            ("room_id", "="),
            ("rango", "&&"),
            where=text("deleted_at IS NULL AND room_id IS NOT NULL"),
            using="gist",
            name="availability_blocks_room_no_overlap",
        ),
    )

    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("branches.id"), nullable=False, index=True)
    professional_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    specialty_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("specialties.id"))
    room_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("rooms.id"), index=True)
    rango: Mapped[Any] = mapped_column(TSTZRANGE, nullable=False)
    reglas: Mapped[dict | None] = mapped_column(JSONB)  # cupos, telemedicina, buffers, excepciones


class Appointment(Base, AuditMixin, TenantMixin):
    """The booking itself. The EXCLUDE constraint is the actual anti
    double-booking guarantee — enforced by Postgres, not application code
    (Kaizen note from the original backend doc: "o banco de dados impede
    double-booking... antes que a API precise processar erros complexos").

    The predicate excludes both soft-deleted AND cancelled rows: a
    cancelled appointment must actually free the professional's slot, or
    nobody (including the same patient) could ever rebook it — cancelling
    only sets `estado`, it doesn't soft-delete the row (history stays
    visible in "mis citas"), so the constraint has to know about `estado`
    too, not just `deleted_at`.

    Requires the btree_gist extension (uuid equality inside a GiST index).
    """

    __tablename__ = "appointments"
    __table_args__ = (
        ExcludeConstraint(
            ("professional_id", "="),
            ("slot", "&&"),
            where=text("deleted_at IS NULL AND estado <> 'cancelada'"),
            using="gist",
            name="appointments_no_overlap",
        ),
        # Mismo recinto (sala/box) no puede tener dos citas solapadas — el
        # recinto es un recurso finito, lo garantiza Postgres igual que el
        # anti doble-reserva por profesional.
        ExcludeConstraint(
            ("room_id", "="),
            ("slot", "&&"),
            where=text("deleted_at IS NULL AND estado <> 'cancelada' AND room_id IS NOT NULL"),
            using="gist",
            name="appointments_room_no_overlap",
        ),
    )

    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("branches.id"), nullable=False, index=True)
    professional_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True)
    service_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("catalog_items.id"))
    room_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("rooms.id"), index=True)
    slot: Mapped[Any] = mapped_column(TSTZRANGE, nullable=False)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, server_default="confirmada")
    # confirmada | completada | cancelada | no_show
