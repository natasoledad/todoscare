from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import create_access_token, verify_password
from app.models.identity import Role, RoleAssignment, User
from app.schemas.auth import LoginRequest, LoginResponse, RoleGrantOut

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
