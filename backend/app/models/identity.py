import uuid

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base, TenantMixin


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
    """Contextual RBAC: a role tied to an optional clinic/branch/insurer scope.

    clinic_id/branch_id both NULL  -> super_admin (crosses every tenant).
    clinic_id set, branch_id NULL  -> scoped to the whole clinic (all its branches).
    clinic_id + branch_id set      -> scoped to a single branch.
    insurer_id set                 -> aseguradora scoped to one insurer entity
                                      (Spec Aseguradora §1: el tercero pagador
                                      opera sobre su propia cartera, no sobre un
                                      tenant clínico).
    """

    __tablename__ = "role_assignments"
    __table_args__ = (UniqueConstraint("user_id", "role_id", "clinic_id", "branch_id", "insurer_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    role_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("roles.id"), nullable=False, index=True)
    clinic_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=True, index=True)
    branch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("branches.id"), nullable=True, index=True)
    insurer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("insurers.id"), nullable=True, index=True)


class PermissionOverride(Base, AuditMixin):
    """Permiso personalizado por usuario y clínica (48.3/48.4, 71.18).

    Capa fina sobre el RBAC fijo por rol: concede (`allow=True`) o revoca
    (`allow=False`) una acción concreta sobre un recurso para un usuario dentro
    de una clínica, sin cambiar su rol. Si no hay override para (recurso,
    acción), rige la matriz del rol —así el comportamiento por defecto no
    cambia—. Un override explícito gana sobre la matriz."""

    __tablename__ = "permission_overrides"
    __table_args__ = (UniqueConstraint("user_id", "clinic_id", "resource", "action", name="uq_permission_override"),)

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    clinic_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=False, index=True)
    resource: Mapped[str] = mapped_column(String(50), nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    allow: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")


class PermissionProfile(Base, AuditMixin, TenantMixin):
    """Perfil de acceso reutilizable (48): un conjunto nombrado de permisos
    (las casillas) sobre un rol base, que el administrador de la clínica define
    una vez y luego asigna a un usuario con un clic —sin revisar acceso por
    acceso cada vez—.

    El `base_role` decide a qué panel entra el usuario (empresa → /empresa,
    medico → /medico, clinic_admin → /admin); el perfil refina qué puede hacer
    dentro de ese panel.

    Semántica de `permisos` (JSONB, lista de {"resource", "action"}):
      - `sin_restriccion = False`: es una allowlist AUTORITATIVA. El usuario con
        este perfil solo puede ejecutar los (recurso, acción) listados, dentro de
        la clínica del perfil. Un override fino por usuario (PR-X) sigue ganando.
      - `sin_restriccion = True`: el perfil no restringe; rige la matriz completa
        del rol base (personas de acceso total: Gerencia, Administrador de Cuenta)."""

    __tablename__ = "permission_profiles"
    __table_args__ = (UniqueConstraint("clinic_id", "nombre", name="uq_permission_profile_nombre"),)

    nombre: Mapped[str] = mapped_column(String(80), nullable=False)
    base_role: Mapped[str] = mapped_column(String(50), nullable=False)  # empresa | medico | clinic_admin
    permisos: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    sin_restriccion: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")


class UserPermissionProfile(Base, AuditMixin):
    """Asignación de un perfil de acceso a un usuario dentro de una clínica.
    A lo sumo un perfil por (usuario, clínica) — asignar reemplaza el anterior."""

    __tablename__ = "user_permission_profiles"
    __table_args__ = (UniqueConstraint("user_id", "clinic_id", name="uq_user_permission_profile"),)

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    clinic_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=False, index=True)
    profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("permission_profiles.id"), nullable=False, index=True)
