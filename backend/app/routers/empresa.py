import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import Range
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.catalog import CatalogItem, Promotion, Specialty
from app.models.finance import Company, CompanyEmployee, LedgerEntry
from app.models.identity import Role, RoleAssignment, User
from app.models.patient import Patient
from app.models.scheduling import Appointment, AvailabilityBlock
from app.models.tenant import Branch, Clinic
from app.rbac.deps import require
from app.rbac.permissions import Action, Resource, RoleCode
from app.schemas.empresa import (
    BloqueIn,
    BloqueOut,
    BloqueUpdate,
    BranchOut,
    FuncionarioIn,
    FuncionarioOut,
    InfoEmpresaOut,
    InfoEmpresaUpdate,
    KpisOut,
    ProfesionalOut,
    PromocionIn,
    PromocionOut,
    PromocionUpdate,
    ServicioAdminOut,
    ServicioIn,
    ServicioUpdate,
    ServicioVendido,
)
from app.tenancy.context import TenantContext

router = APIRouter(prefix="/empresa", tags=["empresa"])


def empresa_clinic_id(ctx: TenantContext) -> uuid.UUID:
    ids = ctx.clinic_ids()
    if not ids:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "La cuenta de empresa no tiene una clínica asignada")
    return next(iter(ids))


# ─────────────────────────── inicio / KPIs ───────────────────────────
@router.get("/inicio", response_model=KpisOut)
async def inicio(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CRM_KPIS_CLINICA, Action.VER)),
) -> KpisOut:
    clinic_id = empresa_clinic_id(ctx)
    clinic = await db.get(Clinic, clinic_id)
    today = datetime.now(timezone.utc).date()
    month_start = today.replace(day=1)

    citas_hoy = (
        await db.execute(
            select(func.count(Appointment.id)).where(
                Appointment.clinic_id == clinic_id,
                Appointment.deleted_at.is_(None),
                Appointment.estado != "cancelada",
                func.date(func.lower(Appointment.slot)) == today,
            )
        )
    ).scalar_one()

    ingresos_mes = (
        await db.execute(
            select(func.coalesce(func.sum(LedgerEntry.monto), 0)).where(
                LedgerEntry.clinic_id == clinic_id,
                LedgerEntry.tipo == "ingreso",
                func.date(LedgerEntry.created_at) >= month_start,
            )
        )
    ).scalar_one()

    servicios_activos = (
        await db.execute(
            select(func.count(CatalogItem.id)).where(
                CatalogItem.clinic_id == clinic_id, CatalogItem.tipo == "servicio", CatalogItem.activo.is_(True), CatalogItem.deleted_at.is_(None)
            )
        )
    ).scalar_one()

    promos_activas = (
        await db.execute(
            select(func.count(Promotion.id)).where(Promotion.clinic_id == clinic_id, Promotion.estado == "Activa", Promotion.deleted_at.is_(None))
        )
    ).scalar_one()

    vendidos = (
        await db.execute(
            select(CatalogItem.nombre, func.count(Appointment.id).label("c"))
            .join(Appointment, Appointment.service_id == CatalogItem.id)
            .where(Appointment.clinic_id == clinic_id, Appointment.deleted_at.is_(None), Appointment.estado != "cancelada")
            .group_by(CatalogItem.nombre)
            .order_by(func.count(Appointment.id).desc())
            .limit(3)
        )
    ).all()

    return KpisOut(
        clinic_nombre=clinic.razon_social,
        citas_hoy=citas_hoy,
        ingresos_mes=float(ingresos_mes),
        servicios_activos=servicios_activos,
        promos_activas=promos_activas,
        mas_vendidos=[ServicioVendido(nombre=n, cantidad=c) for n, c in vendidos],
    )


# ─────────────────────────── agendas ───────────────────────────
@router.get("/profesionales", response_model=list[ProfesionalOut])
async def profesionales(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CLINIC_AGENDAS, Action.VER)),
) -> list[ProfesionalOut]:
    clinic_id = empresa_clinic_id(ctx)
    rows = (
        await db.execute(
            select(User.id, User.nombre)
            .join(RoleAssignment, RoleAssignment.user_id == User.id)
            .join(Role, Role.id == RoleAssignment.role_id)
            .where(Role.code == RoleCode.MEDICO.value, RoleAssignment.clinic_id == clinic_id, RoleAssignment.deleted_at.is_(None))
            .distinct()
        )
    ).all()
    return [ProfesionalOut(id=i, nombre=n) for i, n in rows]


@router.get("/sucursales", response_model=list[BranchOut])
async def sucursales(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CLINIC_AGENDAS, Action.VER)),
) -> list[BranchOut]:
    clinic_id = empresa_clinic_id(ctx)
    rows = (await db.execute(select(Branch).where(Branch.clinic_id == clinic_id, Branch.deleted_at.is_(None)))).scalars().all()
    return [BranchOut(id=b.id, nombre=b.nombre) for b in rows]


async def _bloque_out(db: AsyncSession, block: AvailabilityBlock) -> BloqueOut:
    prof = await db.get(User, block.professional_id)
    branch = await db.get(Branch, block.branch_id)
    return BloqueOut(
        id=block.id,
        professional_id=block.professional_id,
        professional_nombre=prof.nombre if prof else "",
        branch_nombre=branch.nombre if branch else "",
        inicio=block.rango.lower,
        fin=block.rango.upper,
        reglas=block.reglas,
    )


@router.get("/agendas", response_model=list[BloqueOut])
async def list_agendas(
    professional_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CLINIC_AGENDAS, Action.VER)),
) -> list[BloqueOut]:
    clinic_id = empresa_clinic_id(ctx)
    q = select(AvailabilityBlock).where(AvailabilityBlock.clinic_id == clinic_id, AvailabilityBlock.deleted_at.is_(None))
    if professional_id:
        q = q.where(AvailabilityBlock.professional_id == professional_id)
    rows = (await db.execute(q.order_by(AvailabilityBlock.created_at.desc()))).scalars().all()
    return [await _bloque_out(db, b) for b in rows]


@router.post("/agendas", response_model=BloqueOut, status_code=status.HTTP_201_CREATED)
async def crear_bloque(
    payload: BloqueIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CLINIC_AGENDAS, Action.CREAR)),
) -> BloqueOut:
    clinic_id = empresa_clinic_id(ctx)
    if payload.fin <= payload.inicio:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El fin del bloque debe ser posterior al inicio")
    branch = await db.get(Branch, payload.branch_id)
    if branch is None or branch.clinic_id != clinic_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Sucursal inválida")
    block = AvailabilityBlock(
        clinic_id=clinic_id,
        branch_id=payload.branch_id,
        professional_id=payload.professional_id,
        rango=Range(payload.inicio, payload.fin),
        reglas=payload.reglas,
    )
    db.add(block)
    await db.commit()
    await db.refresh(block)
    return await _bloque_out(db, block)


async def _own_block(db: AsyncSession, clinic_id: uuid.UUID, block_id: uuid.UUID) -> AvailabilityBlock:
    block = await db.get(AvailabilityBlock, block_id)
    if block is None or block.deleted_at is not None or block.clinic_id != clinic_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bloque no encontrado")
    return block


@router.patch("/agendas/{block_id}", response_model=BloqueOut)
async def editar_bloque(
    block_id: uuid.UUID,
    payload: BloqueUpdate,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CLINIC_AGENDAS, Action.EDITAR)),
) -> BloqueOut:
    clinic_id = empresa_clinic_id(ctx)
    block = await _own_block(db, clinic_id, block_id)
    inicio = payload.inicio or block.rango.lower
    fin = payload.fin or block.rango.upper
    if fin <= inicio:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El fin del bloque debe ser posterior al inicio")
    block.rango = Range(inicio, fin)
    if payload.reglas is not None:
        block.reglas = payload.reglas
    await db.commit()
    await db.refresh(block)
    return await _bloque_out(db, block)


@router.delete("/agendas/{block_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_bloque(
    block_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CLINIC_AGENDAS, Action.ELIMINAR)),
) -> None:
    clinic_id = empresa_clinic_id(ctx)
    block = await _own_block(db, clinic_id, block_id)
    await db.delete(block)  # soft delete via listener
    await db.commit()


# ─────────────────────────── catálogo ───────────────────────────
async def _servicio_out(db: AsyncSession, item: CatalogItem) -> ServicioAdminOut:
    specialty = await db.get(Specialty, item.specialty_id) if item.specialty_id else None
    return ServicioAdminOut(
        id=item.id, nombre=item.nombre, precio=float(item.precio), duracion_min=item.duracion_min, activo=item.activo, specialty_nombre=specialty.nombre if specialty else None
    )


@router.get("/servicios", response_model=list[ServicioAdminOut])
async def list_servicios(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CATALOGO_PRECIOS, Action.VER)),
) -> list[ServicioAdminOut]:
    clinic_id = empresa_clinic_id(ctx)
    rows = (
        await db.execute(
            select(CatalogItem).where(CatalogItem.clinic_id == clinic_id, CatalogItem.tipo == "servicio", CatalogItem.deleted_at.is_(None)).order_by(CatalogItem.nombre)
        )
    ).scalars().all()
    return [await _servicio_out(db, i) for i in rows]


@router.post("/servicios", response_model=ServicioAdminOut, status_code=status.HTTP_201_CREATED)
async def crear_servicio(
    payload: ServicioIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CATALOGO_PRECIOS, Action.CREAR)),
) -> ServicioAdminOut:
    clinic_id = empresa_clinic_id(ctx)
    item = CatalogItem(clinic_id=clinic_id, specialty_id=payload.specialty_id, tipo="servicio", nombre=payload.nombre, precio=payload.precio, duracion_min=payload.duracion_min)
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return await _servicio_out(db, item)


async def _own_servicio(db: AsyncSession, clinic_id: uuid.UUID, item_id: uuid.UUID) -> CatalogItem:
    item = await db.get(CatalogItem, item_id)
    if item is None or item.deleted_at is not None or item.clinic_id != clinic_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Servicio no encontrado")
    return item


@router.patch("/servicios/{item_id}", response_model=ServicioAdminOut)
async def editar_servicio(
    item_id: uuid.UUID,
    payload: ServicioUpdate,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CATALOGO_PRECIOS, Action.EDITAR)),
) -> ServicioAdminOut:
    clinic_id = empresa_clinic_id(ctx)
    item = await _own_servicio(db, clinic_id, item_id)
    data = payload.model_dump(exclude_none=True)
    for k, v in data.items():
        setattr(item, k, v)
    await db.commit()
    await db.refresh(item)
    return await _servicio_out(db, item)


@router.delete("/servicios/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_servicio(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CATALOGO_PRECIOS, Action.ELIMINAR)),
) -> None:
    """Baja lógica (Spec Empresa §3) — el listener global convierte el delete
    en deleted_at, así el servicio deja de aparecer sin perder el histórico
    de citas que lo referencian."""
    clinic_id = empresa_clinic_id(ctx)
    item = await _own_servicio(db, clinic_id, item_id)
    await db.delete(item)
    await db.commit()


# ─────────────────────────── promociones ───────────────────────────
def _promo_out(p: Promotion) -> PromocionOut:
    return PromocionOut(id=p.id, nombre=p.nombre, descuento=p.descuento, vigencia_inicio=p.vigencia_inicio, vigencia_fin=p.vigencia_fin, segmento=p.segmento, estado=p.estado)


@router.get("/promociones", response_model=list[PromocionOut])
async def list_promos(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.PROMOCIONES, Action.VER)),
) -> list[PromocionOut]:
    clinic_id = empresa_clinic_id(ctx)
    rows = (await db.execute(select(Promotion).where(Promotion.clinic_id == clinic_id, Promotion.deleted_at.is_(None)).order_by(Promotion.created_at.desc()))).scalars().all()
    return [_promo_out(p) for p in rows]


@router.post("/promociones", response_model=PromocionOut, status_code=status.HTTP_201_CREATED)
async def crear_promo(
    payload: PromocionIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.PROMOCIONES, Action.CREAR)),
) -> PromocionOut:
    clinic_id = empresa_clinic_id(ctx)
    p = Promotion(clinic_id=clinic_id, **payload.model_dump())
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return _promo_out(p)


async def _own_promo(db: AsyncSession, clinic_id: uuid.UUID, promo_id: uuid.UUID) -> Promotion:
    p = await db.get(Promotion, promo_id)
    if p is None or p.deleted_at is not None or p.clinic_id != clinic_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Promoción no encontrada")
    return p


@router.patch("/promociones/{promo_id}", response_model=PromocionOut)
async def editar_promo(
    promo_id: uuid.UUID,
    payload: PromocionUpdate,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.PROMOCIONES, Action.EDITAR)),
) -> PromocionOut:
    clinic_id = empresa_clinic_id(ctx)
    p = await _own_promo(db, clinic_id, promo_id)
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(p, k, v)
    await db.commit()
    await db.refresh(p)
    return _promo_out(p)


@router.delete("/promociones/{promo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_promo(
    promo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.PROMOCIONES, Action.ELIMINAR)),
) -> None:
    clinic_id = empresa_clinic_id(ctx)
    p = await _own_promo(db, clinic_id, promo_id)
    await db.delete(p)
    await db.commit()


# ─────────────────────────── info empresa ───────────────────────────
@router.get("/info", response_model=InfoEmpresaOut)
async def get_info(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.INFO_EMPRESA, Action.VER)),
) -> InfoEmpresaOut:
    clinic_id = empresa_clinic_id(ctx)
    clinic = await db.get(Clinic, clinic_id)
    branches = (await db.execute(select(Branch).where(Branch.clinic_id == clinic_id, Branch.deleted_at.is_(None)))).scalars().all()
    return InfoEmpresaOut(
        clinic_id=clinic.id,
        razon_social=clinic.razon_social,
        responsable_sanitario=clinic.responsable_sanitario,
        pais=clinic.pais,
        sucursales=[BranchOut(id=b.id, nombre=b.nombre) for b in branches],
    )


@router.patch("/info", response_model=InfoEmpresaOut)
async def editar_info(
    payload: InfoEmpresaUpdate,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.INFO_EMPRESA, Action.EDITAR)),
) -> InfoEmpresaOut:
    clinic_id = empresa_clinic_id(ctx)
    clinic = await db.get(Clinic, clinic_id)
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(clinic, k, v)
    await db.commit()
    return await get_info(db, ctx)


# ─────────────────────────── funcionarios B2B ───────────────────────────
async def _company_for_clinic(db: AsyncSession, clinic_id: uuid.UUID) -> Company:
    company = (await db.execute(select(Company).where(Company.clinic_id == clinic_id, Company.deleted_at.is_(None)))).scalars().first()
    if company is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Esta cuenta no opera como empresa contratante B2B")
    return company


@router.get("/funcionarios", response_model=list[FuncionarioOut])
async def list_funcionarios(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.FUNCIONARIOS_B2B, Action.VER)),
) -> list[FuncionarioOut]:
    clinic_id = empresa_clinic_id(ctx)
    company = await _company_for_clinic(db, clinic_id)
    rows = (
        await db.execute(
            select(CompanyEmployee, User.nombre, User.email)
            .join(Patient, Patient.id == CompanyEmployee.patient_id)
            .join(User, User.id == Patient.user_id)
            .where(CompanyEmployee.company_id == company.id, CompanyEmployee.deleted_at.is_(None))
        )
    ).all()
    return [FuncionarioOut(id=ce.id, nombre=nombre, correo=email, estado=ce.estado) for ce, nombre, email in rows]


@router.post("/funcionarios", response_model=FuncionarioOut, status_code=status.HTTP_201_CREATED)
async def alta_funcionario(
    payload: FuncionarioIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.FUNCIONARIOS_B2B, Action.CREAR)),
) -> FuncionarioOut:
    clinic_id = empresa_clinic_id(ctx)
    company = await _company_for_clinic(db, clinic_id)
    user = (await db.execute(select(User).where(User.email == payload.correo))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No existe un paciente con ese correo")
    patient = (await db.execute(select(Patient).where(Patient.user_id == user.id, Patient.clinic_id == clinic_id))).scalar_one_or_none()
    if patient is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El paciente no pertenece a esta clínica")
    existing = (await db.execute(select(CompanyEmployee).where(CompanyEmployee.company_id == company.id, CompanyEmployee.patient_id == patient.id, CompanyEmployee.deleted_at.is_(None)))).scalar_one_or_none()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ese paciente ya es funcionario")
    ce = CompanyEmployee(clinic_id=clinic_id, company_id=company.id, patient_id=patient.id, plan_id=payload.plan_id, estado="activo")
    db.add(ce)
    await db.commit()
    await db.refresh(ce)
    return FuncionarioOut(id=ce.id, nombre=user.nombre, correo=user.email, estado=ce.estado)


@router.delete("/funcionarios/{ce_id}", status_code=status.HTTP_204_NO_CONTENT)
async def baja_funcionario(
    ce_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.FUNCIONARIOS_B2B, Action.ELIMINAR)),
) -> None:
    clinic_id = empresa_clinic_id(ctx)
    ce = await db.get(CompanyEmployee, ce_id)
    if ce is None or ce.deleted_at is not None or ce.clinic_id != clinic_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Funcionario no encontrado")
    ce.estado = "baja"  # baja lógica: conserva el registro, marca el estado
    await db.commit()
