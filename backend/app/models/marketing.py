import datetime
import uuid

from sqlalchemy import Date, DateTime, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base, TenantMixin


class MarketingCampaign(Base, AuditMixin, TenantMixin):
    """Gestión de marketing digital del CRM: campañas por canal con
    presupuesto, gasto, leads y conversiones. El gasto se asienta además como
    LedgerEntry tipo='gasto_marketing' (ref 'campana:<id>'), de modo que el
    CAC/ROAS del CRM se calculan sobre el ledger inmutable — una sola fuente
    de verdad, igual que el resto de la plataforma."""

    __tablename__ = "marketing_campaigns"

    nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    canal: Mapped[str] = mapped_column(String(30), nullable=False)  # google_ads | meta_ads | instagram | email | whatsapp | seo | referidos
    estado: Mapped[str] = mapped_column(String(20), nullable=False, server_default="activa")  # activa | pausada | finalizada
    presupuesto: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, server_default="0")
    gasto: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, server_default="0")  # suma cacheada de los asientos de la campaña
    leads: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    conversiones: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")  # leads que se volvieron pacientes
    fecha_inicio: Mapped[datetime.date | None] = mapped_column(Date)
    fecha_fin: Mapped[datetime.date | None] = mapped_column(Date)


class CrmTask(Base, AuditMixin, TenantMixin):
    """Tarea de gestión del CRM (seguimiento de pacientes): llamar, recordar,
    cobrar, etc. (Tanda 6)."""

    __tablename__ = "crm_tasks"

    titulo: Mapped[str] = mapped_column(String(255), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(String(1000))
    patient_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    estado: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pendiente")  # pendiente | hecha
    vencimiento: Mapped[datetime.date | None] = mapped_column(Date)


class SatisfactionSurvey(Base, AuditMixin, TenantMixin):
    """Encuesta de satisfacción (Tanda 6). Se 'envía' (invitación) y luego el
    paciente responde con un puntaje 0-10 (NPS) y comentario. El envío real por
    correo/WhatsApp queda para la integración (Resend/WhatsApp); aquí se modela
    el ciclo invitación → respuesta y el resumen (promedio, NPS, tasa)."""

    __tablename__ = "satisfaction_surveys"

    patient_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    paciente_nombre: Mapped[str | None] = mapped_column(String(255))
    appointment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    estado: Mapped[str] = mapped_column(String(20), nullable=False, server_default="enviada")  # enviada | respondida
    score: Mapped[int | None] = mapped_column(Integer)  # 0-10
    comentario: Mapped[str | None] = mapped_column(String(1000))
    respondida_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))


class MessageTemplate(Base, AuditMixin, TenantMixin):
    """Plantilla de mensaje (email/WhatsApp) reutilizable en campañas y
    comunicaciones (Tanda 6)."""

    __tablename__ = "message_templates"

    nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    canal: Mapped[str] = mapped_column(String(20), nullable=False, server_default="email")  # email | whatsapp
    asunto: Mapped[str | None] = mapped_column(String(255))
    cuerpo: Mapped[str] = mapped_column(String(4000), nullable=False)
