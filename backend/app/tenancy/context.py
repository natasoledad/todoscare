import uuid
from dataclasses import dataclass

from app.rbac.matrix import can
from app.rbac.permissions import Action, RoleCode, Resource


@dataclass(frozen=True)
class RoleGrant:
    role: RoleCode
    clinic_id: uuid.UUID | None
    branch_id: uuid.UUID | None


@dataclass(frozen=True)
class TenantContext:
    """Reconstructed on every request from the JWT's role assignments —
    never trust a clinic_id passed in a request body/query without checking
    it against this context first (see require_clinic_access)."""

    user_id: uuid.UUID
    email: str
    grants: tuple[RoleGrant, ...]

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

    def has_permission(self, resource: Resource, action: Action, clinic_id: uuid.UUID | None = None) -> bool:
        for g in self.grants:
            if clinic_id is not None and g.clinic_id is not None and g.clinic_id != clinic_id:
                continue
            if can(g.role, resource, action):
                return True
        return False
