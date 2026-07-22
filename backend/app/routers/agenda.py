import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import Range
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.catalog import CatalogItem, Specialty
from app.models.scheduling import Appointment, AvailabilityBlock
from app.models.tenant import Branch
from app.rbac.deps import require
from app.rbac.permissions import Action, Resource
from app.routers.patients import get_own_patient
from app.schemas.agenda import CitaOut, ReservaInput, ServicioOut, SlotOut
from app.services.scheduling import generate_slots
from app.tenancy.context import TenantContext

router = APIRouter(prefix="/agenda", tags=["agenda"])


@router.get("/servicios", response_model=list[ServicioOut])
async def list_servicios(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CATALOGO_PRECIOS, Action.VER)),
) -> list[ServicioOut]:
    patient = await get_own_patient(db, ctx)
    rows = (
        await db.execute(
            select(CatalogItem, Specialty.icono)
            .join(Specialty, Specialty.id == CatalogItem.specialty_id, isouter=True)
            .where(
                CatalogItem.clinic_id == patient.clinic_id,
                CatalogItem.tipo == "servicio",
                CatalogItem.activo.is_(True),
                CatalogItem.deleted_at.is_(None),
            )
        )
    ).all()
    return [ServicioOut(id=item.id, nombre=item.nombre, icono=icono, precio=float(item.precio), duracion_min=item.duracion_min or 30) for item, icono in rows]


@router.get("/disponibilidad", response_model=list[SlotOut])
async def get_disponibilidad(
    service_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.OWN_APPOINTMENTS, Action.VER)),
) -> list[SlotOut]:
    patient = await get_own_patient(db, ctx)
    service = await db.get(CatalogItem, service_id)
    if service is None or service.clinic_id != patient.clinic_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Servicio no encontrado")

    blocks = (
        await db.execute(
            select(AvailabilityBlock).where(
                AvailabilityBlock.clinic_id == patient.clinic_id,
                (AvailabilityBlock.specialty_id == service.specialty_id) | (AvailabilityBlock.specialty_id.is_(None)),
            )
        )
    ).scalars().all()

    slots: list[SlotOut] = []
    for block in blocks:
        booked_rows = (
            await db.execute(
                select(Appointment.slot).where(
                    Appointment.professional_id == block.professional_id,
                    Appointment.deleted_at.is_(None),
                    Appointment.estado != "cancelada",
                )
            )
        ).scalars().all()
        booked_ranges = [(r.lower, r.upper) for r in booked_rows]
        for start, end in generate_slots(block.rango.lower, block.rango.upper, service.duracion_min or 30, booked_ranges):
            slots.append(SlotOut(professional_id=block.professional_id, inicio=start, fin=end))

    return slots


@router.post("/reservar", response_model=CitaOut, status_code=status.HTTP_201_CREATED)
async def reservar(
    payload: ReservaInput,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.OWN_APPOINTMENTS, Action.CREAR)),
) -> CitaOut:
    patient = await get_own_patient(db, ctx)
    service = await db.get(CatalogItem, payload.service_id)
    if service is None or service.clinic_id != patient.clinic_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Servicio no encontrado")

    block = (
        await db.execute(
            select(AvailabilityBlock).where(
                AvailabilityBlock.clinic_id == patient.clinic_id,
                AvailabilityBlock.professional_id == payload.professional_id,
                AvailabilityBlock.rango.op("@>")(Range(payload.inicio, payload.fin)),
            )
        )
    ).scalars().first()
    if block is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Ese horario está fuera de la disponibilidad del profesional")

    appointment = Appointment(
        clinic_id=patient.clinic_id,
        branch_id=block.branch_id,
        professional_id=payload.professional_id,
        patient_id=patient.id,
        service_id=service.id,
        slot=Range(payload.inicio, payload.fin),
        estado="confirmada",
    )
    db.add(appointment)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Ese horario ya no está disponible — elige otro.") from None

    await db.refresh(appointment)
    branch = await db.get(Branch, appointment.branch_id)
    return CitaOut(
        id=appointment.id,
        servicio_nombre=service.nombre,
        inicio=payload.inicio,
        fin=payload.fin,
        estado=appointment.estado,
        ubicacion=branch.nombre if branch else "",
    )


@router.get("/mias", response_model=list[CitaOut])
async def list_mias(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.OWN_APPOINTMENTS, Action.VER)),
) -> list[CitaOut]:
    patient = await get_own_patient(db, ctx)
    rows = (
        await db.execute(
            select(Appointment, CatalogItem.nombre, Branch.nombre)
            .join(CatalogItem, CatalogItem.id == Appointment.service_id, isouter=True)
            .join(Branch, Branch.id == Appointment.branch_id, isouter=True)
            .where(Appointment.patient_id == patient.id, Appointment.deleted_at.is_(None))
            .order_by(Appointment.slot.desc())
        )
    ).all()
    return [
        CitaOut(
            id=appt.id,
            servicio_nombre=servicio_nombre or "",
            inicio=appt.slot.lower,
            fin=appt.slot.upper,
            estado=appt.estado,
            ubicacion=branch_nombre or "",
        )
        for appt, servicio_nombre, branch_nombre in rows
    ]


@router.patch("/{appointment_id}/cancelar", response_model=CitaOut)
async def cancelar(
    appointment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.OWN_APPOINTMENTS, Action.ELIMINAR)),
) -> CitaOut:
    patient = await get_own_patient(db, ctx)
    appointment = await db.get(Appointment, appointment_id)
    if appointment is None or appointment.patient_id != patient.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cita no encontrada")
    if appointment.estado in ("cancelada", "completada"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"La cita ya está {appointment.estado}")

    appointment.estado = "cancelada"
    await db.commit()
    await db.refresh(appointment)

    service = await db.get(CatalogItem, appointment.service_id)
    branch = await db.get(Branch, appointment.branch_id)
    return CitaOut(
        id=appointment.id,
        servicio_nombre=service.nombre if service else "",
        inicio=appointment.slot.lower,
        fin=appointment.slot.upper,
        estado=appointment.estado,
        ubicacion=branch.nombre if branch else "",
    )
