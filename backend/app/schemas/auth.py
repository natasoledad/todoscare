from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RoleGrantOut(BaseModel):
    role: str
    clinic_id: str | None
    branch_id: str | None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    grants: list[RoleGrantOut]
