from collections.abc import Callable

from fastapi import Depends, HTTPException, status

from app.rbac.permissions import Action, Resource, RoleCode
from app.tenancy.context import TenantContext
from app.tenancy.deps import get_current_ctx


def require(resource: Resource, action: Action) -> Callable[..., TenantContext]:
    """Usage: `ctx: TenantContext = Depends(require(Resource.OWN_APPOINTMENTS, Action.VER))`.

    Only checks the coarse resource/action grant — ownership/row-level
    checks ("is this patient's own record") still happen in the route body,
    using the returned ctx."""

    def _dependency(ctx: TenantContext = Depends(get_current_ctx)) -> TenantContext:
        if not ctx.has_permission(resource, action):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"No autorizado: {resource.value}.{action.value}")
        return ctx

    return _dependency


def require_any_medico(ctx: TenantContext = Depends(get_current_ctx)) -> TenantContext:
    """Gate for the emergency-QR resolve endpoint (Spec Paciente §5.3):
    "acceso... para un profesional verificado". Identity verification of
    the professional is Spec Paciente's own open question #4 — this is the
    simplest safe interpretation until that's defined: must be logged in
    with a médico role assignment (any clinic), not just any authenticated
    user. Every resolve is still audited regardless (see QrAccessLog)."""
    if not any(g.role == RoleCode.MEDICO for g in ctx.grants):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo un profesional médico puede escanear el QR de emergencia")
    return ctx
