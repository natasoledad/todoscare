import datetime
import uuid

from sqlalchemy import Date, Integer, Numeric, String
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
