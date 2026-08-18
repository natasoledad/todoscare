import uuid
from datetime import time
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Integer, String, Time, text
from sqlalchemy.dialects.postgresql import JSONB, TSTZRANGE, UUID, ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base, TenantMixin


class WeeklyScheduleTemplate(Base, AuditMixin, TenantMixin):
    """Plantilla de horario semanal recurrente de un profesional (punto 52).

    Hasta ahora la agenda se armaba bloque por bloque en una fecha suelta. Esta
    plantilla describe el patrón que se repite cada semana —una fila por día y
    turno— y desde ella se MATERIALIZAN los `availability_blocks` para un rango
    de fechas. Modela lo que en Medilink es la grilla Lun–Dom:

      · `dia_semana`               0=lunes … 6=domingo.
      · `hora_inicio` / `hora_fin` turno de atención.
      · `descanso_inicio/fin`      colación: parte el turno en dos bloques (52.4).
      · `modalidad`                presencial | videoconsulta | ambas (52.7).
      · `capacidad`                sillones simultáneos (52.3) — se guarda en el
                                   bloque para futuros features de cupos.
      · `room_id`                  recinto por defecto de ese día/turno (52.5).

    No hay unique por (día): un profesional puede tener varios turnos el mismo
    día (mañana en una sucursal, tarde en otra). "No atiende" (52.6) = sin fila
    para ese día."""

    __tablename__ = "weekly_schedule_templates"

    professional_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("branches.id"), nullable=False, index=True)
    room_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("rooms.id"), index=True)
    dia_semana: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=lunes … 6=domingo
    hora_inicio: Mapped[time] = mapped_column(Time, nullable=False)
    hora_fin: Mapped[time] = mapped_column(Time, nullable=False)
    descanso_inicio: Mapped[time | None] = mapped_column(Time)
    descanso_fin: Mapped[time | None] = mapped_column(Time)
    modalidad: Mapped[str] = mapped_column(String(20), nullable=False, server_default="presencial")
    capacidad: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")


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


class ScheduleException(Base, AuditMixin, TenantMixin):
    """Bloqueo negativo de agenda — cierra la disponibilidad de un profesional
    en un rango de fechas/horas (puntos 51 y 52.9).

    Es la contraparte de los availability_blocks (que SUMAN disponibilidad):
    esto la RESTA. Sirve para vacaciones, permisos, licencias o feriados. La
    reserva y la disponibilidad lo respetan (no se puede agendar dentro de un
    bloqueo) y la generación de bloques desde el horario semanal lo salta.

      · `branch_id` NULL  -> aplica a todas las sucursales del profesional.
      · `motivo`          -> etiqueta visible (Vacaciones, Permiso, Feriado…).
      · `created_by`      -> auditoría "creado por" (AuditMixin), como en la
                            tabla de bloqueos de Medilink."""

    __tablename__ = "schedule_exceptions"

    professional_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    branch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("branches.id"), index=True)
    rango: Mapped[Any] = mapped_column(TSTZRANGE, nullable=False)
    motivo: Mapped[str | None] = mapped_column(String(160))


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


class OnlineBookingRequest(Base, AuditMixin, TenantMixin):
    """Solicitud de hora hecha desde la agenda online pública (punto 60).

    El paciente que reserva sin login puede no existir todavía como Patient
    (que exige un User). Por eso la reserva online NO crea una cita directa:
    crea esta *solicitud* con el horario deseado y los datos de contacto. El
    personal (empresa) la revisa y la CONFIRMA, momento en el que —si el rut
    corresponde a un paciente registrado— se materializa el `Appointment`
    real (con su garantía anti doble-reserva de Postgres) y se enlaza aquí.

    Mientras está `pendiente` la solicitud reserva el hueco de forma optimista
    (la disponibilidad pública descuenta las solicitudes pendientes), pero la
    exclusividad dura la garantiza el EXCLUDE de `appointments` al confirmar.

      · `codigo`         referencia corta que ve el paciente para consultar.
      · `estado`         pendiente | confirmada | rechazada | cancelada.
      · `appointment_id` la cita creada al confirmar (si la hubo).
    """

    __tablename__ = "online_booking_requests"

    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("branches.id"), nullable=False, index=True)
    professional_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    service_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("catalog_items.id"))
    slot: Mapped[Any] = mapped_column(TSTZRANGE, nullable=False)
    codigo: Mapped[str] = mapped_column(String(12), nullable=False, index=True)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pendiente")
    paciente_nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    paciente_rut: Mapped[str | None] = mapped_column(String(50))
    paciente_telefono: Mapped[str | None] = mapped_column(String(40))
    paciente_email: Mapped[str | None] = mapped_column(String(255))
    notas: Mapped[str | None] = mapped_column(String(500))
    appointment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("appointments.id"), index=True)
