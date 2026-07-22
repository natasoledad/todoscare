from collections.abc import Callable

from fastapi import Depends, HTTPException, status

from app.rbac.permissions import Action, Resource
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
