import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
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


class VitalSigns(Base, AuditMixin, TenantMixin):
    """Signos vitales de una atención (Tanda 3 — vista médica). Todas las
    medidas son opcionales; se registra lo que se toma. created_at = fecha."""

    __tablename__ = "vital_signs"

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True)
    professional_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    appointment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("appointments.id"))
    presion_sistolica: Mapped[int | None] = mapped_column(Integer)   # mmHg
    presion_diastolica: Mapped[int | None] = mapped_column(Integer)  # mmHg
    fc_ppm: Mapped[int | None] = mapped_column(Integer)              # frecuencia cardíaca
    fr_rpm: Mapped[int | None] = mapped_column(Integer)              # frecuencia respiratoria
    spo2: Mapped[int | None] = mapped_column(Integer)                # saturación %
    glicemia: Mapped[int | None] = mapped_column(Integer)           # mg/dl
    eva: Mapped[int | None] = mapped_column(Integer)                # dolor 0-10
    peso_kg: Mapped[float | None] = mapped_column(Numeric(6, 2))
    talla_cm: Mapped[float | None] = mapped_column(Numeric(6, 2))
    temperatura: Mapped[float | None] = mapped_column(Numeric(4, 1))  # °C
    notas: Mapped[str | None] = mapped_column(String(500))


class TreatmentPlan(Base, AuditMixin, TenantMixin):
    """Plan de tratamiento / presupuesto (Tanda 3). El total se calcula de los
    ítems, no se guarda. Odontología y medicina."""

    __tablename__ = "treatment_plans"

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True)
    professional_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    titulo: Mapped[str] = mapped_column(String(255), nullable=False)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, server_default="propuesto")
    # propuesto | aceptado | en_curso | completado | rechazado
    notas: Mapped[str | None] = mapped_column(String(1000))
    # Descuento comercial del plan (69.7): 0.0000–1.0000 sobre el total bruto.
    descuento_pct: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False, server_default="0")


class TreatmentPlanItem(Base, AuditMixin, TenantMixin):
    __tablename__ = "treatment_plan_items"

    plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("treatment_plans.id"), nullable=False, index=True)
    service_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("catalog_items.id"))
    descripcion: Mapped[str] = mapped_column(String(255), nullable=False)
    pieza: Mapped[str | None] = mapped_column(String(10))  # diente (odontología, notación FDI)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    precio_unit: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, server_default="0")
    estado: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pendiente")  # pendiente | realizado


class ClinicalDocument(Base, AuditMixin, TenantMixin):
    """Documentos clínicos (Tanda 5): consentimiento informado, licencia médica,
    interconsulta, etc. Contenido libre + estado (emitido/anulado). Solo el
    profesional tratante, auditado."""

    __tablename__ = "clinical_documents"

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True)
    professional_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    tipo: Mapped[str] = mapped_column(String(30), nullable=False)  # consentimiento | licencia | interconsulta | certificado | otro
    titulo: Mapped[str] = mapped_column(String(255), nullable=False)
    contenido: Mapped[str | None] = mapped_column(String(4000))
    estado: Mapped[str] = mapped_column(String(20), nullable=False, server_default="emitido")  # emitido | anulado
    # Plantillas + firma del paciente (64): el documento puede nacer de una
    # plantilla por bloques y exigir la firma del paciente (consentimientos).
    template_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("document_templates.id"), index=True)
    requiere_firma: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    firmado_paciente: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    firmado_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Firma del profesional (48): instantánea de la firma manuscrita del
    # profesional emisor al momento de crear el documento (data URL PNG). Es una
    # copia inmutable: cambiar la firma del profesional no altera documentos ya
    # emitidos.
    firma_profesional: Mapped[str | None] = mapped_column(Text)


class DocumentTemplate(Base, AuditMixin, TenantMixin):
    """Plantilla de documento por bloques (64.3): consentimientos por
    procedimiento (64.6), certificados (64.7), etc. `bloques` es una lista de
    bloques —párrafos de texto fijo y campos a completar al emitir— con la que
    se arma el contenido del documento. `requiere_firma` marca las plantillas
    de consentimiento que el paciente debe firmar (64.8)."""

    __tablename__ = "document_templates"

    nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    tipo: Mapped[str] = mapped_column(String(30), nullable=False)  # consentimiento | certificado | otro
    bloques: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    requiere_firma: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")


class Periodontogram(Base, AuditMixin, TenantMixin):
    """Periodontograma (Tanda 5). Cada fila es una toma (snapshot) — se guarda
    el histórico. `datos` = { "1.6": {"ps": 3, "sangrado": true}, ... } en
    notación FDI. Odontología."""

    __tablename__ = "periodontograms"

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True)
    professional_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    datos: Mapped[dict] = mapped_column(JSONB, nullable=False)
    notas: Mapped[str | None] = mapped_column(String(500))


class AiFichaSuggestion(Base, AuditMixin, TenantMixin):
    """Sugerencia de la IA clínica al subir un examen (punto 72).

    Cuando el paciente sube un documento y la clínica tiene el conector
    'ia_clinica' activo, la IA lo analiza y propone: (a) `hallazgos` —un parche
    para la ficha clínica del paciente (campos estructurados)— y (b) un
    `proximo_control` sugerido. La sugerencia NO se aplica sola: queda
    `pendiente` hasta que el paciente la confirma (`aplicada`) o la descarta
    (`descartada`), dejando trazabilidad de qué cambió la IA y cuándo."""

    __tablename__ = "ai_ficha_suggestions"

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True)
    exam_order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("exam_orders.id"), index=True)
    resumen: Mapped[str] = mapped_column(String(500), nullable=False)
    hallazgos: Mapped[dict] = mapped_column(JSONB, nullable=False)          # parche para patient.ficha
    proximo_control: Mapped[date | None] = mapped_column(Date)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pendiente")  # pendiente | aplicada | descartada
