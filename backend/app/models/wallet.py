import uuid

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base, TenantMixin


class WalletAccount(Base, AuditMixin, TenantMixin):
    __tablename__ = "wallet_accounts"

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, unique=True)
    puntos: Mapped[int] = mapped_column(nullable=False, server_default="0")
    cashback: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, server_default="0")


class WalletTransaction(Base, AuditMixin, TenantMixin):
    """Append-only ledger of points/cashback movements. Never updated after
    creation — a reversal is a new offsetting row, mirroring the financial
    ledger's immutability rule (Spec Paciente §2.2/§4)."""

    __tablename__ = "wallet_transactions"

    wallet_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("wallet_accounts.id"), nullable=False, index=True)
    tipo: Mapped[str] = mapped_column(String(50), nullable=False)  # consulta | ficha_completada | compra_farmacia | pago_cashback | ...
    puntos: Mapped[int | None] = mapped_column()
    cashback: Mapped[float | None] = mapped_column(Numeric(12, 2))
    motivo: Mapped[str | None] = mapped_column(String(255))
    ref_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # e.g. appointment_id, order_id
