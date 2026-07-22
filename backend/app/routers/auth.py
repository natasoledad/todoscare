from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import create_access_token, verify_password
from app.models.identity import Role, RoleAssignment, User
from app.schemas.auth import LoginRequest, LoginResponse, MeOut, RoleGrantOut
from app.tenancy.context import TenantContext
from app.tenancy.deps import get_current_ctx

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> LoginResponse:
    result = await db.execute(select(User).where(User.email == payload.email, User.deleted_at.is_(None)))
    user = result.scalar_one_or_none()
    if user is None or not user.activo or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Correo o contraseña incorrectos")

    rows = await db.execute(
        select(RoleAssignment, Role.code)
        .join(Role, Role.id == RoleAssignment.role_id)
        .where(RoleAssignment.user_id == user.id, RoleAssignment.deleted_at.is_(None))
    )
    grants = [
        RoleGrantOut(role=role_code, clinic_id=str(ra.clinic_id) if ra.clinic_id else None, branch_id=str(ra.branch_id) if ra.branch_id else None)
        for ra, role_code in rows.all()
    ]
    if not grants:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "El usuario no tiene roles asignados")

    token = create_access_token({"sub": str(user.id)})
    return LoginResponse(access_token=token, grants=grants)


@router.get("/me", response_model=MeOut)
async def me(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(get_current_ctx),
) -> MeOut:
    """Identidad + roles del usuario autenticado, sin datos específicos de
    ningún rol — el frontend lo usa para enrutar por rol (paciente -> /app,
    médico -> /medico) antes de pedir el perfil concreto."""
    user = await db.get(User, ctx.user_id)
    roles = sorted({g.role.value for g in ctx.grants})
    grants = [
        RoleGrantOut(role=g.role.value, clinic_id=str(g.clinic_id) if g.clinic_id else None, branch_id=str(g.branch_id) if g.branch_id else None)
        for g in ctx.grants
    ]
    return MeOut(user_id=str(user.id), nombre=user.nombre, email=user.email, roles=roles, grants=grants)
