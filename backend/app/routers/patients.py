from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import create_access_token, hash_password
from app.models.identity import Role, RoleAssignment, User
from app.models.marketing import MarketingCampaign
from app.models.patient import Dependent, Patient, TycAcceptance, TycVersion
from app.models.tenant import Clinic
from app.models.wallet import WalletAccount
from app.rbac.deps import require
from app.rbac.permissions import Action, Resource, RoleCode
from app.schemas.patients import (
    AuthOut,
    ClinicPublicOut,
    DependentOut,
    FichaUpdateInput,
    OnboardingInput,
    PatientMeOut,
    RegisterInput,
    TycVersionOut,
    WalletOut,
)
from app.services.gamification import (
    DEPENDENT_BONUS_POINTS,
    FICHA_COMPLETA_BONUS_POINTS,
    ONBOARDING_BONUS_POINTS,
    REGISTER_BONUS_POINTS,
    award,
    is_ficha_completa,
)
from app.tenancy.context import TenantContext

router = APIRouter(tags=["patients"])


@router.get("/clinics/public", response_model=list[ClinicPublicOut])
async def list_public_clinics(db: AsyncSession = Depends(get_db)) -> list[ClinicPublicOut]:
    rows = (await db.execute(select(Clinic).where(Clinic.activo.is_(True), Clinic.deleted_at.is_(None)))).scalars().all()
    return [ClinicPublicOut(id=c.id, razon_social=c.razon_social, pais=c.pais) for c in rows]


@router.get("/tyc/latest", response_model=TycVersionOut)
async def get_latest_tyc(pais: str, db: AsyncSession = Depends(get_db)) -> TycVersionOut:
    row = (
        await db.execute(
            select(TycVersion)
            .where(TycVersion.pais == pais, TycVersion.deleted_at.is_(None))
            .order_by(TycVersion.publicado_en.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Sin T&C publicados para el país '{pais}'")
    return TycVersionOut.model_validate(row, from_attributes=True)


async def _get_or_create_paciente_role(db: AsyncSession) -> Role:
    role = (await db.execute(select(Role).where(Role.code == RoleCode.PACIENTE.value))).scalar_one_or_none()
    if role is None:
        role = Role(code=RoleCode.PACIENTE.value)
        db.add(role)
        await db.flush()
    return role


@router.post("/patients/register", response_model=AuthOut, status_code=status.HTTP_201_CREATED)
async def register_patient(payload: RegisterInput, db: AsyncSession = Depends(get_db)) -> AuthOut:
    existing = (await db.execute(select(User).where(User.email == payload.correo))).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe una cuenta con ese correo")

    clinic = await db.get(Clinic, payload.clinic_id)
    if clinic is None or not clinic.activo:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Clínica inválida")

    tyc = await db.get(TycVersion, payload.tyc_version_id)
    if tyc is None or tyc.pais != clinic.pais:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Versión de T&C inválida para el país de la clínica")

    # Atribución de marketing (opcional): la campaña debe ser de la misma clínica.
    origen_campana_id = None
    if payload.campana_id is not None:
        camp = await db.get(MarketingCampaign, payload.campana_id)
        if camp is None or camp.clinic_id != clinic.id or camp.deleted_at is not None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Campaña de atribución inválida")
        origen_campana_id = camp.id

    user = User(email=payload.correo, password_hash=hash_password(payload.password), nombre=payload.nombre, telefono=payload.telefono)
    db.add(user)
    await db.flush()

    patient = Patient(clinic_id=clinic.id, user_id=user.id, rut=payload.rut, direccion=payload.direccion, nivel="Bronce", ficha={}, origen_campana_id=origen_campana_id)
    db.add(patient)
    await db.flush()

    wallet = WalletAccount(clinic_id=clinic.id, patient_id=patient.id)
    db.add(wallet)
    await db.flush()

    await award(db, wallet=wallet, patient=patient, tipo="registro", puntos=REGISTER_BONUS_POINTS, motivo="Bono de bienvenida")

    db.add(TycAcceptance(patient_id=patient.id, tyc_version_id=tyc.id, aceptado_en=datetime.now(timezone.utc)))

    role = await _get_or_create_paciente_role(db)
    db.add(RoleAssignment(user_id=user.id, role_id=role.id, clinic_id=clinic.id))

    await db.commit()

    token = create_access_token({"sub": str(user.id)})
    return AuthOut(access_token=token)


async def get_own_patient(db: AsyncSession, ctx: TenantContext) -> Patient:
    patient = (await db.execute(select(Patient).where(Patient.user_id == ctx.user_id))).scalar_one_or_none()
    if patient is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No se encontró un perfil de paciente para este usuario")
    return patient


async def _tyc_pendiente(db: AsyncSession, patient: Patient) -> bool:
    """True si el admin publicó una versión de T&C (del país de la clínica)
    más nueva que la última que este paciente aceptó — re-aceptación
    bloqueante (Spec Paciente §9 / Spec Admin §6.2)."""
    clinic = await db.get(Clinic, patient.clinic_id)
    latest = (
        await db.execute(
            select(TycVersion).where(TycVersion.pais == clinic.pais, TycVersion.deleted_at.is_(None)).order_by(TycVersion.publicado_en.desc()).limit(1)
        )
    ).scalar_one_or_none()
    if latest is None:
        return False
    accepted = (
        await db.execute(select(TycAcceptance.id).where(TycAcceptance.patient_id == patient.id, TycAcceptance.tyc_version_id == latest.id))
    ).first()
    return accepted is None


async def _patient_out(db: AsyncSession, patient: Patient, user: User) -> PatientMeOut:
    wallet = (await db.execute(select(WalletAccount).where(WalletAccount.patient_id == patient.id))).scalar_one()
    dependents = (await db.execute(select(Dependent).where(Dependent.patient_id == patient.id, Dependent.deleted_at.is_(None)))).scalars().all()
    return PatientMeOut(
        id=patient.id,
        nombre=user.nombre,
        correo=user.email,
        telefono=user.telefono or "",
        direccion=patient.direccion,
        rut=patient.rut,
        nivel=patient.nivel,
        onboarding_completado=patient.onboarding_completado,
        tyc_pendiente=await _tyc_pendiente(db, patient),
        wallet=WalletOut(puntos=wallet.puntos, cashback=float(wallet.cashback)),
        dependents=[DependentOut(id=d.id, nombre=d.nombre) for d in dependents],
        ficha=patient.ficha or {},
    )


@router.get("/patients/me", response_model=PatientMeOut)
async def get_me(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.OWN_MEDICAL_RECORD, Action.VER)),
) -> PatientMeOut:
    patient = await get_own_patient(db, ctx)
    user = await db.get(User, ctx.user_id)
    return await _patient_out(db, patient, user)


@router.post("/patients/onboarding", response_model=PatientMeOut)
async def submit_onboarding(
    payload: OnboardingInput,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.OWN_MEDICAL_RECORD, Action.CREAR)),
) -> PatientMeOut:
    patient = await get_own_patient(db, ctx)
    wallet = (await db.execute(select(WalletAccount).where(WalletAccount.patient_id == patient.id))).scalar_one()

    patient.ficha = {**(patient.ficha or {}), **payload.answers.model_dump(exclude_none=True)}
    patient.onboarding_completado = True

    for dep in payload.dependents:
        db.add(Dependent(clinic_id=patient.clinic_id, patient_id=patient.id, nombre=dep.nombre))

    total_points = ONBOARDING_BONUS_POINTS + DEPENDENT_BONUS_POINTS * len(payload.dependents)
    await award(db, wallet=wallet, patient=patient, tipo="onboarding_completado", puntos=total_points, motivo="Onboarding completado")

    await db.commit()
    await db.refresh(patient)
    user = await db.get(User, ctx.user_id)
    return await _patient_out(db, patient, user)


@router.patch("/patients/me/ficha", response_model=PatientMeOut)
async def update_ficha(
    payload: FichaUpdateInput,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.OWN_MEDICAL_RECORD, Action.EDITAR)),
) -> PatientMeOut:
    patient = await get_own_patient(db, ctx)
    patient.ficha = {**(patient.ficha or {}), **payload.model_dump(exclude_none=True)}

    if not patient.ficha_completa_bonus_otorgado and is_ficha_completa(patient.ficha):
        wallet = (await db.execute(select(WalletAccount).where(WalletAccount.patient_id == patient.id))).scalar_one()
        await award(
            db,
            wallet=wallet,
            patient=patient,
            tipo="ficha_completada",
            puntos=FICHA_COMPLETA_BONUS_POINTS,
            motivo="Ficha clínica completada al 100%",
        )
        patient.ficha_completa_bonus_otorgado = True

    await db.commit()
    await db.refresh(patient)
    user = await db.get(User, ctx.user_id)
    return await _patient_out(db, patient, user)
