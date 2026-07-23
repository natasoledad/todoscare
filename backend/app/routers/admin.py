import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import hash_password
from app.models.finance import LedgerEntry, PaymentSplit, Plan
from app.models.identity import Role, RoleAssignment, User
from app.models.integrations import AuditLog, IntegrationConfig
from app.models.patient import Patient, TycVersion
from app.models.scheduling import Appointment
from app.models.tenant import Branch, Clinic
from app.models.wallet import WalletTransaction
from app.rbac.deps import require
from app.rbac.permissions import Action, Resource, RoleCode
from app.schemas.admin import (
    AdminKpis,
    AltaClinicaIn,
    AltaClinicaOut,
    AsignarRolIn,
    AuditOut,
    ClinicOut,
    ClinicUpdate,
    CrearUsuarioIn,
    FinanzasResumen,
    IntegracionOut,
    IntegracionUpdate,
    LedgerEntryOut,
    PlanIn,
    PlanOut,
    PublicarTycIn,
    RoleAssignmentOut,
    SucursalIn,
    SucursalOut,
    TycOut,
    UsuarioOut,
)
from app.services.admin import admin_scope, assert_clinic_in_scope, assert_super_admin
from app.tenancy.context import TenantContext

router = APIRouter(prefix="/admin", tags=["admin"])

VALID_ROLES = {r.value for r in RoleCode}


async def _role_by_code(db: AsyncSession, code: str) -> Role:
    if code not in VALID_ROLES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Rol inválido: {code}")
    role = (await db.execute(select(Role).where(Role.code == code))).scalar_one_or_none()
    if role is None:
        role = Role(code=code)
        db.add(role)
        await db.flush()
    return role


# ─────────────────────────── inicio / KPIs ───────────────────────────
@router.get("/inicio", response_model=AdminKpis)
async def inicio(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CRM_CONSOLIDADO_GLOBAL, Action.VER)),
) -> AdminKpis:
    scope = admin_scope(ctx)
    today = datetime.now(timezone.utc).date()
    month_start = today.replace(day=1)

    def scoped(col):
        return col.in_(scope) if scope is not None else col.isnot(None)

    clinicas = (await db.execute(select(func.count(Clinic.id)).where(Clinic.deleted_at.is_(None), scoped(Clinic.id) if scope is not None else Clinic.id.isnot(None)))).scalar_one()
    pacientes = (await db.execute(select(func.count(Patient.id)).where(Patient.deleted_at.is_(None), scoped(Patient.clinic_id)))).scalar_one()
    citas_hoy = (
        await db.execute(
            select(func.count(Appointment.id)).where(
                Appointment.deleted_at.is_(None), Appointment.estado != "cancelada", func.date(func.lower(Appointment.slot)) == today, scoped(Appointment.clinic_id)
            )
        )
    ).scalar_one()
    ingresos_mes = (
        await db.execute(
            select(func.coalesce(func.sum(LedgerEntry.monto), 0)).where(LedgerEntry.tipo == "ingreso", func.date(LedgerEntry.created_at) >= month_start, scoped(LedgerEntry.clinic_id))
        )
    ).scalar_one()

    return AdminKpis(
        alcance="plataforma" if scope is None else "clínica",
        clinicas=clinicas,
        pacientes=pacientes,
        citas_hoy=citas_hoy,
        ingresos_mes=float(ingresos_mes),
    )


# ─────────────────────────── clínicas / sucursales ───────────────────────────
@router.get("/clinicas", response_model=list[ClinicOut])
async def list_clinicas(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CLINICAS_SUCURSALES, Action.VER)),
) -> list[ClinicOut]:
    scope = admin_scope(ctx)
    q = select(Clinic).where(Clinic.deleted_at.is_(None))
    if scope is not None:
        q = q.where(Clinic.id.in_(scope))
    clinics = (await db.execute(q.order_by(Clinic.razon_social))).scalars().all()
    out = []
    for c in clinics:
        n_suc = (await db.execute(select(func.count(Branch.id)).where(Branch.clinic_id == c.id, Branch.deleted_at.is_(None)))).scalar_one()
        n_pac = (await db.execute(select(func.count(Patient.id)).where(Patient.clinic_id == c.id, Patient.deleted_at.is_(None)))).scalar_one()
        out.append(ClinicOut(id=c.id, razon_social=c.razon_social, responsable_sanitario=c.responsable_sanitario, pais=c.pais, activo=c.activo, sucursales=n_suc, pacientes=n_pac))
    return out


@router.post("/clinicas", response_model=AltaClinicaOut, status_code=status.HTTP_201_CREATED)
async def alta_clinica(
    payload: AltaClinicaIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CLINICAS_SUCURSALES, Action.CREAR)),
) -> AltaClinicaOut:
    """Alta de un nuevo tenant (Spec Admin §6.1) — solo super_admin. Crea la
    clínica, su primera sucursal y el usuario admin de clínica inicial. El
    tenant queda aislado por clinic_id y operativo."""
    assert_super_admin(ctx)

    if (await db.execute(select(User).where(User.email == payload.admin_correo))).scalar_one_or_none():
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe un usuario con ese correo")

    clinic = Clinic(razon_social=payload.razon_social, pais=payload.pais.upper(), responsable_sanitario=payload.responsable_sanitario)
    db.add(clinic)
    await db.flush()

    branch = Branch(clinic_id=clinic.id, nombre=payload.sucursal_nombre)
    db.add(branch)

    admin_user = User(email=payload.admin_correo, password_hash=hash_password(payload.admin_password), nombre=payload.admin_nombre)
    db.add(admin_user)
    await db.flush()

    role = await _role_by_code(db, RoleCode.CLINIC_ADMIN.value)
    db.add(RoleAssignment(user_id=admin_user.id, role_id=role.id, clinic_id=clinic.id))

    await db.commit()
    return AltaClinicaOut(clinic_id=clinic.id, branch_id=branch.id, admin_user_id=admin_user.id)


@router.patch("/clinicas/{clinic_id}", response_model=ClinicOut)
async def editar_clinica(
    clinic_id: uuid.UUID,
    payload: ClinicUpdate,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CLINICAS_SUCURSALES, Action.EDITAR)),
) -> ClinicOut:
    assert_clinic_in_scope(ctx, clinic_id)
    clinic = await db.get(Clinic, clinic_id)
    if clinic is None or clinic.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Clínica no encontrada")
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(clinic, k, v)
    await db.commit()
    n_suc = (await db.execute(select(func.count(Branch.id)).where(Branch.clinic_id == clinic.id, Branch.deleted_at.is_(None)))).scalar_one()
    n_pac = (await db.execute(select(func.count(Patient.id)).where(Patient.clinic_id == clinic.id, Patient.deleted_at.is_(None)))).scalar_one()
    return ClinicOut(id=clinic.id, razon_social=clinic.razon_social, responsable_sanitario=clinic.responsable_sanitario, pais=clinic.pais, activo=clinic.activo, sucursales=n_suc, pacientes=n_pac)


@router.delete("/clinicas/{clinic_id}", status_code=status.HTTP_204_NO_CONTENT)
async def baja_clinica(
    clinic_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CLINICAS_SUCURSALES, Action.ELIMINAR)),
) -> None:
    """Baja lógica del tenant (Spec Admin §7, doble confirmación en UI). Solo
    super_admin da de baja una clínica entera."""
    assert_super_admin(ctx)
    clinic = await db.get(Clinic, clinic_id)
    if clinic is None or clinic.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Clínica no encontrada")
    clinic.activo = False
    await db.delete(clinic)  # soft delete via listener
    await db.commit()


@router.get("/clinicas/{clinic_id}/sucursales", response_model=list[SucursalOut])
async def list_sucursales(
    clinic_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CLINICAS_SUCURSALES, Action.VER)),
) -> list[SucursalOut]:
    assert_clinic_in_scope(ctx, clinic_id)
    rows = (await db.execute(select(Branch).where(Branch.clinic_id == clinic_id, Branch.deleted_at.is_(None)))).scalars().all()
    return [SucursalOut(id=b.id, nombre=b.nombre, direccion=b.direccion) for b in rows]


@router.post("/clinicas/{clinic_id}/sucursales", response_model=SucursalOut, status_code=status.HTTP_201_CREATED)
async def crear_sucursal(
    clinic_id: uuid.UUID,
    payload: SucursalIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CLINICAS_SUCURSALES, Action.CREAR)),
) -> SucursalOut:
    assert_clinic_in_scope(ctx, clinic_id)
    b = Branch(clinic_id=clinic_id, nombre=payload.nombre, direccion=payload.direccion)
    db.add(b)
    await db.commit()
    await db.refresh(b)
    return SucursalOut(id=b.id, nombre=b.nombre, direccion=b.direccion)


# ─────────────────────────── usuarios / roles ───────────────────────────
@router.get("/usuarios", response_model=list[UsuarioOut])
async def list_usuarios(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.USUARIOS_ROLES, Action.VER)),
) -> list[UsuarioOut]:
    scope = admin_scope(ctx)
    ra_rows = (
        await db.execute(select(RoleAssignment, Role.code).join(Role, Role.id == RoleAssignment.role_id).where(RoleAssignment.deleted_at.is_(None)))
    ).all()
    by_user: dict[uuid.UUID, list[RoleAssignmentOut]] = {}
    for ra, code in ra_rows:
        if scope is not None and (ra.clinic_id is None or ra.clinic_id not in scope):
            continue
        by_user.setdefault(ra.user_id, []).append(RoleAssignmentOut(id=ra.id, role=code, clinic_id=ra.clinic_id, branch_id=ra.branch_id))
    if not by_user:
        return []
    users = (await db.execute(select(User).where(User.id.in_(by_user.keys()), User.deleted_at.is_(None)))).scalars().all()
    return [UsuarioOut(id=u.id, nombre=u.nombre, email=u.email, activo=u.activo, roles=by_user.get(u.id, [])) for u in users]


@router.post("/usuarios", response_model=UsuarioOut, status_code=status.HTTP_201_CREATED)
async def crear_usuario(
    payload: CrearUsuarioIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.USUARIOS_ROLES, Action.CREAR)),
) -> UsuarioOut:
    if payload.clinic_id is not None:
        assert_clinic_in_scope(ctx, payload.clinic_id)
    else:
        assert_super_admin(ctx)  # rol sin clínica (p. ej. super_admin) solo lo crea un super_admin
    if (await db.execute(select(User).where(User.email == payload.correo))).scalar_one_or_none():
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe un usuario con ese correo")

    user = User(email=payload.correo, password_hash=hash_password(payload.password), nombre=payload.nombre)
    db.add(user)
    await db.flush()
    role = await _role_by_code(db, payload.role)
    db.add(RoleAssignment(user_id=user.id, role_id=role.id, clinic_id=payload.clinic_id, branch_id=payload.branch_id))
    await db.commit()
    return UsuarioOut(
        id=user.id, nombre=user.nombre, email=user.email, activo=user.activo,
        roles=[RoleAssignmentOut(id=uuid.uuid4(), role=payload.role, clinic_id=payload.clinic_id, branch_id=payload.branch_id)],
    )


@router.post("/usuarios/{user_id}/roles", status_code=status.HTTP_201_CREATED)
async def asignar_rol(
    user_id: uuid.UUID,
    payload: AsignarRolIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.USUARIOS_ROLES, Action.EDITAR)),
) -> dict:
    if payload.clinic_id is not None:
        assert_clinic_in_scope(ctx, payload.clinic_id)
    else:
        assert_super_admin(ctx)
    user = await db.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")
    role = await _role_by_code(db, payload.role)
    db.add(RoleAssignment(user_id=user_id, role_id=role.id, clinic_id=payload.clinic_id, branch_id=payload.branch_id))
    await db.commit()
    return {"ok": True}


@router.delete("/roles/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def quitar_rol(
    assignment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.USUARIOS_ROLES, Action.ELIMINAR)),
) -> None:
    ra = await db.get(RoleAssignment, assignment_id)
    if ra is None or ra.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Asignación no encontrada")
    if ra.clinic_id is not None:
        assert_clinic_in_scope(ctx, ra.clinic_id)
    else:
        assert_super_admin(ctx)
    await db.delete(ra)  # soft delete via listener
    await db.commit()


# ─────────────────────────── planes (super_admin) ───────────────────────────
@router.get("/planes", response_model=list[PlanOut])
async def list_planes(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.PLANES_PRECIOS, Action.VER)),
) -> list[PlanOut]:
    rows = (await db.execute(select(Plan).where(Plan.deleted_at.is_(None)).order_by(Plan.tipo, Plan.nombre))).scalars().all()
    return [PlanOut(id=p.id, tipo=p.tipo, esfera=p.esfera, nombre=p.nombre, precio=float(p.precio)) for p in rows]


@router.post("/planes", response_model=PlanOut, status_code=status.HTTP_201_CREATED)
async def crear_plan(
    payload: PlanIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.PLANES_PRECIOS, Action.CREAR)),
) -> PlanOut:
    assert_super_admin(ctx)
    if payload.tipo == "publico" and payload.esfera is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Un plan público debe indicar esfera (federal/estatal/municipal)")
    p = Plan(**payload.model_dump())
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return PlanOut(id=p.id, tipo=p.tipo, esfera=p.esfera, nombre=p.nombre, precio=float(p.precio))


@router.delete("/planes/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_plan(
    plan_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.PLANES_PRECIOS, Action.ELIMINAR)),
) -> None:
    assert_super_admin(ctx)
    p = await db.get(Plan, plan_id)
    if p is None or p.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Plan no encontrado")
    await db.delete(p)
    await db.commit()


# ─────────────────────────── T&C por país ───────────────────────────
@router.get("/tyc", response_model=list[TycOut])
async def list_tyc(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.TYC_PAIS, Action.VER)),
) -> list[TycOut]:
    rows = (await db.execute(select(TycVersion).where(TycVersion.deleted_at.is_(None)).order_by(TycVersion.pais, TycVersion.publicado_en.desc()))).scalars().all()
    return [TycOut(id=t.id, pais=t.pais, version=t.version, publicado_en=t.publicado_en) for t in rows]


@router.post("/tyc", response_model=TycOut, status_code=status.HTTP_201_CREATED)
async def publicar_tyc(
    payload: PublicarTycIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.TYC_PAIS, Action.CREAR)),
) -> TycOut:
    """Publicar una nueva versión de T&C por país (Spec Admin §6.2). Al
    publicarse, todos los pacientes de ese país deben re-aceptar en su
    próximo ingreso (ver `tyc_pendiente` en /patients/me). El histórico de
    versiones nunca se borra."""
    assert_super_admin(ctx)
    t = TycVersion(pais=payload.pais.upper(), version=payload.version, contenido=payload.contenido, publicado_en=datetime.now(timezone.utc))
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return TycOut(id=t.id, pais=t.pais, version=t.version, publicado_en=t.publicado_en)


# ─────────────────────────── finanzas (read-only, inmutable) ───────────────────────────
@router.get("/finanzas", response_model=FinanzasResumen)
async def finanzas(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.LEDGER_FINANCIERO, Action.VER)),
) -> FinanzasResumen:
    scope = admin_scope(ctx)

    def scoped(col):
        return col.in_(scope) if scope is not None else col.isnot(None)

    ingresos = (await db.execute(select(func.coalesce(func.sum(LedgerEntry.monto), 0)).where(LedgerEntry.tipo == "ingreso", scoped(LedgerEntry.clinic_id)))).scalar_one()
    splits = (await db.execute(select(func.coalesce(func.sum(PaymentSplit.monto), 0)).where(scoped(PaymentSplit.clinic_id)))).scalar_one()
    cashback = (
        await db.execute(select(func.coalesce(func.sum(WalletTransaction.cashback), 0)).where(WalletTransaction.cashback > 0, scoped(WalletTransaction.clinic_id)))
    ).scalar_one()
    return FinanzasResumen(ingresos_mes=float(ingresos), split_profesionales=float(splits), cashback_emitido=float(cashback))


@router.get("/finanzas/ledger", response_model=list[LedgerEntryOut])
async def ledger(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.LEDGER_FINANCIERO, Action.VER)),
) -> list[LedgerEntryOut]:
    scope = admin_scope(ctx)
    q = select(LedgerEntry).where(LedgerEntry.deleted_at.is_(None))
    if scope is not None:
        q = q.where(LedgerEntry.clinic_id.in_(scope))
    rows = (await db.execute(q.order_by(LedgerEntry.created_at.desc()).limit(100))).scalars().all()
    return [LedgerEntryOut(fecha=e.created_at, tipo=e.tipo, monto=float(e.monto), moneda=e.moneda, ref=e.ref) for e in rows]


# ─────────────────────────── auditoría (solo metadatos, nunca contenido clínico) ───────────────────────────
@router.get("/auditoria", response_model=list[AuditOut])
async def auditoria(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.FICHA_CLINICA_METADATOS, Action.VER)),
) -> list[AuditOut]:
    scope = admin_scope(ctx)
    q = select(AuditLog, User.nombre).join(User, User.id == AuditLog.actor_id, isouter=True).where(AuditLog.deleted_at.is_(None))
    if scope is not None:
        q = q.where(AuditLog.clinic_id.in_(scope))
    rows = (await db.execute(q.order_by(AuditLog.fecha.desc()).limit(100))).all()
    return [AuditOut(fecha=a.fecha, actor=nombre, accion=a.accion, recurso=a.recurso, clinic_id=a.clinic_id) for a, nombre in rows]


# ─────────────────────────── integraciones ───────────────────────────
@router.get("/integraciones", response_model=list[IntegracionOut])
async def list_integraciones(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CLINICAS_SUCURSALES, Action.VER)),
) -> list[IntegracionOut]:
    scope = admin_scope(ctx)
    q = select(IntegrationConfig).where(IntegrationConfig.deleted_at.is_(None))
    if scope is not None:
        q = q.where(IntegrationConfig.clinic_id.in_(scope))
    rows = (await db.execute(q)).scalars().all()
    return [IntegracionOut(id=i.id, tipo=i.tipo, activo=i.activo) for i in rows]


@router.patch("/integraciones/{integ_id}", response_model=IntegracionOut)
async def toggle_integracion(
    integ_id: uuid.UUID,
    payload: IntegracionUpdate,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CLINICAS_SUCURSALES, Action.EDITAR)),
) -> IntegracionOut:
    integ = await db.get(IntegrationConfig, integ_id)
    if integ is None or integ.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Integración no encontrada")
    assert_clinic_in_scope(ctx, integ.clinic_id)
    integ.activo = payload.activo
    await db.commit()
    return IntegracionOut(id=integ.id, tipo=integ.tipo, activo=integ.activo)
