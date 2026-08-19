import uuid
from dataclasses import dataclass

from app.rbac.matrix import can
from app.rbac.permissions import Action, RoleCode, Resource


@dataclass(frozen=True)
class RoleGrant:
    role: RoleCode
    clinic_id: uuid.UUID | None
    branch_id: uuid.UUID | None
    insurer_id: uuid.UUID | None = None


@dataclass(frozen=True)
class PermissionGrant:
    """Override fino de permiso (48): concede/revoca (resource, action) para un
    usuario en una clínica. `resource`/`action` guardan el valor del enum."""

    clinic_id: uuid.UUID
    resource: str
    action: str
    allow: bool


@dataclass(frozen=True)
class TenantContext:
    """Reconstructed on every request from the JWT's role assignments —
    never trust a clinic_id passed in a request body/query without checking
    it against this context first (see require_clinic_access)."""

    user_id: uuid.UUID
    email: str
    grants: tuple[RoleGrant, ...]
    overrides: tuple[PermissionGrant, ...] = ()

    def is_super_admin(self) -> bool:
        return any(g.role == RoleCode.SUPER_ADMIN for g in self.grants)

    def clinic_ids(self) -> set[uuid.UUID] | None:
        """None means unrestricted access (super_admin crosses every tenant)."""
        if self.is_super_admin():
            return None
        return {g.clinic_id for g in self.grants if g.clinic_id is not None}

    def has_access_to_clinic(self, clinic_id: uuid.UUID) -> bool:
        ids = self.clinic_ids()
        return ids is None or clinic_id in ids

    def insurer_ids(self) -> set[uuid.UUID]:
        """Aseguradoras a las que el usuario está vinculado (Spec Aseguradora
        §3: 'Datos de otras aseguradoras — No'). Vacío para roles no
        aseguradora."""
        return {g.insurer_id for g in self.grants if g.insurer_id is not None}

    def has_access_to_insurer(self, insurer_id: uuid.UUID) -> bool:
        return insurer_id in self.insurer_ids()

    def _override(self, resource: Resource, action: Action, clinic_id: uuid.UUID | None) -> bool | None:
        """Override explícito aplicable a (recurso, acción). Un `deny` (allow=
        False) gana sobre un `allow` si ambos aplican; None si no hay override."""
        aplicables = [
            o for o in self.overrides
            if o.resource == resource.value and o.action == action.value
            and (clinic_id is None or o.clinic_id == clinic_id)
        ]
        if not aplicables:
            return None
        return all(o.allow for o in aplicables)  # cualquier deny bloquea

    def has_permission(self, resource: Resource, action: Action, clinic_id: uuid.UUID | None = None) -> bool:
        # Permisos personalizados (48): el override explícito manda sobre la matriz.
        ov = self._override(resource, action, clinic_id)
        if ov is not None:
            return ov
        for g in self.grants:
            if clinic_id is not None and g.clinic_id is not None and g.clinic_id != clinic_id:
                continue
            if can(g.role, resource, action):
                return True
        return False
