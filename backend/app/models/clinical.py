import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base, TenantMixin


class MedicalRecord(Base, AuditMixin, TenantMixin):
    """Prontuario híbrido (JSONB) — visible only to the professional who
    wrote it, within the atención relationship (Spec Médico §2/§3)."""

    __tablename__ = "medical_records"

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True)
    professional_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    appointment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("appointments.id"))
    contenido: Mapped[dict] = mapped_column(JSONB, nullable=False)  # motivo, evolución, diagnóstico — libre por especialidad


class Prescription(Base, AuditMixin, TenantMixin):
    """Immutable once signed — corrections are a new row referencing the one
    being replaced (anula + reemite), never an edit (Spec Médico §5.2)."""

    __tablename__ = "prescriptions"

    record_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("medical_records.id"), nullable=False, index=True)
    items: Mapped[dict] = mapped_column(JSONB, nullable=False)  # [{medicamento, dosis, indicaciones}, ...]
    firmado_por: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    firmado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    estado: Mapped[str] = mapped_column(String(20), nullable=False, server_default="vigente")  # vigente | anulada
    reemplaza_a: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("prescriptions.id"))


class ExamOrder(Base, AuditMixin, TenantMixin):
    __tablename__ = "exam_orders"

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True)
    professional_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    tipo: Mapped[str] = mapped_column(String(30), nullable=False)  # laboratorio | imagenes
    estado: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pendiente")
    # pendiente | en_proceso | listo | cancelada


class ExamResult(Base, AuditMixin, TenantMixin):
    __tablename__ = "exam_results"

    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("exam_orders.id"), nullable=False, index=True)
    archivo_url: Mapped[str | None] = mapped_column(String(1000))
    resultado: Mapped[dict | None] = mapped_column(JSONB)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, server_default="en_proceso")


class Odontogram(Base, AuditMixin, TenantMixin):
    __tablename__ = "odontograms"

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, unique=True)
    piezas: Mapped[dict] = mapped_column(JSONB, nullable=False)  # {"15": {"estado": "pendiente"}, ...}


class Hospitalization(Base, AuditMixin, TenantMixin):
    __tablename__ = "hospitalizations"

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True)
    motivo: Mapped[str] = mapped_column(String(255), nullable=False)
    centro: Mapped[str | None] = mapped_column(String(255))
    ingreso: Mapped[date | None] = mapped_column(Date)
    egreso: Mapped[date | None] = mapped_column(Date)


class EmergencyQr(Base, AuditMixin, TenantMixin):
    """Read-only emergency access (Spec Paciente §5.3). token is what's
    encoded in the QR image; scanning it resolves to this row."""

    __tablename__ = "emergency_qrs"

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, unique=True)
    token: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    resumen: Mapped[dict] = mapped_column(JSONB, nullable=False)  # grupo sanguíneo, alergias
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")


class QrAccessLog(Base, AuditMixin, TenantMixin):
    """Every emergency-QR scan, forever — "cada acceso queda registrado con
    fecha, hora y profesional que consultó" (Spec Paciente §5.3)."""

    __tablename__ = "qr_access_logs"

    qr_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("emergency_qrs.id"), nullable=False, index=True)
    accedido_por: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    profesional_nombre: Mapped[str | None] = mapped_column(String(255))
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
