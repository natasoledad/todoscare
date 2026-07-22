import uuid

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base


class User(Base, AuditMixin):
    """Global identity — not tenant-scoped. A user's tenant reach is entirely
    defined by their RoleAssignment rows (e.g. a médico may work at several
    clinics; a paciente's assignment is scoped to the clinic they registered at)."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    telefono: Mapped[str | None] = mapped_column(String(50))
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")


class Role(Base, AuditMixin):
    """Fixed lookup table — one row per RoleCode (see app/rbac/permissions.py)."""

    __tablename__ = "roles"

    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)


class RoleAssignment(Base, AuditMixin):
    """Contextual RBAC: a role tied to an optional clinic/branch scope.

    clinic_id/branch_id both NULL  -> super_admin (crosses every tenant).
    clinic_id set, branch_id NULL  -> scoped to the whole clinic (all its branches).
    clinic_id + branch_id set      -> scoped to a single branch.
    """

    __tablename__ = "role_assignments"
    __table_args__ = (UniqueConstraint("user_id", "role_id", "clinic_id", "branch_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    role_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("roles.id"), nullable=False, index=True)
    clinic_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=True, index=True)
    branch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("branches.id"), nullable=True, index=True)
