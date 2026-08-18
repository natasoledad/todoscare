import uuid
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import cast, func, select
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.dialects.postgresql import Range
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.database import get_db
from app.models.catalog import CatalogItem, MotivoAtencion, Promotion, Specialty
from app.models.facility import Room
from app.models.professional import ProfessionalProfile
from app.models.finance import CashPayment, Company, CompanyEmployee, LedgerEntry, PaymentSplit
from app.models.identity import Role, RoleAssignment, User
from app.models.patient import Patient
from app.models.scheduling import Appointment, AvailabilityBlock, ScheduleException, WeeklyScheduleTemplate
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
    EspecialidadIn,
    EspecialidadOut,
    EspecialidadUpdate,
    BloqueoIn,
    BloqueoOut,
    EstadoProfesionalIn,
    FinalizarLiquidacionIn,
    FinalizarLiquidacionOut,
    GenerarBloquesIn,
    GenerarBloquesOut,
    LiquidacionDetalleOut,
    LiquidacionProfOut,
    HorarioIn,
    HorarioOut,
    HorarioUpdate,
    InfoEmpresaOut,
    InfoEmpresaUpdate,
    KpisOut,
    MotivoIn,
    MotivoOut,
    MotivoUpdate,
    PerfilProfesionalUpdate,
    ProfesionalOut,
    PromocionIn,
    RemanejoIn,
    RemanejoOut,
    PromocionOut,
    PromocionUpdate,
    RecintoIn,
    RecintoOut,
    RecintoUpdate,
    ServicioAdminOut,
    ServicioIn,
    ServicioUpdate,
    ServicioVendido,
)
from app.services.crm import month_bounds
from app.services.medico import audit
from app.services.scheduling import overlaps_exception
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
    prof = aliased(ProfessionalProfile)
    rows = (
        await db.execute(
            select(User.id, User.nombre, prof.specialty_id, prof.duracion_min, prof.modalidad, prof.activo, prof.comision_pct, Specialty.nombre, Specialty.tipo)
            .join(RoleAssignment, RoleAssignment.user_id == User.id)
            .join(Role, Role.id == RoleAssignment.role_id)
            .outerjoin(prof, (prof.user_id == User.id) & (prof.clinic_id == clinic_id) & (prof.deleted_at.is_(None)))
            .outerjoin(Specialty, Specialty.id == prof.specialty_id)
            .where(Role.code == RoleCode.MEDICO.value, RoleAssignment.clinic_id == clinic_id, RoleAssignment.deleted_at.is_(None))
            .distinct()
            .order_by(User.nombre)
        )
    ).all()
    return [
        ProfesionalOut(
            id=i, nombre=n, specialty_id=sid, specialty_nombre=snom, tipo_especialidad=stipo,
            duracion_min=dur, modalidad=mod or "presencial",
            comision_pct=float(cpct) if cpct is not None else None,
            activo=act if act is not None else True,
        )
        for i, n, sid, dur, mod, act, cpct, snom, stipo in rows
    ]


@router.get("/sucursales", response_model=list[BranchOut])
async def sucursales(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CLINIC_AGENDAS, Action.VER)),
) -> list[BranchOut]:
    clinic_id = empresa_clinic_id(ctx)
    rows = (await db.execute(select(Branch).where(Branch.clinic_id == clinic_id, Branch.deleted_at.is_(None)))).scalars().all()
    return [BranchOut(id=b.id, nombre=b.nombre) for b in rows]


# ─────────────────────────── especialidades (54) ───────────────────────────
# NOTA de tenancy: `specialties` es una taxonomía global (compartida entre
# clínicas), no tenant-scoped. Por eso la clínica crea/edita el vocabulario
# global y `activo` deshabilita la especialidad del catálogo (54.4) — igual
# que las pestañas Habilitadas/Deshabilitadas de Medilink. La habilitación
# por-clínica (que una sede use un subconjunto) es un refinamiento futuro; la
# asignación real al profesional ya es tenant-scoped vía ProfessionalProfile.
def _esp_out(s: Specialty) -> EspecialidadOut:
    return EspecialidadOut(id=s.id, nombre=s.nombre, tipo=s.tipo, icono=s.icono, activo=s.activo)


@router.get("/especialidades", response_model=list[EspecialidadOut])
async def list_especialidades(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CATALOGO_PRECIOS, Action.VER)),
) -> list[EspecialidadOut]:
    empresa_clinic_id(ctx)  # exige contexto de empresa
    rows = (await db.execute(select(Specialty).where(Specialty.deleted_at.is_(None)).order_by(Specialty.tipo, Specialty.nombre))).scalars().all()
    return [_esp_out(s) for s in rows]


@router.post("/especialidades", response_model=EspecialidadOut, status_code=status.HTTP_201_CREATED)
async def crear_especialidad(
    payload: EspecialidadIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CATALOGO_PRECIOS, Action.CREAR)),
) -> EspecialidadOut:
    empresa_clinic_id(ctx)
    s = Specialty(nombre=payload.nombre, tipo=payload.tipo, icono=payload.icono)
    db.add(s)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe una especialidad con ese nombre") from None
    await db.refresh(s)
    return _esp_out(s)


@router.patch("/especialidades/{esp_id}", response_model=EspecialidadOut)
async def editar_especialidad(
    esp_id: uuid.UUID,
    payload: EspecialidadUpdate,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CATALOGO_PRECIOS, Action.EDITAR)),
) -> EspecialidadOut:
    empresa_clinic_id(ctx)
    s = await db.get(Specialty, esp_id)
    if s is None or s.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Especialidad no encontrada")
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(s, k, v)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe una especialidad con ese nombre") from None
    await db.refresh(s)
    return _esp_out(s)


# ─────────────────────────── perfil del profesional (54.1b) ───────────────────────────
async def _ensure_profile(db: AsyncSession, clinic_id: uuid.UUID, user_id: uuid.UUID) -> ProfessionalProfile:
    """Valida que el usuario sea un profesional (rol médico) de la clínica y
    devuelve su perfil, creándolo vacío la primera vez (upsert)."""
    is_medico = (
        await db.execute(
            select(func.count())
            .select_from(RoleAssignment)
            .join(Role, Role.id == RoleAssignment.role_id)
            .where(
                RoleAssignment.user_id == user_id,
                RoleAssignment.clinic_id == clinic_id,
                RoleAssignment.deleted_at.is_(None),
                Role.code == RoleCode.MEDICO.value,
            )
        )
    ).scalar_one()
    if not is_medico:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profesional no encontrado en esta clínica")
    profile = (
        await db.execute(
            select(ProfessionalProfile).where(
                ProfessionalProfile.clinic_id == clinic_id,
                ProfessionalProfile.user_id == user_id,
                ProfessionalProfile.deleted_at.is_(None),
            )
        )
    ).scalars().first()
    if profile is None:
        profile = ProfessionalProfile(clinic_id=clinic_id, user_id=user_id)
        db.add(profile)
    return profile


async def _perfil_out(db: AsyncSession, user_id: uuid.UUID, profile: ProfessionalProfile) -> ProfesionalOut:
    user = await db.get(User, user_id)
    specialty = await db.get(Specialty, profile.specialty_id) if profile.specialty_id else None
    return ProfesionalOut(
        id=user_id, nombre=user.nombre if user else "",
        specialty_id=profile.specialty_id, specialty_nombre=specialty.nombre if specialty else None,
        tipo_especialidad=specialty.tipo if specialty else None,
        duracion_min=profile.duracion_min, modalidad=profile.modalidad,
        comision_pct=float(profile.comision_pct) if profile.comision_pct is not None else None,
        activo=profile.activo,
    )


@router.patch("/profesionales/{prof_id}/perfil", response_model=ProfesionalOut)
async def editar_perfil_profesional(
    prof_id: uuid.UUID,
    payload: PerfilProfesionalUpdate,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CLINIC_AGENDAS, Action.EDITAR)),
) -> ProfesionalOut:
    clinic_id = empresa_clinic_id(ctx)
    profile = await _ensure_profile(db, clinic_id, prof_id)
    data = payload.model_dump(exclude_unset=True)
    if data.get("specialty_id") is not None:
        specialty = await db.get(Specialty, data["specialty_id"])
        if specialty is None or specialty.deleted_at is not None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Especialidad no encontrada")
    for k, v in data.items():
        setattr(profile, k, v)
    await db.commit()
    await db.refresh(profile)
    return await _perfil_out(db, prof_id, profile)


# ─────────────────────────── estado del profesional (55) ───────────────────────────
async def _profile_activo(db: AsyncSession, clinic_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    """¿El profesional está habilitado en esta clínica? Sin perfil todavía se
    considera activo (comportamiento previo intacto); con perfil, manda su flag."""
    activo = (
        await db.execute(
            select(ProfessionalProfile.activo).where(
                ProfessionalProfile.clinic_id == clinic_id,
                ProfessionalProfile.user_id == user_id,
                ProfessionalProfile.deleted_at.is_(None),
            )
        )
    ).scalars().first()
    return True if activo is None else bool(activo)


@router.patch("/profesionales/{prof_id}/estado", response_model=ProfesionalOut)
async def cambiar_estado_profesional(
    prof_id: uuid.UUID,
    payload: EstadoProfesionalIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CLINIC_AGENDAS, Action.EDITAR)),
) -> ProfesionalOut:
    """Habilita/inhabilita al profesional en la clínica (55.1). Inhabilitado:
    no recibe nuevos bloques ni nuevas citas (55.3), y si es un profesional
    puro totalmente inhabilitado no puede loguear (55.2, en /auth/login). Su
    ficha y su historial se conservan para visualización administrativa (55.4)."""
    clinic_id = empresa_clinic_id(ctx)
    profile = await _ensure_profile(db, clinic_id, prof_id)
    profile.activo = payload.activo
    await db.commit()
    await db.refresh(profile)
    return await _perfil_out(db, prof_id, profile)


@router.post("/profesionales/{prof_id}/remanejo", response_model=RemanejoOut)
async def remanejar_pacientes(
    prof_id: uuid.UUID,
    payload: RemanejoIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CLINIC_AGENDAS, Action.EDITAR)),
) -> RemanejoOut:
    """Remaneja las citas FUTURAS del profesional (origen) a otro profesional
    (destino) — típicamente tras inhabilitarlo (55.5). Cada cita se mueve en su
    propia transacción: si choca con la agenda/recinto del destino (EXCLUDE de
    Postgres) se cuenta como conflicto y se deja en el origen para resolver a
    mano."""
    clinic_id = empresa_clinic_id(ctx)
    if payload.destino_id == prof_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El destino debe ser un profesional distinto")
    # destino debe ser médico ACTIVO de la clínica
    await _ensure_profile(db, clinic_id, payload.destino_id)  # valida que sea médico de la clínica
    if not await _profile_activo(db, clinic_id, payload.destino_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El profesional destino está inhabilitado")
    destino = await db.get(User, payload.destino_id)

    now = datetime.now(timezone.utc)
    ids = (
        await db.execute(
            select(Appointment.id).where(
                Appointment.clinic_id == clinic_id,
                Appointment.professional_id == prof_id,
                Appointment.deleted_at.is_(None),
                Appointment.estado.in_(["confirmada", "en_sala_espera", "en_atencion"]),
                func.lower(Appointment.slot) > now,
            )
        )
    ).scalars().all()

    movidas = 0
    conflictos = 0
    # Cada movimiento en su propia sesión: aísla el choque con el EXCLUDE gist.
    from app.core.database import AsyncSessionLocal
    for aid in ids:
        async with AsyncSessionLocal() as s:
            appt = await s.get(Appointment, aid)
            if appt is None:
                continue
            appt.professional_id = payload.destino_id
            try:
                await s.commit()
                movidas += 1
            except IntegrityError:
                await s.rollback()
                conflictos += 1

    return RemanejoOut(
        origen_id=prof_id, destino_id=payload.destino_id,
        destino_nombre=destino.nombre if destino else "", movidas=movidas, conflictos=conflictos,
    )


# ─────────────────────────── motivos de atención (54.9) ───────────────────────────
async def _motivo_out(db: AsyncSession, m: MotivoAtencion) -> MotivoOut:
    specialty = await db.get(Specialty, m.specialty_id) if m.specialty_id else None
    return MotivoOut(id=m.id, nombre=m.nombre, specialty_id=m.specialty_id, specialty_nombre=specialty.nombre if specialty else None, activo=m.activo)


@router.get("/motivos", response_model=list[MotivoOut])
async def list_motivos(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CLINIC_AGENDAS, Action.VER)),
) -> list[MotivoOut]:
    clinic_id = empresa_clinic_id(ctx)
    rows = (await db.execute(select(MotivoAtencion).where(MotivoAtencion.clinic_id == clinic_id, MotivoAtencion.deleted_at.is_(None)).order_by(MotivoAtencion.nombre))).scalars().all()
    return [await _motivo_out(db, m) for m in rows]


@router.post("/motivos", response_model=MotivoOut, status_code=status.HTTP_201_CREATED)
async def crear_motivo(
    payload: MotivoIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CLINIC_AGENDAS, Action.CREAR)),
) -> MotivoOut:
    clinic_id = empresa_clinic_id(ctx)
    m = MotivoAtencion(clinic_id=clinic_id, nombre=payload.nombre, specialty_id=payload.specialty_id)
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return await _motivo_out(db, m)


async def _own_motivo(db: AsyncSession, clinic_id: uuid.UUID, motivo_id: uuid.UUID) -> MotivoAtencion:
    m = await db.get(MotivoAtencion, motivo_id)
    if m is None or m.deleted_at is not None or m.clinic_id != clinic_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Motivo no encontrado")
    return m


@router.patch("/motivos/{motivo_id}", response_model=MotivoOut)
async def editar_motivo(
    motivo_id: uuid.UUID,
    payload: MotivoUpdate,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CLINIC_AGENDAS, Action.EDITAR)),
) -> MotivoOut:
    clinic_id = empresa_clinic_id(ctx)
    m = await _own_motivo(db, clinic_id, motivo_id)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(m, k, v)
    await db.commit()
    await db.refresh(m)
    return await _motivo_out(db, m)


@router.delete("/motivos/{motivo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_motivo(
    motivo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CLINIC_AGENDAS, Action.ELIMINAR)),
) -> None:
    clinic_id = empresa_clinic_id(ctx)
    m = await _own_motivo(db, clinic_id, motivo_id)
    await db.delete(m)  # baja lógica vía listener
    await db.commit()


# ─────────────────────────── liquidación de profesionales (58) ───────────────────────────
# Se apoya en los PaymentSplit ya existentes (una atención que comisiona -> un
# split al profesional). "Activas" = splits pendientes; "finalizar" = marcar
# conciliado y asentar el egreso, igual que la conciliación del CRM.
def _split_estado(estado: str) -> str:
    return "conciliado" if estado == "finalizadas" else "pendiente"


@router.get("/liquidaciones", response_model=list[LiquidacionProfOut])
async def list_liquidaciones(
    period: str | None = None,
    estado: str = "activas",
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.LIQUIDACION_PROFESIONALES, Action.VER)),
) -> list[LiquidacionProfOut]:
    clinic_id = empresa_clinic_id(ctx)
    start, end = month_bounds(period)
    rows = (
        await db.execute(
            select(PaymentSplit.beneficiario_id, User.nombre, PaymentSplit.monto, PaymentSplit.regla)
            .join(User, User.id == PaymentSplit.beneficiario_id)
            .where(
                PaymentSplit.clinic_id == clinic_id,
                PaymentSplit.deleted_at.is_(None),
                PaymentSplit.estado == _split_estado(estado),
                func.date(PaymentSplit.created_at) >= start,
                func.date(PaymentSplit.created_at) < end,
            )
        )
    ).all()
    agg: dict[uuid.UUID, dict] = {}
    for pid, nombre, monto, regla in rows:
        a = agg.setdefault(pid, {"nombre": nombre, "cantidad": 0, "realizado": 0.0, "a_pagar": 0.0})
        a["cantidad"] += 1
        a["a_pagar"] += float(monto)
        a["realizado"] += float((regla or {}).get("base", 0) or 0)
    return [
        LiquidacionProfOut(professional_id=pid, nombre=a["nombre"], cantidad=a["cantidad"], realizado=round(a["realizado"], 2), a_pagar=round(a["a_pagar"], 2))
        for pid, a in sorted(agg.items(), key=lambda kv: kv[1]["a_pagar"], reverse=True)
    ]


@router.get("/liquidaciones/{professional_id}/detalle", response_model=list[LiquidacionDetalleOut])
async def liquidacion_detalle(
    professional_id: uuid.UUID,
    period: str | None = None,
    estado: str = "activas",
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.LIQUIDACION_PROFESIONALES, Action.VER)),
) -> list[LiquidacionDetalleOut]:
    clinic_id = empresa_clinic_id(ctx)
    start, end = month_bounds(period)
    appt_id = cast(func.split_part(LedgerEntry.ref, ":", 2), PgUUID(as_uuid=True))
    pat_user = aliased(User)
    rows = (
        await db.execute(
            select(PaymentSplit, CatalogItem.nombre, pat_user.nombre)
            .join(LedgerEntry, LedgerEntry.id == PaymentSplit.ledger_entry_id)
            .outerjoin(Appointment, appt_id == Appointment.id)
            .outerjoin(CatalogItem, CatalogItem.id == Appointment.service_id)
            .outerjoin(Patient, Patient.id == Appointment.patient_id)
            .outerjoin(pat_user, pat_user.id == Patient.user_id)
            .where(
                PaymentSplit.clinic_id == clinic_id,
                PaymentSplit.beneficiario_id == professional_id,
                PaymentSplit.deleted_at.is_(None),
                PaymentSplit.estado == _split_estado(estado),
                func.date(PaymentSplit.created_at) >= start,
                func.date(PaymentSplit.created_at) < end,
                LedgerEntry.ref.like("appointment:%"),
            )
            .order_by(PaymentSplit.created_at.desc())
        )
    ).all()
    return [
        LiquidacionDetalleOut(
            split_id=s.id, fecha=s.created_at, prestacion=prestacion, paciente=paciente,
            base=float((s.regla or {}).get("base", 0) or 0), monto=float(s.monto), estado=s.estado,
        )
        for s, prestacion, paciente in rows
    ]


@router.post("/liquidaciones/{professional_id}/finalizar", response_model=FinalizarLiquidacionOut)
async def finalizar_liquidacion(
    professional_id: uuid.UUID,
    payload: FinalizarLiquidacionIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.LIQUIDACION_PROFESIONALES, Action.EDITAR)),
) -> FinalizarLiquidacionOut:
    """Finaliza (paga) la liquidación: marca conciliados los splits pendientes
    del profesional —hasta la fecha `hasta` si se indica— y asienta el egreso
    inmutable en el ledger, igual que la conciliación del CRM (58.6/58.10)."""
    clinic_id = empresa_clinic_id(ctx)
    q = select(PaymentSplit).where(
        PaymentSplit.clinic_id == clinic_id,
        PaymentSplit.beneficiario_id == professional_id,
        PaymentSplit.deleted_at.is_(None),
        PaymentSplit.estado == "pendiente",
    )
    if payload.hasta is not None:
        q = q.where(func.date(PaymentSplit.created_at) <= payload.hasta)
    splits = (await db.execute(q)).scalars().all()
    now = datetime.now(timezone.utc)
    total = 0.0
    for s in splits:
        s.estado = "conciliado"
        s.conciliado_at = now
        db.add(LedgerEntry(clinic_id=clinic_id, tipo="liquidacion_pagada", monto=s.monto, ref=f"split:{s.id}"))
        total += float(s.monto)
    await db.commit()
    prof = await db.get(User, professional_id)
    return FinalizarLiquidacionOut(professional_id=professional_id, profesional_nombre=prof.nombre if prof else "", finalizadas=len(splits), monto=round(total, 2))


# ─────────────────────────── horario semanal recurrente (52) ───────────────────────────
# La plantilla guarda horas de pared locales; al materializar los bloques se
# convierten a UTC con la zona horaria de la clínica (según su país).
_TZ_BY_PAIS = {"CL": "America/Santiago", "BR": "America/Sao_Paulo", "MX": "America/Mexico_City"}


def _clinic_tz(pais: str | None) -> ZoneInfo:
    return ZoneInfo(_TZ_BY_PAIS.get((pais or "").upper(), "UTC"))


async def _assert_medico_clinica(db: AsyncSession, clinic_id: uuid.UUID, user_id: uuid.UUID) -> None:
    ok = (
        await db.execute(
            select(func.count()).select_from(RoleAssignment).join(Role, Role.id == RoleAssignment.role_id).where(
                RoleAssignment.user_id == user_id,
                RoleAssignment.clinic_id == clinic_id,
                RoleAssignment.deleted_at.is_(None),
                Role.code == RoleCode.MEDICO.value,
            )
        )
    ).scalar_one()
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profesional no encontrado en esta clínica")


async def _horario_out(db: AsyncSession, t: WeeklyScheduleTemplate) -> HorarioOut:
    prof = await db.get(User, t.professional_id)
    branch = await db.get(Branch, t.branch_id)
    room = await db.get(Room, t.room_id) if t.room_id else None
    return HorarioOut(
        id=t.id, professional_id=t.professional_id, professional_nombre=prof.nombre if prof else "",
        branch_id=t.branch_id, branch_nombre=branch.nombre if branch else "",
        room_id=t.room_id, room_nombre=room.nombre if room else None,
        dia_semana=t.dia_semana, hora_inicio=t.hora_inicio, hora_fin=t.hora_fin,
        descanso_inicio=t.descanso_inicio, descanso_fin=t.descanso_fin,
        modalidad=t.modalidad, capacidad=t.capacidad, activo=t.activo,
    )


def _validar_horario(payload: HorarioIn | HorarioUpdate, hi, hf, di, df) -> None:
    if hi is not None and hf is not None and hf <= hi:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "La hora de término debe ser posterior a la de inicio")
    if (di is None) != (df is None):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El descanso necesita inicio y término")
    if di is not None and df is not None:
        if df <= di:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "El término del descanso debe ser posterior a su inicio")
        if hi is not None and hf is not None and (di < hi or df > hf):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "El descanso debe estar dentro del turno")


@router.get("/horarios", response_model=list[HorarioOut])
async def list_horarios(
    professional_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CLINIC_AGENDAS, Action.VER)),
) -> list[HorarioOut]:
    clinic_id = empresa_clinic_id(ctx)
    q = select(WeeklyScheduleTemplate).where(WeeklyScheduleTemplate.clinic_id == clinic_id, WeeklyScheduleTemplate.deleted_at.is_(None))
    if professional_id:
        q = q.where(WeeklyScheduleTemplate.professional_id == professional_id)
    q = q.order_by(WeeklyScheduleTemplate.dia_semana, WeeklyScheduleTemplate.hora_inicio)
    rows = (await db.execute(q)).scalars().all()
    return [await _horario_out(db, t) for t in rows]


@router.post("/horarios", response_model=HorarioOut, status_code=status.HTTP_201_CREATED)
async def crear_horario(
    payload: HorarioIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CLINIC_AGENDAS, Action.CREAR)),
) -> HorarioOut:
    clinic_id = empresa_clinic_id(ctx)
    branch = await db.get(Branch, payload.branch_id)
    if branch is None or branch.clinic_id != clinic_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Sucursal inválida")
    await _assert_medico_clinica(db, clinic_id, payload.professional_id)
    await _validar_recinto(db, clinic_id, payload.room_id)
    _validar_horario(payload, payload.hora_inicio, payload.hora_fin, payload.descanso_inicio, payload.descanso_fin)
    t = WeeklyScheduleTemplate(
        clinic_id=clinic_id, professional_id=payload.professional_id, branch_id=payload.branch_id, room_id=payload.room_id,
        dia_semana=payload.dia_semana, hora_inicio=payload.hora_inicio, hora_fin=payload.hora_fin,
        descanso_inicio=payload.descanso_inicio, descanso_fin=payload.descanso_fin,
        modalidad=payload.modalidad, capacidad=payload.capacidad,
    )
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return await _horario_out(db, t)


async def _own_horario(db: AsyncSession, clinic_id: uuid.UUID, horario_id: uuid.UUID) -> WeeklyScheduleTemplate:
    t = await db.get(WeeklyScheduleTemplate, horario_id)
    if t is None or t.deleted_at is not None or t.clinic_id != clinic_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Horario no encontrado")
    return t


@router.patch("/horarios/{horario_id}", response_model=HorarioOut)
async def editar_horario(
    horario_id: uuid.UUID,
    payload: HorarioUpdate,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CLINIC_AGENDAS, Action.EDITAR)),
) -> HorarioOut:
    clinic_id = empresa_clinic_id(ctx)
    t = await _own_horario(db, clinic_id, horario_id)
    data = payload.model_dump(exclude_unset=True)
    if "room_id" in data:
        await _validar_recinto(db, clinic_id, data["room_id"])
    hi = data.get("hora_inicio", t.hora_inicio)
    hf = data.get("hora_fin", t.hora_fin)
    di = data.get("descanso_inicio", t.descanso_inicio)
    df = data.get("descanso_fin", t.descanso_fin)
    _validar_horario(payload, hi, hf, di, df)
    for k, v in data.items():
        setattr(t, k, v)
    await db.commit()
    await db.refresh(t)
    return await _horario_out(db, t)


@router.delete("/horarios/{horario_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_horario(
    horario_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CLINIC_AGENDAS, Action.ELIMINAR)),
) -> None:
    clinic_id = empresa_clinic_id(ctx)
    t = await _own_horario(db, clinic_id, horario_id)
    await db.delete(t)  # baja lógica vía listener; no borra bloques ya generados
    await db.commit()


@router.post("/horarios/generar", response_model=GenerarBloquesOut)
async def generar_bloques(
    payload: GenerarBloquesIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CLINIC_AGENDAS, Action.CREAR)),
) -> GenerarBloquesOut:
    """Materializa los availability_blocks a partir del horario semanal, para el
    rango [desde, hasta]. Es idempotente: si ya hay un bloque solapado del mismo
    profesional/sucursal, lo omite; si el recinto choca (EXCLUDE), también. El
    descanso parte el turno en dos bloques (52.4)."""
    clinic_id = empresa_clinic_id(ctx)
    if payload.hasta < payload.desde:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El rango de fechas es inválido")
    if (payload.hasta - payload.desde).days > 366:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El rango no puede superar un año")

    clinic = await db.get(Clinic, clinic_id)
    tz = _clinic_tz(clinic.pais if clinic else None)

    q = select(WeeklyScheduleTemplate).where(
        WeeklyScheduleTemplate.clinic_id == clinic_id,
        WeeklyScheduleTemplate.deleted_at.is_(None),
        WeeklyScheduleTemplate.activo.is_(True),
    )
    if payload.professional_id:
        q = q.where(WeeklyScheduleTemplate.professional_id == payload.professional_id)
    templates = (await db.execute(q)).scalars().all()

    # especialidad por profesional (para etiquetar el bloque)
    spec_by_prof: dict[uuid.UUID, uuid.UUID | None] = {}
    for pid in {t.professional_id for t in templates}:
        spec_by_prof[pid] = (
            await db.execute(
                select(ProfessionalProfile.specialty_id).where(
                    ProfessionalProfile.clinic_id == clinic_id, ProfessionalProfile.user_id == pid, ProfessionalProfile.deleted_at.is_(None)
                )
            )
        ).scalars().first()

    by_wd: dict[int, list[WeeklyScheduleTemplate]] = {}
    for t in templates:
        by_wd.setdefault(t.dia_semana, []).append(t)

    def _seg(day: date, t: WeeklyScheduleTemplate) -> list[tuple[datetime, datetime]]:
        def combine(tm) -> datetime:
            return datetime.combine(day, tm, tzinfo=tz).astimezone(timezone.utc)
        start, end = combine(t.hora_inicio), combine(t.hora_fin)
        if t.descanso_inicio and t.descanso_fin:
            segs = [(start, combine(t.descanso_inicio)), (combine(t.descanso_fin), end)]
        else:
            segs = [(start, end)]
        return [(s, e) for s, e in segs if e > s]

    # Candidatos (uno por segmento/día/plantilla)
    candidatos: list[tuple[WeeklyScheduleTemplate, datetime, datetime]] = []
    dias = 0
    d = payload.desde
    while d <= payload.hasta:
        dias += 1
        for t in by_wd.get(d.weekday(), []):
            for s, e in _seg(d, t):
                candidatos.append((t, s, e))
        d += timedelta(days=1)

    from app.core.database import AsyncSessionLocal
    generados = 0
    omitidos = 0
    for t, s, e in candidatos:
        async with AsyncSessionLocal() as sess:
            # No materializar dentro de un bloqueo negativo (52.9).
            if await overlaps_exception(sess, clinic_id, t.professional_id, s, e, t.branch_id):
                omitidos += 1
                continue
            existe = (
                await sess.execute(
                    select(AvailabilityBlock.id).where(
                        AvailabilityBlock.clinic_id == clinic_id,
                        AvailabilityBlock.professional_id == t.professional_id,
                        AvailabilityBlock.branch_id == t.branch_id,
                        AvailabilityBlock.deleted_at.is_(None),
                        AvailabilityBlock.rango.op("&&")(Range(s, e)),
                    )
                )
            ).scalars().first()
            if existe is not None:
                omitidos += 1
                continue
            sess.add(
                AvailabilityBlock(
                    clinic_id=clinic_id, branch_id=t.branch_id, professional_id=t.professional_id, room_id=t.room_id,
                    specialty_id=spec_by_prof.get(t.professional_id),
                    rango=Range(s, e), reglas={"modalidad": t.modalidad, "capacidad": t.capacidad, "origen": "plantilla"},
                )
            )
            try:
                await sess.commit()
                generados += 1
            except IntegrityError:
                await sess.rollback()
                omitidos += 1

    return GenerarBloquesOut(generados=generados, omitidos=omitidos, dias=dias)


# ─────────────────────────── bloqueos negativos de agenda (51 / 52.9) ───────────────────────────
async def _bloqueo_out(db: AsyncSession, b: ScheduleException) -> BloqueoOut:
    prof = await db.get(User, b.professional_id)
    branch = await db.get(Branch, b.branch_id) if b.branch_id else None
    autor = await db.get(User, b.created_by) if b.created_by else None
    return BloqueoOut(
        id=b.id, professional_id=b.professional_id, professional_nombre=prof.nombre if prof else "",
        branch_id=b.branch_id, branch_nombre=branch.nombre if branch else None,
        inicio=b.rango.lower, fin=b.rango.upper, motivo=b.motivo, creado_por=autor.nombre if autor else None,
    )


@router.get("/bloqueos", response_model=list[BloqueoOut])
async def list_bloqueos(
    professional_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CLINIC_AGENDAS, Action.VER)),
) -> list[BloqueoOut]:
    clinic_id = empresa_clinic_id(ctx)
    q = select(ScheduleException).where(ScheduleException.clinic_id == clinic_id, ScheduleException.deleted_at.is_(None))
    if professional_id:
        q = q.where(ScheduleException.professional_id == professional_id)
    q = q.order_by(func.lower(ScheduleException.rango).desc())
    rows = (await db.execute(q)).scalars().all()
    return [await _bloqueo_out(db, b) for b in rows]


@router.post("/bloqueos", response_model=BloqueoOut, status_code=status.HTTP_201_CREATED)
async def crear_bloqueo(
    payload: BloqueoIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CLINIC_AGENDAS, Action.CREAR)),
) -> BloqueoOut:
    clinic_id = empresa_clinic_id(ctx)
    if payload.fin <= payload.inicio:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El fin del bloqueo debe ser posterior al inicio")
    await _assert_medico_clinica(db, clinic_id, payload.professional_id)
    if payload.branch_id is not None:
        branch = await db.get(Branch, payload.branch_id)
        if branch is None or branch.clinic_id != clinic_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Sucursal inválida")
    b = ScheduleException(
        clinic_id=clinic_id, professional_id=payload.professional_id, branch_id=payload.branch_id,
        rango=Range(payload.inicio, payload.fin), motivo=payload.motivo, created_by=ctx.user_id,
    )
    db.add(b)
    await db.commit()
    await db.refresh(b)
    return await _bloqueo_out(db, b)


@router.delete("/bloqueos/{bloqueo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_bloqueo(
    bloqueo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CLINIC_AGENDAS, Action.ELIMINAR)),
) -> None:
    clinic_id = empresa_clinic_id(ctx)
    b = await db.get(ScheduleException, bloqueo_id)
    if b is None or b.deleted_at is not None or b.clinic_id != clinic_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bloqueo no encontrado")
    await db.delete(b)  # baja lógica vía listener
    await db.commit()


async def _bloque_out(db: AsyncSession, block: AvailabilityBlock) -> BloqueOut:
    prof = await db.get(User, block.professional_id)
    branch = await db.get(Branch, block.branch_id)
    room = await db.get(Room, block.room_id) if block.room_id else None
    return BloqueOut(
        id=block.id,
        professional_id=block.professional_id,
        professional_nombre=prof.nombre if prof else "",
        branch_nombre=branch.nombre if branch else "",
        inicio=block.rango.lower,
        fin=block.rango.upper,
        room_id=block.room_id,
        room_nombre=room.nombre if room else None,
        reglas=block.reglas,
    )


async def _validar_recinto(db: AsyncSession, clinic_id: uuid.UUID, room_id: uuid.UUID | None) -> None:
    if room_id is None:
        return
    room = await db.get(Room, room_id)
    if room is None or room.deleted_at is not None or room.clinic_id != clinic_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Recinto inválido")


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
    if not await _profile_activo(db, clinic_id, payload.professional_id):
        raise HTTPException(status.HTTP_409_CONFLICT, "El profesional está inhabilitado; su agenda está congelada")
    await _validar_recinto(db, clinic_id, payload.room_id)
    block = AvailabilityBlock(
        clinic_id=clinic_id,
        branch_id=payload.branch_id,
        professional_id=payload.professional_id,
        room_id=payload.room_id,
        rango=Range(payload.inicio, payload.fin),
        reglas=payload.reglas,
    )
    db.add(block)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "El recinto ya está ocupado por otro profesional en ese horario") from None
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
    if payload.room_id is not None:
        await _validar_recinto(db, clinic_id, payload.room_id)
        block.room_id = payload.room_id
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "El recinto ya está ocupado por otro profesional en ese horario") from None
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


# ─────────────────────────── recintos (salas/boxes) ───────────────────────────
def _recinto_out(r: Room) -> RecintoOut:
    return RecintoOut(id=r.id, nombre=r.nombre, numero=r.numero, tipo=r.tipo, activo=r.activo, branch_id=r.branch_id)


@router.get("/recintos", response_model=list[RecintoOut])
async def list_recintos(
    tipo: str | None = None,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CLINIC_AGENDAS, Action.VER)),
) -> list[RecintoOut]:
    clinic_id = empresa_clinic_id(ctx)
    q = select(Room).where(Room.clinic_id == clinic_id, Room.deleted_at.is_(None))
    if tipo in ("medica", "dental"):
        q = q.where(Room.tipo == tipo)
    rows = (await db.execute(q.order_by(Room.tipo, Room.numero))).scalars().all()
    return [_recinto_out(r) for r in rows]


@router.post("/recintos", response_model=RecintoOut, status_code=status.HTTP_201_CREATED)
async def crear_recinto(
    payload: RecintoIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CLINIC_AGENDAS, Action.CREAR)),
) -> RecintoOut:
    clinic_id = empresa_clinic_id(ctx)
    if payload.tipo not in ("medica", "dental"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Tipo de recinto inválido (medica | dental)")
    if payload.branch_id is not None:
        branch = await db.get(Branch, payload.branch_id)
        if branch is None or branch.clinic_id != clinic_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Sucursal inválida")
    room = Room(clinic_id=clinic_id, branch_id=payload.branch_id, nombre=payload.nombre, numero=payload.numero, tipo=payload.tipo)
    db.add(room)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, f"Ya existe un recinto {payload.tipo} con el número {payload.numero}") from None
    await db.refresh(room)
    return _recinto_out(room)


async def _own_recinto(db: AsyncSession, clinic_id: uuid.UUID, room_id: uuid.UUID) -> Room:
    room = await db.get(Room, room_id)
    if room is None or room.deleted_at is not None or room.clinic_id != clinic_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recinto no encontrado")
    return room


@router.patch("/recintos/{room_id}", response_model=RecintoOut)
async def editar_recinto(
    room_id: uuid.UUID,
    payload: RecintoUpdate,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CLINIC_AGENDAS, Action.EDITAR)),
) -> RecintoOut:
    clinic_id = empresa_clinic_id(ctx)
    room = await _own_recinto(db, clinic_id, room_id)
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(room, k, v)
    await db.commit()
    await db.refresh(room)
    return _recinto_out(room)


@router.delete("/recintos/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_recinto(
    room_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CLINIC_AGENDAS, Action.ELIMINAR)),
) -> None:
    clinic_id = empresa_clinic_id(ctx)
    room = await _own_recinto(db, clinic_id, room_id)
    await db.delete(room)  # soft delete via listener
    await db.commit()


# ─────────────────────────── catálogo ───────────────────────────
async def _servicio_out(db: AsyncSession, item: CatalogItem) -> ServicioAdminOut:
    specialty = await db.get(Specialty, item.specialty_id) if item.specialty_id else None
    return ServicioAdminOut(
        id=item.id, nombre=item.nombre, precio=float(item.precio), duracion_min=item.duracion_min, activo=item.activo,
        specialty_nombre=specialty.nombre if specialty else None, afecto_iva=item.afecto_iva, comisiona=item.comisiona
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
    item = CatalogItem(clinic_id=clinic_id, specialty_id=payload.specialty_id, tipo="servicio", nombre=payload.nombre, precio=payload.precio, duracion_min=payload.duracion_min, afecto_iva=payload.afecto_iva, comisiona=payload.comisiona)
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
