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
from app.models.finance import Company, CompanyEmployee, LedgerEntry, PaymentSplit
from app.models.insurance import Affiliate, Agreement, Arancel, Authorization, Insurer
from app.models.integrations import IntegrationConfig
from app.models.marketing import MarketingCampaign
from app.models.identity import PermissionProfile, Role, RoleAssignment, User
from app.models.patient import Patient, TycAcceptance, TycVersion
from app.models.scheduling import Appointment, AvailabilityBlock
from app.models.tax import TaxEmitter, TaxFolioRange
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


async def seed_tax_emitter(db, clinic_id, pais: str, *, tax_id, razon_social, giro, direccion, config, folios) -> None:
    """Emisor fiscal + folios/CAF (Chile) o serie (Brasil) + conector 'tributario'
    habilitado, para poder emitir documentos end-to-end en el smoke test. `folios`
    es una lista de (tipo_documento, serie, desde, hasta, caf_ref)."""
    em = (await db.execute(select(TaxEmitter).where(TaxEmitter.clinic_id == clinic_id))).scalar_one_or_none()
    if em is None:
        em = TaxEmitter(
            clinic_id=clinic_id, pais=pais, tax_id=tax_id, razon_social=razon_social,
            giro=giro, direccion=direccion, config=config,
        )
        db.add(em)
        await db.flush()
        for tipo_documento, serie, desde, hasta, caf_ref in folios:
            db.add(
                TaxFolioRange(
                    clinic_id=clinic_id, emitter_id=em.id, tipo_documento=tipo_documento, serie=serie,
                    desde=desde, hasta=hasta, siguiente=desde, caf_ref=caf_ref,
                )
            )
    existing = (
        await db.execute(
            select(IntegrationConfig).where(IntegrationConfig.clinic_id == clinic_id, IntegrationConfig.tipo == "tributario")
        )
    ).scalar_one_or_none()
    if existing is None:
        db.add(IntegrationConfig(clinic_id=clinic_id, tipo="tributario", activo=True, credenciales=None))


# ── Perfiles de acceso reutilizables (48) ──────────────────────────────────
# Los 12 perfiles que espera una clínica que contrata el software. `base_role`
# decide el panel (empresa → /empresa, medico → /medico, clinic_admin → /admin);
# los permisos son la allowlist autoritativa dentro de ese panel. Gerencia y
# Administrador de Cuenta usan `sin_restriccion` (acceso total al panel admin).
PERFILES_BASE: list[dict] = [
    {"nombre": "Recepción", "base_role": "empresa", "sin_restriccion": False, "permisos": [
        ("clinic_agendas", ["ver", "crear", "editar", "eliminar"]),
        ("catalogo_precios", ["ver"]),
        ("cajas", ["ver", "crear", "editar"]),
        ("info_empresa", ["ver"]),
    ]},
    {"nombre": "TENS", "base_role": "medico", "sin_restriccion": False, "permisos": [
        ("own_agenda", ["ver"]),
        ("prontuario_atendidos", ["ver", "crear", "editar"]),
        ("ordenes_examen", ["ver"]),
    ]},
    {"nombre": "TONS", "base_role": "medico", "sin_restriccion": False, "permisos": [
        ("own_agenda", ["ver"]),
        ("prontuario_atendidos", ["ver", "crear", "editar"]),
        ("ordenes_examen", ["ver", "crear"]),
    ]},
    {"nombre": "Médico", "base_role": "medico", "sin_restriccion": False, "permisos": [
        ("own_agenda", ["ver", "crear", "editar", "eliminar"]),
        ("prontuario_atendidos", ["ver", "crear", "editar"]),
        ("prescripciones", ["ver", "crear", "editar"]),
        ("ordenes_examen", ["ver", "crear", "editar", "eliminar"]),
        ("liquidacion_propia", ["ver"]),
    ]},
    {"nombre": "Dentista", "base_role": "medico", "sin_restriccion": False, "permisos": [
        ("own_agenda", ["ver", "crear", "editar", "eliminar"]),
        ("prontuario_atendidos", ["ver", "crear", "editar"]),
        ("prescripciones", ["ver", "crear", "editar"]),
        ("ordenes_examen", ["ver", "crear", "editar", "eliminar"]),
        ("liquidacion_propia", ["ver"]),
    ]},
    {"nombre": "Líder", "base_role": "empresa", "sin_restriccion": False, "permisos": [
        ("clinic_agendas", ["ver", "crear", "editar", "eliminar"]),
        ("catalogo_precios", ["ver", "crear", "editar"]),
        ("promociones", ["ver", "crear", "editar"]),
        ("cajas", ["ver", "crear", "editar"]),
        ("inventario", ["ver", "crear", "editar"]),
        ("laboratorios", ["ver", "crear", "editar"]),
        ("liquidacion_profesionales", ["ver", "editar"]),
        ("crm_kpis_clinica", ["ver"]),
        ("crm_campanas", ["ver", "crear", "editar", "eliminar"]),
        ("info_empresa", ["ver", "editar"]),
        ("funcionarios_b2b", ["ver", "crear", "editar"]),
    ]},
    {"nombre": "Coordinación", "base_role": "empresa", "sin_restriccion": False, "permisos": [
        ("clinic_agendas", ["ver", "crear", "editar", "eliminar"]),
        ("catalogo_precios", ["ver", "editar"]),
        ("promociones", ["ver", "crear", "editar"]),
        ("crm_kpis_clinica", ["ver"]),
        ("crm_campanas", ["ver", "crear", "editar"]),
        ("funcionarios_b2b", ["ver", "crear", "editar"]),
        ("info_empresa", ["ver"]),
    ]},
    {"nombre": "Gerencia", "base_role": "clinic_admin", "sin_restriccion": True, "permisos": []},
    {"nombre": "Reportería", "base_role": "empresa", "sin_restriccion": False, "permisos": [
        ("clinic_agendas", ["ver"]),
        ("catalogo_precios", ["ver"]),
        ("cajas", ["ver"]),
        ("inventario", ["ver"]),
        ("laboratorios", ["ver"]),
        ("liquidacion_profesionales", ["ver"]),
        ("crm_kpis_clinica", ["ver"]),
    ]},
    {"nombre": "CallCenter", "base_role": "empresa", "sin_restriccion": False, "permisos": [
        ("clinic_agendas", ["ver", "crear", "editar"]),
        ("catalogo_precios", ["ver"]),
        ("info_empresa", ["ver"]),
    ]},
    {"nombre": "Administrativo", "base_role": "empresa", "sin_restriccion": False, "permisos": [
        ("cajas", ["ver", "crear", "editar"]),
        ("tributario", ["ver", "crear", "editar"]),
        ("liquidacion_profesionales", ["ver", "editar"]),
        ("inventario", ["ver", "crear", "editar", "eliminar"]),
        ("laboratorios", ["ver", "crear", "editar", "eliminar"]),
        ("catalogo_precios", ["ver", "editar"]),
    ]},
    {"nombre": "Administrador de Cuenta", "base_role": "clinic_admin", "sin_restriccion": True, "permisos": []},
]


async def seed_permission_profiles(db, clinic_id) -> None:
    """Crea (idempotente) los 12 perfiles de acceso base para una clínica. Solo
    define los perfiles; no los asigna a ningún usuario, así que no altera los
    permisos efectivos de los usuarios ya sembrados."""
    for spec in PERFILES_BASE:
        existe = (
            await db.execute(
                select(PermissionProfile).where(
                    PermissionProfile.clinic_id == clinic_id, PermissionProfile.nombre == spec["nombre"]
                )
            )
        ).scalar_one_or_none()
        if existe is not None:
            continue
        permisos = [{"resource": r, "action": a} for r, acts in spec["permisos"] for a in acts]
        db.add(PermissionProfile(
            clinic_id=clinic_id, nombre=spec["nombre"], base_role=spec["base_role"],
            permisos=permisos, sin_restriccion=spec["sin_restriccion"],
        ))
    await db.flush()


# ── Catálogo CIE-10 (71.20) ────────────────────────────────────────────────
# Subconjunto curado de códigos frecuentes (odontológicos K00–K14 + atención
# general). El catálogo es ampliable desde la BD; esto cubre el uso diario.
_DENTAL = "K00–K14 · Cavidad bucal y maxilares"
_RESP = "J00–J99 · Sistema respiratorio"
_CRONICO = "E/I · Crónicas y metabólicas"
_DIG = "K20–K93 · Sistema digestivo"
_MUSC = "M00–M99 · Sistema osteomuscular"
_GEN = "R/Z · Síntomas y exámenes"
_INFEC = "A/B · Infecciosas"
_PIEL = "L00–L99 · Piel"
_SM = "F00–F99 · Salud mental"
_GU = "N00–N99 · Genitourinario"

CIE10_SEED: list[tuple[str, str, str]] = [
    ("K00.6", "Alteraciones en la erupción dentaria", _DENTAL),
    ("K01.1", "Diente impactado", _DENTAL),
    ("K02.1", "Caries de la dentina", _DENTAL),
    ("K02.5", "Caries dental con exposición pulpar", _DENTAL),
    ("K02.9", "Caries dental, no especificada", _DENTAL),
    ("K03.1", "Abrasión de los dientes", _DENTAL),
    ("K03.6", "Depósitos (sarro/cálculo) en los dientes", _DENTAL),
    ("K04.0", "Pulpitis", _DENTAL),
    ("K04.1", "Necrosis de la pulpa", _DENTAL),
    ("K04.5", "Periodontitis apical crónica", _DENTAL),
    ("K04.7", "Absceso periapical sin fístula", _DENTAL),
    ("K05.0", "Gingivitis aguda", _DENTAL),
    ("K05.1", "Gingivitis crónica", _DENTAL),
    ("K05.3", "Periodontitis crónica", _DENTAL),
    ("K06.0", "Retracción gingival", _DENTAL),
    ("K07.3", "Anomalías de la posición de los dientes (maloclusión)", _DENTAL),
    ("K08.1", "Pérdida de dientes por accidente, extracción o enf. periodontal", _DENTAL),
    ("K08.9", "Trastorno de los dientes y sus estructuras, no especificado", _DENTAL),
    ("K12.0", "Aftas bucales recidivantes", _DENTAL),
    ("K13.0", "Enfermedades de los labios", _DENTAL),
    ("J00", "Rinofaringitis aguda (resfriado común)", _RESP),
    ("J02.9", "Faringitis aguda, no especificada", _RESP),
    ("J03.9", "Amigdalitis aguda, no especificada", _RESP),
    ("J06.9", "Infección aguda de las vías respiratorias superiores", _RESP),
    ("J45.9", "Asma, no especificada", _RESP),
    ("I10", "Hipertensión esencial (primaria)", _CRONICO),
    ("E11.9", "Diabetes mellitus tipo 2 sin complicaciones", _CRONICO),
    ("E78.5", "Hiperlipidemia, no especificada", _CRONICO),
    ("E66.9", "Obesidad, no especificada", _CRONICO),
    ("K21.9", "Enfermedad por reflujo gastroesofágico sin esofagitis", _DIG),
    ("K29.7", "Gastritis, no especificada", _DIG),
    ("K59.0", "Estreñimiento", _DIG),
    ("M54.5", "Lumbago no especificado", _MUSC),
    ("M54.2", "Cervicalgia", _MUSC),
    ("M79.1", "Mialgia", _MUSC),
    ("R51", "Cefalea", _GEN),
    ("R50.9", "Fiebre, no especificada", _GEN),
    ("R10.4", "Dolor abdominal, otro y no especificado", _GEN),
    ("N39.0", "Infección de vías urinarias, sitio no especificado", _GU),
    ("A09", "Diarrea y gastroenteritis de presunto origen infeccioso", _INFEC),
    ("B34.9", "Infección viral, no especificada", _INFEC),
    ("L20.9", "Dermatitis atópica, no especificada", _PIEL),
    ("L23.9", "Dermatitis alérgica de contacto, de causa no especificada", _PIEL),
    ("F41.1", "Trastorno de ansiedad generalizada", _SM),
    ("F32.9", "Episodio depresivo, no especificado", _SM),
    ("Z00.0", "Examen médico general", _GEN),
    ("Z01.2", "Examen odontológico", _GEN),
]


async def seed_cie10(db) -> int:
    """Carga (idempotente) el catálogo CIE-10 base. Devuelve cuántos códigos
    nuevos insertó. Global (no tenant): existe una sola vez en la BD."""
    from app.models.clinical import Cie10Code

    nuevos = 0
    for codigo, descripcion, categoria in CIE10_SEED:
        existe = (await db.execute(select(Cie10Code).where(Cie10Code.codigo == codigo))).scalar_one_or_none()
        if existe is not None:
            continue
        db.add(Cie10Code(codigo=codigo, descripcion=descripcion, categoria=categoria))
        nuevos += 1
    await db.flush()
    return nuevos


async def assign_role(db, user_id, role_id, clinic_id=None, branch_id=None, insurer_id=None) -> None:
    existing = (
        await db.execute(
            select(RoleAssignment).where(
                RoleAssignment.user_id == user_id,
                RoleAssignment.role_id == role_id,
                RoleAssignment.clinic_id == clinic_id,
                RoleAssignment.branch_id == branch_id,
                RoleAssignment.insurer_id == insurer_id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        return
    db.add(RoleAssignment(user_id=user_id, role_id=role_id, clinic_id=clinic_id, branch_id=branch_id, insurer_id=insurer_id))


async def main() -> None:
    async with AsyncSessionLocal() as db:
        roles = {code.value: await get_or_create_role(db, code.value) for code in RoleCode}
        for pais in TYC_COUNTRIES:
            await get_or_create_tyc(db, pais)

        clinic_a = await get_or_create_clinic(db, "Clínica Demo A", "MX")
        clinic_b = await get_or_create_clinic(db, "Clínica Demo B", "CL")
        clinic_c = await get_or_create_clinic(db, "Clínica Demo C", "BR")  # Tanda 7: emisión de Nota Fiscal
        branch_a1 = await get_or_create_branch(db, clinic_a.id, "Sucursal A1")

        # Perfiles de acceso reutilizables (48): los 12 perfiles base por clínica.
        await seed_permission_profiles(db, clinic_a.id)
        await seed_permission_profiles(db, clinic_b.id)

        # Catálogo CIE-10 (71.20): referencia global.
        await seed_cie10(db)

        # Entidad aseguradora (global, no tenant) — el rol se vincula a ella.
        insurer_x = (await db.execute(select(Insurer).where(Insurer.nombre == "Seguros Bienestar MX"))).scalar_one_or_none()
        if insurer_x is None:
            insurer_x = Insurer(nombre="Seguros Bienestar MX", pais="MX", tipo="seguro", contacto="convenios@bienestar.mx")
            db.add(insurer_x)
            await db.flush()

        super_admin = await get_or_create_user(db, "super@todoscare.dev", "Super Admin")
        admin_a = await get_or_create_user(db, "admin.a@todoscare.dev", "Admin Clínica A")
        admin_b = await get_or_create_user(db, "admin.b@todoscare.dev", "Admin Clínica B")
        medico_a = await get_or_create_user(db, "medico.a@todoscare.dev", "Dra. Nátaly")
        # A second médico in the same clinic with NO appointments — exists so
        # the "solo pacientes que atiende" isolation (Spec Médico §3) is
        # actually testable: he must be denied Camila's ficha.
        medico_b = await get_or_create_user(db, "medico.b@todoscare.dev", "Dr. Fuentes")
        empresa_a = await get_or_create_user(db, "empresa.a@todoscare.dev", "Clínica Demo A (portal)")
        # Portales de empresa para las clínicas CL y BR — emiten sus documentos
        # tributarios (boleta SII / Nota Fiscal) en el smoke test de Tanda 7.
        empresa_b = await get_or_create_user(db, "empresa.b@todoscare.dev", "Clínica Demo B (portal CL)")
        empresa_c = await get_or_create_user(db, "empresa.c@todoscare.dev", "Clínica Demo C (portal BR)")
        paciente_a = await get_or_create_user(db, "paciente.a@todoscare.dev", "Camila Rodríguez")
        aseguradora_x = await get_or_create_user(db, "aseguradora.x@todoscare.dev", "Aseguradora X")

        await assign_role(db, super_admin.id, roles[RoleCode.SUPER_ADMIN.value].id)
        await assign_role(db, admin_a.id, roles[RoleCode.CLINIC_ADMIN.value].id, clinic_id=clinic_a.id)
        await assign_role(db, admin_b.id, roles[RoleCode.CLINIC_ADMIN.value].id, clinic_id=clinic_b.id)
        await assign_role(db, medico_a.id, roles[RoleCode.MEDICO.value].id, clinic_id=clinic_a.id, branch_id=branch_a1.id)
        await assign_role(db, medico_b.id, roles[RoleCode.MEDICO.value].id, clinic_id=clinic_a.id, branch_id=branch_a1.id)
        await assign_role(db, empresa_a.id, roles[RoleCode.EMPRESA.value].id, clinic_id=clinic_a.id)
        await assign_role(db, empresa_b.id, roles[RoleCode.EMPRESA.value].id, clinic_id=clinic_b.id)
        await assign_role(db, empresa_c.id, roles[RoleCode.EMPRESA.value].id, clinic_id=clinic_c.id)
        await assign_role(db, paciente_a.id, roles[RoleCode.PACIENTE.value].id, clinic_id=clinic_a.id)
        # Fase 7: la aseguradora se vincula a su ENTIDAD (insurer), no a un
        # tenant clínico — un pagador opera sobre su cartera y su red de
        # clínicas en convenio (Spec Aseguradora Prestador §1).
        await assign_role(db, aseguradora_x.id, roles[RoleCode.ASEGURADORA.value].id, insurer_id=insurer_x.id)

        specialties = {}
        for nombre, icono in SPECIALTIES:
            specialties[nombre] = await get_or_create_specialty(db, nombre, icono)
        catalog = {}
        for nombre, precio, duracion_min in SERVICIOS_CLINICA_A:
            catalog[nombre] = await get_or_create_catalog_item(db, clinic_a.id, specialties[nombre].id, nombre, precio, duracion_min)

        # Agenda online pública (60): la clínica demo publica su reserva sin login
        # en /reservar/<slug> y ofrece sus prestaciones como reservables.
        if clinic_a.slug is None:
            clinic_a.slug = "clinica-demo-a"
        clinic_a.agenda_online = {"habilitada": True, "anticipacion_horas": 2, "ventana_dias": 45, "mensaje": "Reserva tu hora en línea; te confirmaremos a la brevedad."}
        for item in catalog.values():
            item.reservable_online = True

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
            # Camila ya aceptó la versión vigente de T&C de su país (para que
            # no arranque con tyc_pendiente=True). Si el admin publica una
            # versión nueva, ahí sí quedará pendiente de re-aceptar.
            tyc_mx = (await db.execute(select(TycVersion).where(TycVersion.pais == clinic_a.pais).order_by(TycVersion.publicado_en.desc()).limit(1))).scalar_one()
            db.add(TycAcceptance(patient_id=patient.id, tyc_version_id=tyc_mx.id, aceptado_en=datetime.now(timezone.utc)))
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

        # ── CRM (Fase 6) demo data ──
        # El CRM no guarda cifras: las calcula del ledger + agenda. Sembramos
        # los asientos que lo alimentan: (a) un ingreso del mes anterior para
        # que la variación mes-vs-mes no sea trivial; (b) ingresos de atención
        # ligados a una cita real (ref 'appointment:<id>') para "ingresos por
        # servicio" y el ticket promedio; (c) los splits 60% pendientes que la
        # pantalla de liquidaciones concilia. El prestador es Dr. Fuentes
        # (medico_b) a propósito: así no altera las liquidaciones de la Dra.
        # Nátaly que verifica la prueba del rol médico.
        existing_split = (await db.execute(select(PaymentSplit).where(PaymentSplit.clinic_id == clinic_a.id))).scalars().first()
        if not existing_split:
            prev = LedgerEntry(clinic_id=clinic_a.id, tipo="ingreso", monto=1200, ref="seed-prev")
            db.add(prev)
            await db.flush()
            prev.created_at = today.replace(day=1) - timedelta(days=2)  # mes anterior

            # Marketing digital: 2 campañas cuyo gasto (200+100=300) se asienta
            # en el ledger. Con 1 paciente nuevo este mes (Camila) => CAC = 300.
            campana_google = None
            for nombre, canal, presupuesto, gasto, leads, conv in [
                ("Google Ads — Chequeo preventivo", "google_ads", 500, 200, 40, 1),
                ("Instagram — Sonrisa perfecta", "instagram", 300, 100, 25, 0),
            ]:
                camp = MarketingCampaign(clinic_id=clinic_a.id, nombre=nombre, canal=canal, estado="activa", presupuesto=presupuesto, gasto=gasto, leads=leads, conversiones=conv)
                db.add(camp)
                await db.flush()
                db.add(LedgerEntry(clinic_id=clinic_a.id, tipo="gasto_marketing", monto=gasto, ref=f"campana:{camp.id}"))
                if canal == "google_ads":
                    campana_google = camp

            # Atribución real: Camila llegó por la campaña de Google Ads.
            patient_row = (await db.execute(select(Patient).where(Patient.clinic_id == clinic_a.id).order_by(Patient.created_at).limit(1))).scalar_one()
            patient_row.origen_campana_id = campana_google.id

            cita = (
                await db.execute(
                    select(Appointment).where(Appointment.clinic_id == clinic_a.id, Appointment.service_id.isnot(None)).limit(1)
                )
            ).scalar_one()
            for _ in range(3):
                led = LedgerEntry(clinic_id=clinic_a.id, tipo="ingreso", monto=270, ref=f"appointment:{cita.id}")
                db.add(led)
                await db.flush()
                db.add(
                    PaymentSplit(
                        clinic_id=clinic_a.id,
                        ledger_entry_id=led.id,
                        beneficiario_id=medico_b.id,
                        monto=162,  # 60% de 270
                        regla={"pct": 0.60, "base": 270},
                    )
                )

        # ── Aseguradora / Prestador (Fase 7) demo data ──
        # Un convenio vigente entre la aseguradora y Clínica Demo A, con un
        # arancel (cobertura 80% / copago) para "Médico general", Camila como
        # afiliada vigente, y una autorización pendiente de resolver.
        existing_agreement = (await db.execute(select(Agreement).where(Agreement.insurer_id == insurer_x.id, Agreement.clinic_id == clinic_a.id))).scalars().first()
        if not existing_agreement:
            patient_row = (await db.execute(select(Patient).where(Patient.clinic_id == clinic_a.id).order_by(Patient.created_at).limit(1))).scalar_one()
            servicio = catalog["Médico general"]
            agreement = Agreement(
                clinic_id=clinic_a.id,
                insurer_id=insurer_x.id,
                vigencia_inicio=(today - timedelta(days=90)).date(),
                vigencia_fin=(today + timedelta(days=275)).date(),
            )
            db.add(agreement)
            await db.flush()
            db.add(Arancel(clinic_id=clinic_a.id, agreement_id=agreement.id, service_id=servicio.id, cobertura_pct=80, copago=100))
            db.add(
                Affiliate(
                    insurer_id=insurer_x.id,
                    patient_id=patient_row.id,
                    documento_identidad="MX-CURP-CAMILA-01",
                    plan_cobertura="Plan Integral",
                    vigencia_desde=(today - timedelta(days=365)).date(),
                    vigencia_hasta=(today + timedelta(days=365)).date(),
                )
            )
            # Dos solicitudes pendientes: uno para aprobar, otro para rechazar.
            for _ in range(2):
                db.add(
                    Authorization(
                        clinic_id=clinic_a.id,
                        agreement_id=agreement.id,
                        patient_id=patient_row.id,
                        service_id=servicio.id,
                        estado="pendiente",
                    )
                )

        # ── Integraciones (Fase 8) demo data ──
        # Conectores habilitados por clínica (whatsapp/lab/farmacia/pago/mapas/
        # push). 'push' se deja inactivo a propósito para poder probar que un
        # conector deshabilitado rechaza el evento. Y se geolocalizan las
        # sucursales para el conector de mapas.
        existing_integ = (await db.execute(select(IntegrationConfig).where(IntegrationConfig.clinic_id == clinic_a.id))).scalars().first()
        if not existing_integ:
            for tipo, activo in [("whatsapp", True), ("lab", True), ("farmacia", True), ("pago", True), ("mapas", True), ("push", False), ("ia_clinica", True)]:
                db.add(IntegrationConfig(clinic_id=clinic_a.id, tipo=tipo, activo=activo, credenciales=None))
            branch_a1.geo = {"lat": 19.4326, "lng": -99.1332}  # CDMX centro
            branch_a1.direccion = "Av. Reforma 222, Cuauhtémoc, CDMX"

        # ── Tributario (Tanda 7) demo data ──
        # Chile: emisor con RUT + resolución SII + CAF (folios) para boleta,
        # factura y nota de crédito. Brasil: emisor com CNPJ + inscrições +
        # regime, com série para NFS-e (município) e NF-e (SEFAZ estadual).
        await seed_tax_emitter(
            db, clinic_b.id, "CL",
            tax_id="76.123.456-7",
            razon_social="Clínica Demo B SpA",
            giro="Servicios de salud",
            direccion="Av. Providencia 1234, Santiago",
            config={"acteco": "869010", "comuna": "Providencia", "resolucion_sii_numero": 80, "resolucion_sii_fecha": "2014-08-22"},
            folios=[
                ("boleta_electronica", None, 1, 1000, "CAF-39-2026"),
                ("boleta_exenta", None, 1, 1000, "CAF-41-2026"),  # prestaciones médicas/odontológicas (exentas)
                ("factura_electronica", None, 1, 500, "CAF-33-2026"),
                ("factura_exenta", None, 1, 500, "CAF-34-2026"),
                ("nota_credito", None, 1, 500, "CAF-61-2026"),
            ],
        )
        await seed_tax_emitter(
            db, clinic_a.id, "MX",
            tax_id="MECA850101AB1",
            razon_social="Clínica Demo A SA de CV",
            giro="Servicios de salud",
            direccion="Av. Reforma 222, Cuauhtémoc, CDMX",
            config={"regimen_fiscal": "601", "codigo_postal": "06600", "uso_cfdi": "G03"},
            folios=[
                ("factura", "A", 1, 100000, "CSD-A"),        # CFDI de Ingreso
                ("nota_credito", "A", 1, 100000, "CSD-A-NC"),  # CFDI de Egreso
            ],
        )
        await seed_tax_emitter(
            db, clinic_c.id, "BR",
            tax_id="12.345.678/0001-99",
            razon_social="Clínica Demo C Ltda",
            giro="Atividades de atenção à saúde humana",
            direccion="Av. Paulista 1000, São Paulo",
            config={
                "inscricao_municipal": "1.234.567-8", "inscricao_estadual": "110.042.490.114",
                "cnae": "8630-5/03", "regime_tributario": "simples",
                "municipio_ibge": "3550308", "municipio_nome": "São Paulo", "uf": "SP",
                "iss_aliquota": 0.05, "icms_aliquota": 0.18,
            },
            folios=[
                ("nfse", "RPS", 1, 100000, "SERIE-NFSE"),
                ("nfe", "1", 1, 100000, "SERIE-NFE"),
            ],
        )

        await db.commit()

    print("Seed OK. Demo password for every user:", DEMO_PASSWORD)
    print("  super@todoscare.dev        -> super_admin (global)")
    print("  admin.a@todoscare.dev      -> clinic_admin @ Clínica Demo A")
    print("  admin.b@todoscare.dev      -> clinic_admin @ Clínica Demo B")
    print("  medico.a@todoscare.dev     -> medico @ Clínica Demo A / Sucursal A1 (atiende a Camila)")
    print("  medico.b@todoscare.dev     -> medico @ Clínica Demo A / Sucursal A1 (sin citas)")
    print("  empresa.a@todoscare.dev    -> empresa @ Clínica Demo A")
    print("  empresa.b@todoscare.dev    -> empresa @ Clínica Demo B (CL — emite boleta SII)")
    print("  empresa.c@todoscare.dev    -> empresa @ Clínica Demo C (BR — emite Nota Fiscal)")
    print("  paciente.a@todoscare.dev   -> paciente @ Clínica Demo A")
    print("  aseguradora.x@todoscare.dev-> aseguradora @ Seguros Bienestar MX (convenio con Clínica Demo A)")


if __name__ == "__main__":
    asyncio.run(main())
