import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.dialects.postgresql import Range
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.database import get_db
from app.models.catalog import CatalogItem, Promotion, Specialty
from app.models.finance import CashPayment, Company, CompanyEmployee, LedgerEntry, PaymentSplit
from app.models.identity import Role, RoleAssignment, User
from app.models.patient import Patient
from app.models.scheduling import Appointment, AvailabilityBlock
from app.models.tenant import Branch, Clinic
from app.rbac.deps import require
from app.rbac.permissions import Action, Resource, RoleCode
from app.schemas.empresa import (
    AgendaDiaOut,
    BloqueIn,
    BloqueOut,
    BloqueUpdate,
    BranchOut,
    CambiarEstadoIn,
    CitaAgendaOut,
    DesempenoGrupo,
    DesempenoOut,
    DesempenoProfesional,
    PacienteEstadoIn,
    PacienteListaOut,
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
from app.services.crm import month_bounds
from app.services.medico import audit
from app.tenancy.context import TenantContext

router = APIRouter(prefix="/empresa", tags=["empresa"])

# Estados de cita enriquecidos (Tanda 1). El estado es un String libre en el
# modelo, así que ampliar el flujo no requiere migración. 'completada' NO se
# fija desde aquí: nace del cierre del médico, que además asienta el ingreso.
ESTADOS_CITA = ["confirmada", "en_sala_espera", "en_atencion", "completada", "no_show", "cancelada"]
ESTADOS_EDITABLES_EMPRESA = {"confirmada", "en_sala_espera", "en_atencion", "no_show", "cancelada"}


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


# ────────────────── agenda del día de la clínica (gerencia) ──────────────────
@router.get("/agenda", response_model=AgendaDiaOut)
async def agenda_dia(
    fecha: date | None = None,
    professional_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CLINIC_AGENDAS, Action.VER)),
) -> AgendaDiaOut:
    """Agenda del día de TODA la clínica (todos los profesionales) para gerencia:
    paciente, profesional, estado y situación de pago por cita. La 'situación'
    se calcula del ledger inmutable (¿hay 'ingreso' asentado para esta cita?),
    nunca se guarda — mismo principio que el CRM."""
    clinic_id = empresa_clinic_id(ctx)
    day = fecha or datetime.now(timezone.utc).date()

    PacienteUser = aliased(User)
    Prof = aliased(User)
    q = (
        select(Appointment, PacienteUser.nombre, Prof.nombre, CatalogItem.nombre, CatalogItem.precio)
        .join(Patient, Patient.id == Appointment.patient_id)
        .join(PacienteUser, PacienteUser.id == Patient.user_id)
        .join(Prof, Prof.id == Appointment.professional_id)
        .outerjoin(CatalogItem, CatalogItem.id == Appointment.service_id)
        .where(
            Appointment.clinic_id == clinic_id,
            Appointment.deleted_at.is_(None),
            func.date(func.lower(Appointment.slot)) == day,
        )
    )
    if professional_id:
        q = q.where(Appointment.professional_id == professional_id)
    rows = (await db.execute(q.order_by(func.lower(Appointment.slot)))).all()

    # Situación de pago: ingresos ya asentados por cita (ref = appointment:<id>).
    appt_ids = [appt.id for appt, *_ in rows]
    facturado: dict[str, float] = {}
    if appt_ids:
        refs = [f"appointment:{i}" for i in appt_ids]
        led = (
            await db.execute(
                select(LedgerEntry.ref, func.coalesce(func.sum(LedgerEntry.monto), 0))
                .where(LedgerEntry.clinic_id == clinic_id, LedgerEntry.tipo == "ingreso", LedgerEntry.ref.in_(refs))
                .group_by(LedgerEntry.ref)
            )
        ).all()
        facturado = {ref.split(":", 1)[1]: float(m) for ref, m in led}

    # Situación de pago recibido: citas con al menos un pago de caja (Tanda 2).
    pagadas: set[uuid.UUID] = set()
    if appt_ids:
        pag_rows = (
            await db.execute(
                select(CashPayment.appointment_id)
                .where(
                    CashPayment.clinic_id == clinic_id,
                    CashPayment.tipo == "pago",
                    CashPayment.deleted_at.is_(None),
                    CashPayment.appointment_id.in_(appt_ids),
                )
                .distinct()
            )
        ).scalars().all()
        pagadas = set(pag_rows)

    citas: list[CitaAgendaOut] = []
    por_estado: dict[str, int] = {}
    for appt, pac_nombre, prof_nombre, serv_nombre, serv_precio in rows:
        por_estado[appt.estado] = por_estado.get(appt.estado, 0) + 1
        fact = str(appt.id) in facturado
        citas.append(
            CitaAgendaOut(
                id=appt.id,
                inicio=appt.slot.lower,
                fin=appt.slot.upper,
                paciente_id=appt.patient_id,
                paciente_nombre=pac_nombre,
                profesional_id=appt.professional_id,
                profesional_nombre=prof_nombre,
                servicio_nombre=serv_nombre,
                estado=appt.estado,
                monto=facturado[str(appt.id)] if fact else (float(serv_precio) if serv_precio is not None else None),
                facturado=fact,
                pagado=appt.id in pagadas,
            )
        )
    return AgendaDiaOut(fecha=day, total=len(citas), por_estado=por_estado, citas=citas)


@router.patch("/citas/{appointment_id}/estado", response_model=CitaAgendaOut)
async def cambiar_estado_cita(
    appointment_id: uuid.UUID,
    payload: CambiarEstadoIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CLINIC_AGENDAS, Action.EDITAR)),
) -> CitaAgendaOut:
    """Recepción/gerencia mueve el estado operativo de la cita (llegó, en sala,
    en atención, faltó, anuló). 'completada' se reserva al cierre del médico —
    porque ese paso asienta el ingreso en el ledger."""
    clinic_id = empresa_clinic_id(ctx)
    nuevo = payload.estado
    if nuevo not in ESTADOS_EDITABLES_EMPRESA:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Estado inválido. Para 'completada' usa el cierre de atención del médico." if nuevo == "completada" else f"Estado inválido: {nuevo}",
        )
    appt = await db.get(Appointment, appointment_id)
    if appt is None or appt.deleted_at is not None or appt.clinic_id != clinic_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cita no encontrada")
    if appt.estado == "completada":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "La cita ya fue cerrada por el médico")
    antes = appt.estado
    appt.estado = nuevo
    audit(db, ctx, clinic_id=clinic_id, accion="cambiar_estado_cita", recurso=f"appointment:{appt.id}", antes={"estado": antes}, despues={"estado": nuevo})
    await db.commit()
    await db.refresh(appt)

    pac = await db.get(Patient, appt.patient_id)
    pac_user = await db.get(User, pac.user_id) if pac else None
    prof = await db.get(User, appt.professional_id)
    service = await db.get(CatalogItem, appt.service_id) if appt.service_id else None
    return CitaAgendaOut(
        id=appt.id,
        inicio=appt.slot.lower,
        fin=appt.slot.upper,
        paciente_id=appt.patient_id,
        paciente_nombre=pac_user.nombre if pac_user else "",
        profesional_id=appt.professional_id,
        profesional_nombre=prof.nombre if prof else "",
        servicio_nombre=service.nombre if service else None,
        estado=appt.estado,
        monto=float(service.precio) if service else None,
        facturado=False,
    )


# ────────────────── pacientes (listado con deudas) — Tanda 4 ──────────────────
@router.get("/pacientes", response_model=list[PacienteListaOut])
async def listar_pacientes(
    activo: bool | None = None,
    q: str | None = None,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CLINIC_AGENDAS, Action.VER)),
) -> list[PacienteListaOut]:
    """Pacientes de la clínica con nº de tratamientos y DEUDA (facturado − pagado),
    calculada del ledger vs. los cobros de caja — nunca almacenada."""
    clinic_id = empresa_clinic_id(ctx)

    query = (
        select(Patient, User.nombre)
        .join(User, User.id == Patient.user_id)
        .where(Patient.clinic_id == clinic_id, Patient.deleted_at.is_(None))
    )
    if activo is not None:
        query = query.where(Patient.activo.is_(activo))
    if q:
        query = query.where(User.nombre.ilike(f"%{q}%"))
    rows = (await db.execute(query.order_by(User.nombre))).all()

    # nº de tratamientos = atenciones completadas
    trat = dict(
        (await db.execute(
            select(Appointment.patient_id, func.count(Appointment.id))
            .where(Appointment.clinic_id == clinic_id, Appointment.estado == "completada", Appointment.deleted_at.is_(None))
            .group_by(Appointment.patient_id)
        )).all()
    )
    # facturado por paciente (ingresos ligados a sus citas)
    facturado = dict(
        (await db.execute(
            select(Appointment.patient_id, func.coalesce(func.sum(LedgerEntry.monto), 0))
            .join(Appointment, func.cast(func.split_part(LedgerEntry.ref, ":", 2), PgUUID) == Appointment.id)
            .where(LedgerEntry.clinic_id == clinic_id, LedgerEntry.tipo == "ingreso", LedgerEntry.ref.like("appointment:%"))
            .group_by(Appointment.patient_id)
        )).all()
    )
    # pagado por paciente (cobros de caja ligados a sus citas)
    pagado = dict(
        (await db.execute(
            select(Appointment.patient_id, func.coalesce(func.sum(CashPayment.monto), 0))
            .join(Appointment, Appointment.id == CashPayment.appointment_id)
            .where(CashPayment.clinic_id == clinic_id, CashPayment.tipo == "pago", CashPayment.deleted_at.is_(None))
            .group_by(Appointment.patient_id)
        )).all()
    )

    out: list[PacienteListaOut] = []
    for p, nombre in rows:
        deuda = float(facturado.get(p.id, 0)) - float(pagado.get(p.id, 0))
        out.append(PacienteListaOut(id=p.id, nombre=nombre, rut=p.rut, activo=p.activo, n_tratamientos=int(trat.get(p.id, 0)), deuda=round(max(deuda, 0.0), 2)))
    return out


@router.patch("/pacientes/{patient_id}/estado", response_model=PacienteListaOut)
async def cambiar_estado_paciente(
    patient_id: uuid.UUID,
    payload: PacienteEstadoIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CLINIC_AGENDAS, Action.EDITAR)),
) -> PacienteListaOut:
    clinic_id = empresa_clinic_id(ctx)
    p = await db.get(Patient, patient_id)
    if p is None or p.deleted_at is not None or p.clinic_id != clinic_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Paciente no encontrado")
    p.activo = payload.activo
    audit(db, ctx, clinic_id=clinic_id, accion="habilitar_paciente" if payload.activo else "deshabilitar_paciente", recurso=f"patient:{patient_id}")
    await db.commit()
    user = await db.get(User, p.user_id)
    return PacienteListaOut(id=p.id, nombre=user.nombre if user else "", rut=p.rut, activo=p.activo, n_tratamientos=0, deuda=0.0)


# ────────────────── panel de desempeño ampliado — Tanda 4 ──────────────────
@router.get("/desempeno", response_model=DesempenoOut)
async def desempeno(
    period: str | None = None,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CRM_KPIS_CLINICA, Action.VER)),
) -> DesempenoOut:
    """Panel de desempeño: ventas y recaudación del mes, por profesional (con
    monto a pagar según su split) y por grupo de servicio (con ticket medio).
    Todo calculado del ledger + agenda; nada se almacena."""
    clinic_id = empresa_clinic_id(ctx)
    start, end = month_bounds(period)

    ventas = float((await db.execute(
        select(func.coalesce(func.sum(LedgerEntry.monto), 0)).where(
            LedgerEntry.clinic_id == clinic_id, LedgerEntry.tipo == "ingreso",
            LedgerEntry.ref.like("appointment:%"),
            func.date(LedgerEntry.created_at) >= start, func.date(LedgerEntry.created_at) < end,
        )
    )).scalar_one())
    recaudado = float((await db.execute(
        select(func.coalesce(func.sum(CashPayment.monto), 0)).where(
            CashPayment.clinic_id == clinic_id, CashPayment.tipo == "pago", CashPayment.deleted_at.is_(None),
            func.date(CashPayment.created_at) >= start, func.date(CashPayment.created_at) < end,
        )
    )).scalar_one())

    # por profesional: desde los splits del período (una ingreso → un split del tratante)
    prof_rows = (await db.execute(
        select(User.nombre, func.count(PaymentSplit.id), func.coalesce(func.sum(LedgerEntry.monto), 0), func.coalesce(func.sum(PaymentSplit.monto), 0))
        .join(LedgerEntry, LedgerEntry.id == PaymentSplit.ledger_entry_id)
        .join(User, User.id == PaymentSplit.beneficiario_id)
        .where(
            PaymentSplit.clinic_id == clinic_id,
            func.date(LedgerEntry.created_at) >= start, func.date(LedgerEntry.created_at) < end,
        )
        .group_by(User.nombre)
        .order_by(func.coalesce(func.sum(LedgerEntry.monto), 0).desc())
    )).all()
    por_profesional = [
        DesempenoProfesional(
            nombre=n, atenciones=int(c), ventas=float(v), a_pagar=float(ap),
            pct=round(float(ap) / float(v) * 100, 1) if float(v) else None,
        )
        for n, c, v, ap in prof_rows
    ]

    # por grupo de servicio: atenciones completadas del período por especialidad
    grupo_rows = (await db.execute(
        select(Specialty.nombre, func.count(Appointment.id), func.coalesce(func.sum(CatalogItem.precio), 0))
        .join(CatalogItem, CatalogItem.id == Appointment.service_id)
        .join(Specialty, Specialty.id == CatalogItem.specialty_id, isouter=True)
        .where(
            Appointment.clinic_id == clinic_id, Appointment.estado == "completada", Appointment.deleted_at.is_(None),
            func.date(func.lower(Appointment.slot)) >= start, func.date(func.lower(Appointment.slot)) < end,
        )
        .group_by(Specialty.nombre)
        .order_by(func.coalesce(func.sum(CatalogItem.precio), 0).desc())
    )).all()
    por_grupo = [
        DesempenoGrupo(grupo=g or "Sin especialidad", cantidad=int(c), monto=float(m), ticket_medio=round(float(m) / int(c), 2) if int(c) else 0.0)
        for g, c, m in grupo_rows
    ]

    atenciones = sum(p.atenciones for p in por_profesional)
    ticket = round(ventas / atenciones, 2) if atenciones else 0.0
    return DesempenoOut(
        periodo=start.strftime("%Y-%m"), ventas=ventas, recaudado=recaudado,
        atenciones=atenciones, ticket_medio=ticket, por_profesional=por_profesional, por_grupo=por_grupo,
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
