"""Agenda online pública (punto 60) — SIN autenticación.

La clínica publica su agenda en higia.cl/reservar/<slug>. Un paciente (aunque
no tenga cuenta) ve los servicios reservables y la disponibilidad real, y deja
una *solicitud de hora*. El personal la confirma después desde el panel de
empresa, momento en que se materializa la cita. Este router no usa RBAC:
resuelve la clínica por su `slug` y fija el `clinic_id` explícitamente.
"""

import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import Range
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.catalog import CatalogItem, Specialty
from app.models.identity import User
from app.models.professional import ProfessionalProfile
from app.models.scheduling import Appointment, AvailabilityBlock, OnlineBookingRequest, PublicAgendaVisit
from app.models.tenant import Branch, Clinic
from app.schemas.public import (
    ClinicaPublicaOut,
    ReservaPublicaIn,
    ReservaPublicaOut,
    ServicioPublicoOut,
    SlotPublicoOut,
    SolicitudEstadoOut,
    SucursalPublicaOut,
)
from app.services.scheduling import generate_slots, overlaps_exception

router = APIRouter(prefix="/public/reservas", tags=["public"])

DEFAULT_CFG = {"habilitada": False, "anticipacion_horas": 2, "ventana_dias": 30, "mensaje": None}


def _cfg(clinic: Clinic) -> dict:
    return {**DEFAULT_CFG, **(clinic.agenda_online or {})}


async def _clinic_by_slug(db: AsyncSession, slug: str) -> Clinic:
    clinic = (
        await db.execute(select(Clinic).where(Clinic.slug == slug, Clinic.deleted_at.is_(None)))
    ).scalar_one_or_none()
    if clinic is None or not clinic.activo:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Clínica no encontrada")
    return clinic


async def _prof_nombres(db: AsyncSession, ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not ids:
        return {}
    rows = (await db.execute(select(User.id, User.nombre).where(User.id.in_(ids)))).all()
    return {uid: nombre for uid, nombre in rows}


@router.get("/{slug}", response_model=ClinicaPublicaOut)
async def clinica_publica(slug: str, db: AsyncSession = Depends(get_db)) -> ClinicaPublicaOut:
    clinic = await _clinic_by_slug(db, slug)
    cfg = _cfg(clinic)

    servicios: list[ServicioPublicoOut] = []
    if cfg["habilitada"]:
        rows = (
            await db.execute(
                select(CatalogItem, Specialty.nombre, Specialty.icono)
                .join(Specialty, Specialty.id == CatalogItem.specialty_id, isouter=True)
                .where(
                    CatalogItem.clinic_id == clinic.id,
                    CatalogItem.tipo == "servicio",
                    CatalogItem.activo.is_(True),
                    CatalogItem.reservable_online.is_(True),
                    CatalogItem.deleted_at.is_(None),
                )
                .order_by(CatalogItem.nombre)
            )
        ).all()
        servicios = [
            ServicioPublicoOut(id=it.id, nombre=it.nombre, especialidad=esp, icono=icono, precio=float(it.precio), duracion_min=it.duracion_min or 30)
            for it, esp, icono in rows
        ]

    branch_rows = (
        await db.execute(
            select(Branch).where(Branch.clinic_id == clinic.id, Branch.activo.is_(True), Branch.deleted_at.is_(None)).order_by(Branch.nombre)
        )
    ).scalars().all()
    sucursales = [SucursalPublicaOut(id=b.id, nombre=b.nombre, direccion=b.direccion) for b in branch_rows]

    # Registrar la visita para el embudo de conversión (60.12), solo si la
    # agenda está publicada (una página apagada no cuenta como visita real).
    if cfg["habilitada"]:
        db.add(PublicAgendaVisit(clinic_id=clinic.id))
        await db.commit()

    return ClinicaPublicaOut(
        slug=slug,
        nombre=clinic.razon_social,
        habilitada=bool(cfg["habilitada"]),
        mensaje=cfg["mensaje"],
        servicios=servicios,
        sucursales=sucursales,
    )


@router.get("/{slug}/disponibilidad", response_model=list[SlotPublicoOut])
async def disponibilidad_publica(
    slug: str,
    service_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[SlotPublicoOut]:
    clinic = await _clinic_by_slug(db, slug)
    cfg = _cfg(clinic)
    if not cfg["habilitada"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "La agenda online no está habilitada")

    service = await db.get(CatalogItem, service_id)
    if service is None or service.clinic_id != clinic.id or not service.reservable_online or not service.activo:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Servicio no disponible")

    now = datetime.now(timezone.utc)
    earliest = now + timedelta(hours=int(cfg["anticipacion_horas"]))
    latest = now + timedelta(days=int(cfg["ventana_dias"]))
    dur = service.duracion_min or 30

    # Profesionales inhabilitados: agenda congelada, no se ofrecen (55.3).
    inactivos = set(
        (
            await db.execute(
                select(ProfessionalProfile.user_id).where(
                    ProfessionalProfile.clinic_id == clinic.id,
                    ProfessionalProfile.activo.is_(False),
                    ProfessionalProfile.deleted_at.is_(None),
                )
            )
        ).scalars().all()
    )

    blocks = (
        await db.execute(
            select(AvailabilityBlock).where(
                AvailabilityBlock.clinic_id == clinic.id,
                AvailabilityBlock.deleted_at.is_(None),
                (AvailabilityBlock.specialty_id == service.specialty_id) | (AvailabilityBlock.specialty_id.is_(None)),
            )
        )
    ).scalars().all()

    slots: list[SlotPublicoOut] = []
    prof_ids: set[uuid.UUID] = set()
    for block in blocks:
        if block.professional_id in inactivos:
            continue
        start = max(block.rango.lower, earliest)
        end = min(block.rango.upper, latest)
        if start >= end:
            continue
        # Huecos ya tomados: citas vigentes + solicitudes pendientes del profesional.
        booked_appt = (
            await db.execute(
                select(Appointment.slot).where(
                    Appointment.professional_id == block.professional_id,
                    Appointment.deleted_at.is_(None),
                    Appointment.estado != "cancelada",
                )
            )
        ).scalars().all()
        booked_req = (
            await db.execute(
                select(OnlineBookingRequest.slot).where(
                    OnlineBookingRequest.professional_id == block.professional_id,
                    OnlineBookingRequest.deleted_at.is_(None),
                    OnlineBookingRequest.estado == "pendiente",
                )
            )
        ).scalars().all()
        booked = [(r.lower, r.upper) for r in booked_appt] + [(r.lower, r.upper) for r in booked_req]
        for s, e in generate_slots(start, end, dur, booked):
            if await overlaps_exception(db, clinic.id, block.professional_id, s, e, block.branch_id):
                continue
            slots.append(SlotPublicoOut(professional_id=block.professional_id, profesional_nombre="", inicio=s, fin=e))
            prof_ids.add(block.professional_id)

    nombres = await _prof_nombres(db, prof_ids)
    for sl in slots:
        sl.profesional_nombre = nombres.get(sl.professional_id, "")
    slots.sort(key=lambda x: (x.inicio, x.profesional_nombre))
    return slots


@router.post("/{slug}", response_model=ReservaPublicaOut, status_code=status.HTTP_201_CREATED)
async def reservar_publico(
    slug: str,
    payload: ReservaPublicaIn,
    db: AsyncSession = Depends(get_db),
) -> ReservaPublicaOut:
    clinic = await _clinic_by_slug(db, slug)
    cfg = _cfg(clinic)
    if not cfg["habilitada"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "La agenda online no está habilitada")

    if payload.fin <= payload.inicio:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El horario es inválido")

    service = await db.get(CatalogItem, payload.service_id)
    if service is None or service.clinic_id != clinic.id or not service.reservable_online or not service.activo:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Servicio no disponible")

    now = datetime.now(timezone.utc)
    earliest = now + timedelta(hours=int(cfg["anticipacion_horas"]))
    latest = now + timedelta(days=int(cfg["ventana_dias"]))
    if payload.inicio < earliest:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El horario está fuera del plazo mínimo de anticipación")
    if payload.inicio > latest:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El horario está fuera de la ventana de reserva")

    # ¿El profesional atiende ese hueco? (dentro de un availability_block suyo)
    block = (
        await db.execute(
            select(AvailabilityBlock).where(
                AvailabilityBlock.clinic_id == clinic.id,
                AvailabilityBlock.professional_id == payload.professional_id,
                AvailabilityBlock.deleted_at.is_(None),
                AvailabilityBlock.rango.op("@>")(Range(payload.inicio, payload.fin)),
            )
        )
    ).scalars().first()
    if block is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Ese horario está fuera de la disponibilidad del profesional")

    if await overlaps_exception(db, clinic.id, payload.professional_id, payload.inicio, payload.fin, block.branch_id):
        raise HTTPException(status.HTTP_409_CONFLICT, "Ese horario está bloqueado para el profesional")

    # Choque con una cita vigente o con otra solicitud pendiente del profesional.
    slot_range = Range(payload.inicio, payload.fin)
    clash_appt = (
        await db.execute(
            select(Appointment.id).where(
                Appointment.professional_id == payload.professional_id,
                Appointment.deleted_at.is_(None),
                Appointment.estado != "cancelada",
                Appointment.slot.op("&&")(slot_range),
            )
        )
    ).scalars().first()
    clash_req = (
        await db.execute(
            select(OnlineBookingRequest.id).where(
                OnlineBookingRequest.professional_id == payload.professional_id,
                OnlineBookingRequest.deleted_at.is_(None),
                OnlineBookingRequest.estado == "pendiente",
                OnlineBookingRequest.slot.op("&&")(slot_range),
            )
        )
    ).scalars().first()
    if clash_appt or clash_req:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ese horario ya no está disponible — elige otro.")

    codigo = secrets.token_hex(4).upper()
    req = OnlineBookingRequest(
        clinic_id=clinic.id,
        branch_id=block.branch_id,
        professional_id=payload.professional_id,
        service_id=service.id,
        slot=slot_range,
        codigo=codigo,
        estado="pendiente",
        paciente_nombre=payload.nombre.strip(),
        paciente_rut=payload.rut,
        paciente_telefono=payload.telefono,
        paciente_email=payload.email,
        notas=payload.notas,
    )
    db.add(req)
    await db.commit()

    prof = await db.get(User, payload.professional_id)
    return ReservaPublicaOut(
        codigo=codigo,
        estado=req.estado,
        inicio=payload.inicio,
        fin=payload.fin,
        servicio_nombre=service.nombre,
        profesional_nombre=prof.nombre if prof else "",
    )


@router.get("/{slug}/estado/{codigo}", response_model=SolicitudEstadoOut)
async def estado_solicitud(slug: str, codigo: str, db: AsyncSession = Depends(get_db)) -> SolicitudEstadoOut:
    clinic = await _clinic_by_slug(db, slug)
    req = (
        await db.execute(
            select(OnlineBookingRequest).where(
                OnlineBookingRequest.clinic_id == clinic.id,
                OnlineBookingRequest.codigo == codigo.upper(),
                OnlineBookingRequest.deleted_at.is_(None),
            )
        )
    ).scalars().first()
    if req is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Solicitud no encontrada")
    return SolicitudEstadoOut(codigo=req.codigo, estado=req.estado, inicio=req.slot.lower, fin=req.slot.upper)
