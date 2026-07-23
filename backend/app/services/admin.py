"""Admin sub-rol scoping (Spec Administrador §2). The RBAC matrix grants
super_admin / clinic_admin / branch_admin the *same* resource permissions;
what differs is reach:

- super_admin  -> crosses every tenant (clinic_ids() is None).
- clinic_admin -> only their clinic(s).

Platform-global actions (crear un tenant nuevo, planes, T&C por país) are
reserved to super_admin — a clinic_admin operating inside their own clinic
must not be able to mint new clinics or edit platform planes.
"""

import uuid

from fastapi import HTTPException, status

from app.tenancy.context import TenantContext


def admin_scope(ctx: TenantContext) -> set[uuid.UUID] | None:
    """None => todos los tenants (super_admin); si no, el conjunto de
    clinic_ids que el admin puede tocar."""
    return ctx.clinic_ids()


def assert_super_admin(ctx: TenantContext) -> None:
    if not ctx.is_super_admin():
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo el Super-Admin de plataforma puede realizar esta acción")


def assert_clinic_in_scope(ctx: TenantContext, clinic_id: uuid.UUID) -> None:
    if not ctx.has_access_to_clinic(clinic_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Fuera del alcance de tu administración")
