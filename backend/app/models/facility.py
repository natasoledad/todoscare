import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base, TenantMixin


class Room(Base, AuditMixin, TenantMixin):
    """Recinto físico de atención: una sala médica o un box dental, numerado.

    Es un recurso finito del centro: dos profesionales no pueden ocupar el mismo
    recinto a la misma hora. Esa exclusión la garantiza Postgres con un EXCLUDE
    USING gist sobre `availability_blocks` (a nivel de agenda) y sobre
    `appointments` (a nivel de reserva), atados por `room_id` — igual que el
    anti doble-reserva por profesional. `numero` es único por tipo dentro de la
    clínica (Sala Médica 1..N, Box Dental 1..N)."""

    __tablename__ = "rooms"
    __table_args__ = (UniqueConstraint("clinic_id", "tipo", "numero", name="uq_room_clinic_tipo_numero"),)

    branch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("branches.id"), index=True)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)  # "Sala Médica 1", "Box Dental 2"
    numero: Mapped[int] = mapped_column(Integer, nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)  # medica | dental
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
