import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column


class Base(DeclarativeBase):
    pass


class AuditMixin:
    """created_at/updated_at + created_by + soft-delete (deleted_at).

    Hard deletes are intercepted globally (see app/core/audit.py) and turned
    into a deleted_at timestamp so clinical/financial history is never lost.
    """

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    @declared_attr
    def created_by(cls) -> Mapped[uuid.UUID | None]:
        return mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TenantMixin:
    """clinic_id present on every tenant-scoped table, NOT NULL, indexed.

    Never query a TenantMixin table without filtering by clinic_id — see
    app/tenancy/deps.py for the enforced pattern.
    """

    @declared_attr
    def clinic_id(cls) -> Mapped[uuid.UUID]:
        return mapped_column(UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=False, index=True)
