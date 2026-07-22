"""Demo seed data for Fase 1 smoke-testing: two clinics (so tenant isolation
is actually testable), one user per role, roles lookup table populated from
RoleCode. Run with: `python -m app.seed` (idempotent — safe to re-run).
"""

import asyncio

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.identity import Role, RoleAssignment, User
from app.models.patient import Patient
from app.models.tenant import Branch, Clinic
from app.rbac.permissions import RoleCode

DEMO_PASSWORD = "Demo1234!"


async def get_or_create_role(db, code: str) -> Role:
    row = (await db.execute(select(Role).where(Role.code == code))).scalar_one_or_none()
    if row:
        return row
    row = Role(code=code)
    db.add(row)
    await db.flush()
    return row


async def get_or_create_user(db, email: str, nombre: str) -> User:
    row = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if row:
        return row
    row = User(email=email, password_hash=hash_password(DEMO_PASSWORD), nombre=nombre)
    db.add(row)
    await db.flush()
    return row


async def get_or_create_clinic(db, razon_social: str, pais: str) -> Clinic:
    row = (await db.execute(select(Clinic).where(Clinic.razon_social == razon_social))).scalar_one_or_none()
    if row:
        return row
    row = Clinic(razon_social=razon_social, pais=pais)
    db.add(row)
    await db.flush()
    return row


async def get_or_create_branch(db, clinic_id, nombre: str) -> Branch:
    row = (
        await db.execute(select(Branch).where(Branch.clinic_id == clinic_id, Branch.nombre == nombre))
    ).scalar_one_or_none()
    if row:
        return row
    row = Branch(clinic_id=clinic_id, nombre=nombre)
    db.add(row)
    await db.flush()
    return row


async def assign_role(db, user_id, role_id, clinic_id=None, branch_id=None) -> None:
    existing = (
        await db.execute(
            select(RoleAssignment).where(
                RoleAssignment.user_id == user_id,
                RoleAssignment.role_id == role_id,
                RoleAssignment.clinic_id == clinic_id,
                RoleAssignment.branch_id == branch_id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        return
    db.add(RoleAssignment(user_id=user_id, role_id=role_id, clinic_id=clinic_id, branch_id=branch_id))


async def main() -> None:
    async with AsyncSessionLocal() as db:
        roles = {code.value: await get_or_create_role(db, code.value) for code in RoleCode}

        clinic_a = await get_or_create_clinic(db, "Clínica Demo A", "MX")
        clinic_b = await get_or_create_clinic(db, "Clínica Demo B", "CL")
        branch_a1 = await get_or_create_branch(db, clinic_a.id, "Sucursal A1")

        super_admin = await get_or_create_user(db, "super@todoscare.dev", "Super Admin")
        admin_a = await get_or_create_user(db, "admin.a@todoscare.dev", "Admin Clínica A")
        admin_b = await get_or_create_user(db, "admin.b@todoscare.dev", "Admin Clínica B")
        medico_a = await get_or_create_user(db, "medico.a@todoscare.dev", "Dra. Nátaly")
        empresa_a = await get_or_create_user(db, "empresa.a@todoscare.dev", "Clínica Demo A (portal)")
        paciente_a = await get_or_create_user(db, "paciente.a@todoscare.dev", "Camila Rodríguez")
        aseguradora_x = await get_or_create_user(db, "aseguradora.x@todoscare.dev", "Aseguradora X")

        await assign_role(db, super_admin.id, roles[RoleCode.SUPER_ADMIN.value].id)
        await assign_role(db, admin_a.id, roles[RoleCode.CLINIC_ADMIN.value].id, clinic_id=clinic_a.id)
        await assign_role(db, admin_b.id, roles[RoleCode.CLINIC_ADMIN.value].id, clinic_id=clinic_b.id)
        await assign_role(db, medico_a.id, roles[RoleCode.MEDICO.value].id, clinic_id=clinic_a.id, branch_id=branch_a1.id)
        await assign_role(db, empresa_a.id, roles[RoleCode.EMPRESA.value].id, clinic_id=clinic_a.id)
        await assign_role(db, paciente_a.id, roles[RoleCode.PACIENTE.value].id, clinic_id=clinic_a.id)
        # Simplification for Fase 1: aseguradora scoped to the one clinic it
        # has a convenio with here. A real aseguradora spans many clinics —
        # revisit this scoping model in Fase 7 (Spec Aseguradora Prestador).
        await assign_role(db, aseguradora_x.id, roles[RoleCode.ASEGURADORA.value].id, clinic_id=clinic_a.id)

        existing_patient = (
            await db.execute(select(Patient).where(Patient.user_id == paciente_a.id))
        ).scalar_one_or_none()
        if not existing_patient:
            db.add(
                Patient(
                    clinic_id=clinic_a.id,
                    user_id=paciente_a.id,
                    rut="18.245.301-K",
                    direccion="Av. Providencia 1234",
                )
            )

        await db.commit()

    print("Seed OK. Demo password for every user:", DEMO_PASSWORD)
    print("  super@todoscare.dev        -> super_admin (global)")
    print("  admin.a@todoscare.dev      -> clinic_admin @ Clínica Demo A")
    print("  admin.b@todoscare.dev      -> clinic_admin @ Clínica Demo B")
    print("  medico.a@todoscare.dev     -> medico @ Clínica Demo A / Sucursal A1")
    print("  empresa.a@todoscare.dev    -> empresa @ Clínica Demo A")
    print("  paciente.a@todoscare.dev   -> paciente @ Clínica Demo A")
    print("  aseguradora.x@todoscare.dev-> aseguradora @ Clínica Demo A")


if __name__ == "__main__":
    asyncio.run(main())
