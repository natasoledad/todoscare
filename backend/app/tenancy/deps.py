import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.identity import PermissionOverride, Role, RoleAssignment, User
from app.rbac.permissions import RoleCode
from app.tenancy.context import PermissionGrant, RoleGrant, TenantContext

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_ctx(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> TenantContext:
    try:
        payload = decode_access_token(token)
        user_id = uuid.UUID(payload["sub"])
    except (ValueError, KeyError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciales inválidas") from exc

    user = await db.get(User, user_id)
    if user is None or not user.activo or user.deleted_at is not None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario inactivo o inexistente")

    rows = await db.execute(
        select(RoleAssignment, Role.code)
        .join(Role, Role.id == RoleAssignment.role_id)
        .where(RoleAssignment.user_id == user_id, RoleAssignment.deleted_at.is_(None))
    )
    grants = tuple(
        RoleGrant(role=RoleCode(role_code), clinic_id=ra.clinic_id, branch_id=ra.branch_id, insurer_id=ra.insurer_id)
        for ra, role_code in rows.all()
    )
    if not grants:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "El usuario no tiene roles asignados")

    # Permisos personalizados (48): overrides finos del usuario.
    ov_rows = (
        await db.execute(
            select(PermissionOverride).where(
                PermissionOverride.user_id == user_id, PermissionOverride.deleted_at.is_(None)
            )
        )
    ).scalars().all()
    overrides = tuple(
        PermissionGrant(clinic_id=o.clinic_id, resource=o.resource, action=o.action, allow=o.allow)
        for o in ov_rows
    )

    return TenantContext(user_id=user.id, email=user.email, grants=grants, overrides=overrides)


def require_clinic_access(ctx: TenantContext, clinic_id: uuid.UUID) -> None:
    """Call before running any tenant-scoped query with a clinic_id that
    came from the request rather than derived purely from the token."""
    if not ctx.has_access_to_clinic(clinic_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Sin acceso a esta clínica")
