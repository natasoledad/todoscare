"""Demo seed data for Fase 1 smoke-testing: two clinics (so tenant isolation
is actually testable), one user per role, roles lookup table populated from
RoleCode. Run with: `python -m app.seed` (idempotent — safe to re-run).
"""

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import Range

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.catalog import CatalogItem, Promotion, Specialty
from app.models.clinical import ExamOrder, ExamResult, Hospitalization, MedicalRecord, Odontogram, Prescription
from app.models.finance import Company, CompanyEmployee, LedgerEntry
from app.models.identity import Role, RoleAssignment, User
from app.models.patient import Patient, TycVersion
from app.models.scheduling import Appointment, AvailabilityBlock
from app.models.tenant import Branch, Clinic
from app.models.wallet import WalletAccount
from app.rbac.permissions import RoleCode
from app.services.gamification import FICHA_COMPLETA_BONUS_POINTS, ONBOARDING_BONUS_POINTS, REGISTER_BONUS_POINTS, award

SPECIALTIES = [
    ("Médico general", "🩺"),
    ("Cardiología", "❤️"),
    ("Ginecología", "⚕️"),
    ("Psicología", "🧠"),
    ("Nutrición", "🥗"),
    ("Odontología", "🦷"),
    ("Telemedicina 24/7", "📱"),
]

# (specialty nombre, precio, duracion_min)
SERVICIOS_CLINICA_A = [
    ("Médico general", 450, 30),
    ("Cardiología", 700, 40),
    ("Ginecología", 650, 40),
    ("Psicología", 550, 50),
    ("Nutrición", 500, 30),
    ("Odontología", 600, 45),
    ("Telemedicina 24/7", 350, 20),
]

DEMO_PASSWORD = "Demo1234!"

TYC_COUNTRIES = ("CL", "BR", "CO", "MX")


async def get_or_create_tyc(db, pais: str) -> TycVersion:
    row = (await db.execute(select(TycVersion).where(TycVersion.pais == pais))).scalar_one_or_none()
    if row:
        return row
    row = TycVersion(
        pais=pais,
        version="1.0",
        contenido=(
            "Tratamiento de datos personales y de salud conforme al marco legal vigente. "
            "Cada actualización de estos términos requiere tu nueva aceptación para continuar "
            "usando la plataforma."
        ),
        publicado_en=datetime.now(timezone.utc),
    )
    db.add(row)
    await db.flush()
    return row


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


async def get_or_create_specialty(db, nombre: str, icono: str) -> Specialty:
    row = (await db.execute(select(Specialty).where(Specialty.nombre == nombre))).scalar_one_or_none()
    if row:
        return row
    row = Specialty(nombre=nombre, icono=icono)
    db.add(row)
    await db.flush()
    return row


async def get_or_create_catalog_item(db, clinic_id, specialty_id, nombre: str, precio, duracion_min: int) -> CatalogItem:
    row = (
        await db.execute(
            select(CatalogItem).where(CatalogItem.clinic_id == clinic_id, CatalogItem.nombre == nombre, CatalogItem.tipo == "servicio")
        )
    ).scalar_one_or_none()
    if row:
        return row
    row = CatalogItem(clinic_id=clinic_id, specialty_id=specialty_id, tipo="servicio", nombre=nombre, precio=precio, duracion_min=duracion_min)
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
        for pais in TYC_COUNTRIES:
            await get_or_create_tyc(db, pais)

        clinic_a = await get_or_create_clinic(db, "Clínica Demo A", "MX")
        clinic_b = await get_or_create_clinic(db, "Clínica Demo B", "CL")
        branch_a1 = await get_or_create_branch(db, clinic_a.id, "Sucursal A1")

        super_admin = await get_or_create_user(db, "super@todoscare.dev", "Super Admin")
        admin_a = await get_or_create_user(db, "admin.a@todoscare.dev", "Admin Clínica A")
        admin_b = await get_or_create_user(db, "admin.b@todoscare.dev", "Admin Clínica B")
        medico_a = await get_or_create_user(db, "medico.a@todoscare.dev", "Dra. Nátaly")
        # A second médico in the same clinic with NO appointments — exists so
        # the "solo pacientes que atiende" isolation (Spec Médico §3) is
        # actually testable: he must be denied Camila's ficha.
        medico_b = await get_or_create_user(db, "medico.b@todoscare.dev", "Dr. Fuentes")
        empresa_a = await get_or_create_user(db, "empresa.a@todoscare.dev", "Clínica Demo A (portal)")
        paciente_a = await get_or_create_user(db, "paciente.a@todoscare.dev", "Camila Rodríguez")
        aseguradora_x = await get_or_create_user(db, "aseguradora.x@todoscare.dev", "Aseguradora X")

        await assign_role(db, super_admin.id, roles[RoleCode.SUPER_ADMIN.value].id)
        await assign_role(db, admin_a.id, roles[RoleCode.CLINIC_ADMIN.value].id, clinic_id=clinic_a.id)
        await assign_role(db, admin_b.id, roles[RoleCode.CLINIC_ADMIN.value].id, clinic_id=clinic_b.id)
        await assign_role(db, medico_a.id, roles[RoleCode.MEDICO.value].id, clinic_id=clinic_a.id, branch_id=branch_a1.id)
        await assign_role(db, medico_b.id, roles[RoleCode.MEDICO.value].id, clinic_id=clinic_a.id, branch_id=branch_a1.id)
        await assign_role(db, empresa_a.id, roles[RoleCode.EMPRESA.value].id, clinic_id=clinic_a.id)
        await assign_role(db, paciente_a.id, roles[RoleCode.PACIENTE.value].id, clinic_id=clinic_a.id)
        # Simplification for Fase 1: aseguradora scoped to the one clinic it
        # has a convenio with here. A real aseguradora spans many clinics —
        # revisit this scoping model in Fase 7 (Spec Aseguradora Prestador).
        await assign_role(db, aseguradora_x.id, roles[RoleCode.ASEGURADORA.value].id, clinic_id=clinic_a.id)

        specialties = {}
        for nombre, icono in SPECIALTIES:
            specialties[nombre] = await get_or_create_specialty(db, nombre, icono)
        catalog = {}
        for nombre, precio, duracion_min in SERVICIOS_CLINICA_A:
            catalog[nombre] = await get_or_create_catalog_item(db, clinic_a.id, specialties[nombre].id, nombre, precio, duracion_min)

        # medico_a is available all day today, at branch_a1, for any
        # specialty (specialty_id=None) — a real deployment would seed one
        # block per specialty/professional; kept to one block for Fase 2.
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        existing_block = (
            await db.execute(select(AvailabilityBlock).where(AvailabilityBlock.professional_id == medico_a.id))
        ).scalar_one_or_none()
        if not existing_block:
            db.add(
                AvailabilityBlock(
                    clinic_id=clinic_a.id,
                    branch_id=branch_a1.id,
                    professional_id=medico_a.id,
                    specialty_id=None,
                    rango=Range(today + timedelta(hours=9), today + timedelta(hours=18)),
                )
            )

        existing_patient = (
            await db.execute(select(Patient).where(Patient.user_id == paciente_a.id))
        ).scalar_one_or_none()
        if not existing_patient:
            # Camila represents an already-established demo user (not a
            # fresh signup) — onboarding_completado=True so logging in as
            # her lands straight in the app, and her ficha is filled in to
            # match the seeded exams/odontograma/hospitalizaciones below.
            patient = Patient(
                clinic_id=clinic_a.id,
                user_id=paciente_a.id,
                rut="18.245.301-K",
                direccion="Av. Providencia 1234",
                onboarding_completado=True,
                ficha_completa_bonus_otorgado=True,
                ficha={
                    "fecha_nacimiento": "1990-05-14",
                    "sexo": "Femenino",
                    "grupo_sanguineo": "O+",
                    "alergias": "Penicilina",
                    "medicacion_actual": "Losartán 50mg diario",
                    "antecedentes": "Hipertensión (2022)",
                    "contacto_emergencia": "Pedro Rodríguez +52 55 9999 0000",
                    "seguro": "Sí",
                },
            )
            db.add(patient)
            await db.flush()
            wallet = WalletAccount(clinic_id=clinic_a.id, patient_id=patient.id)
            db.add(wallet)
            await db.flush()
            await award(db, wallet=wallet, patient=patient, tipo="registro", puntos=REGISTER_BONUS_POINTS, motivo="Bono de bienvenida (seed)")
            await award(db, wallet=wallet, patient=patient, tipo="onboarding_completado", puntos=ONBOARDING_BONUS_POINTS, motivo="Onboarding completado (seed)")
            await award(db, wallet=wallet, patient=patient, tipo="ficha_completada", puntos=FICHA_COMPLETA_BONUS_POINTS, motivo="Ficha clínica completada al 100%")
            for tipo, motivo, puntos, cashback in [
                ("consulta", "Consulta general", 45, 22),
                ("compra_farmacia", "Compra en farmacia", 18, 9),
                ("pago_cashback", "Pago con cashback", None, -35),
                ("consulta", "Limpieza dental", 60, 30),
            ]:
                await award(db, wallet=wallet, patient=patient, tipo=tipo, puntos=puntos, cashback=cashback, motivo=motivo)

            now = datetime.now(timezone.utc)
            for nombre, dias_atras, estado in [
                ("Hemograma completo", 60, "listo"),
                ("Perfil lipídico", 60, "listo"),
                ("Radiografía panorámica (dental)", 45, "en_proceso"),
            ]:
                order = ExamOrder(clinic_id=clinic_a.id, patient_id=patient.id, professional_id=medico_a.id, tipo="laboratorio", estado=estado)
                db.add(order)
                await db.flush()
                order.created_at = now - timedelta(days=dias_atras)
                db.add(ExamResult(clinic_id=clinic_a.id, order_id=order.id, resultado={"nombre": nombre}, estado=estado))

            db.add(
                Odontogram(
                    clinic_id=clinic_a.id,
                    patient_id=patient.id,
                    piezas={str(i): {"estado": "pendiente" if i in (4, 11) else "sana"} for i in range(16)},
                )
            )

            db.add(Hospitalization(clinic_id=clinic_a.id, patient_id=patient.id, motivo="Apendicectomía", centro="Hospital Ángeles", ingreso=datetime(2019, 3, 12).date(), egreso=datetime(2019, 3, 15).date()))
            db.add(Hospitalization(clinic_id=clinic_a.id, patient_id=patient.id, motivo="Observación", centro="Clínica Roma Norte", ingreso=datetime(2023, 8, 4).date(), egreso=datetime(2023, 8, 5).date()))

            record = MedicalRecord(clinic_id=clinic_a.id, patient_id=patient.id, professional_id=medico_a.id, contenido={"motivo": "Control"})
            db.add(record)
            await db.flush()
            db.add(
                Prescription(
                    clinic_id=clinic_a.id,
                    record_id=record.id,
                    firmado_por=medico_a.id,
                    firmado_en=now,
                    estado="vigente",
                    items=[
                        {"medicamento": "Losartán 50mg", "cantidad": "30 comprimidos", "indicaciones": "1 vez al día", "precio": 180},
                        {"medicamento": "Omeprazol 20mg", "cantidad": "14 cápsulas", "indicaciones": "1 vez al día en ayunas", "precio": 95},
                    ],
                )
            )

            # A confirmed appointment today so Dra. Nátaly's agenda isn't
            # empty and the médico flow has a real cita to attend. This is
            # what establishes the care relationship the ficha access checks
            # against (Spec Médico §3).
            servicio_general = catalog["Médico general"]
            db.add(
                Appointment(
                    clinic_id=clinic_a.id,
                    branch_id=branch_a1.id,
                    professional_id=medico_a.id,
                    patient_id=patient.id,
                    service_id=servicio_general.id,
                    slot=Range(today + timedelta(hours=10), today + timedelta(hours=10, minutes=30)),
                    estado="confirmada",
                )
            )

        # ── Empresa (Fase 4) demo data for Clínica Demo A ──
        # Promotions the empresa portal manages and the paciente app shows.
        existing_promo = (await db.execute(select(Promotion).where(Promotion.clinic_id == clinic_a.id))).scalars().first()
        if not existing_promo:
            db.add(Promotion(clinic_id=clinic_a.id, nombre="Chequeo preventivo -20%", descuento="-20%", segmento="Todos", estado="Activa"))
            db.add(Promotion(clinic_id=clinic_a.id, nombre="Odontología familiar 2x1", descuento="2x1", segmento="Odontología", estado="Activa"))
            db.add(Promotion(clinic_id=clinic_a.id, nombre="Primera telemedicina gratis", descuento="100%", segmento="Nuevos", estado="Borrador"))

        # A couple of ingresos so the empresa KPIs (ingresos del mes) aren't flat.
        existing_ledger = (await db.execute(select(LedgerEntry).where(LedgerEntry.clinic_id == clinic_a.id))).scalars().first()
        if not existing_ledger:
            for monto in (450, 600, 320):
                db.add(LedgerEntry(clinic_id=clinic_a.id, tipo="ingreso", monto=monto, ref="seed"))

        # The clinic also operates as a B2B contratante (empresa portal §Funcionarios).
        existing_company = (await db.execute(select(Company).where(Company.clinic_id == clinic_a.id))).scalars().first()
        if not existing_company:
            db.add(Company(clinic_id=clinic_a.id, razon_social="Corporativo Demo S.A."))

        await db.commit()

    print("Seed OK. Demo password for every user:", DEMO_PASSWORD)
    print("  super@todoscare.dev        -> super_admin (global)")
    print("  admin.a@todoscare.dev      -> clinic_admin @ Clínica Demo A")
    print("  admin.b@todoscare.dev      -> clinic_admin @ Clínica Demo B")
    print("  medico.a@todoscare.dev     -> medico @ Clínica Demo A / Sucursal A1 (atiende a Camila)")
    print("  medico.b@todoscare.dev     -> medico @ Clínica Demo A / Sucursal A1 (sin citas)")
    print("  empresa.a@todoscare.dev    -> empresa @ Clínica Demo A")
    print("  paciente.a@todoscare.dev   -> paciente @ Clínica Demo A")
    print("  aseguradora.x@todoscare.dev-> aseguradora @ Clínica Demo A")


if __name__ == "__main__":
    asyncio.run(main())
