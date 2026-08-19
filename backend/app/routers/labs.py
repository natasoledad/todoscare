"""Laboratorios dentales (punto 57) — visión Empresa/Cliente.

Catálogo de laboratorios (57.1) y sus prestaciones con costo (lo que se paga
al lab) vs precio (lo que se cobra al paciente) (57.3b). Las órdenes de trabajo
y las cuentas por pagar llegan en PR-S.
"""

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.laboratory import DentalLab, LabService
from app.rbac.deps import require
from app.rbac.permissions import Action, Resource
from app.schemas.labs import (
    LabIn,
    LabOut,
    LabServiceIn,
    LabServiceOut,
    LabServiceUpdate,
    LabUpdate,
)
from app.tenancy.context import TenantContext

router = APIRouter(prefix="/empresa/labs", tags=["laboratorios"])


def _clinic_id(ctx: TenantContext) -> uuid.UUID:
    ids = ctx.clinic_ids()
    if not ids:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "La cuenta no tiene una clínica asignada")
    return next(iter(ids))


def _lab_out(lab: DentalLab) -> LabOut:
    return LabOut(id=lab.id, nombre=lab.nombre, rut=lab.rut, contacto=lab.contacto, activo=lab.activo)


def _service_out(s: LabService) -> LabServiceOut:
    costo, precio = float(s.costo), float(s.precio)
    return LabServiceOut(id=s.id, lab_id=s.lab_id, nombre=s.nombre, costo=costo, precio=precio, margen=round(precio - costo, 2), activo=s.activo)


async def _own_lab(db: AsyncSession, cid: uuid.UUID, lab_id: uuid.UUID) -> DentalLab:
    lab = await db.get(DentalLab, lab_id)
    if lab is None or lab.clinic_id != cid or lab.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Laboratorio no encontrado")
    return lab


async def _own_service(db: AsyncSession, cid: uuid.UUID, sid: uuid.UUID) -> LabService:
    s = await db.get(LabService, sid)
    if s is None or s.clinic_id != cid or s.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prestación no encontrada")
    return s


# ─────────────────────────── laboratorios (57.1) ───────────────────────────
@router.get("", response_model=list[LabOut])
async def list_labs(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.LABORATORIOS, Action.VER)),
) -> list[LabOut]:
    cid = _clinic_id(ctx)
    rows = (await db.execute(select(DentalLab).where(DentalLab.clinic_id == cid, DentalLab.deleted_at.is_(None)).order_by(DentalLab.nombre))).scalars().all()
    return [_lab_out(lab) for lab in rows]


@router.post("", response_model=LabOut, status_code=status.HTTP_201_CREATED)
async def crear_lab(
    payload: LabIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.LABORATORIOS, Action.CREAR)),
) -> LabOut:
    cid = _clinic_id(ctx)
    lab = DentalLab(clinic_id=cid, nombre=payload.nombre, rut=payload.rut, contacto=payload.contacto)
    db.add(lab)
    await db.commit()
    await db.refresh(lab)
    return _lab_out(lab)


@router.patch("/{lab_id}", response_model=LabOut)
async def editar_lab(
    lab_id: uuid.UUID,
    payload: LabUpdate,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.LABORATORIOS, Action.EDITAR)),
) -> LabOut:
    cid = _clinic_id(ctx)
    lab = await _own_lab(db, cid, lab_id)
    for f in ("nombre", "rut", "contacto", "activo"):
        v = getattr(payload, f)
        if v is not None:
            setattr(lab, f, v)
    await db.commit()
    await db.refresh(lab)
    return _lab_out(lab)


@router.delete("/{lab_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_lab(
    lab_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.LABORATORIOS, Action.ELIMINAR)),
) -> None:
    cid = _clinic_id(ctx)
    lab = await _own_lab(db, cid, lab_id)
    await db.delete(lab)  # baja lógica vía listener global de auditoría
    await db.commit()


# ─────────────────────────── prestaciones del lab (57.3b) ───────────────────────────
@router.get("/{lab_id}/servicios", response_model=list[LabServiceOut])
async def list_servicios(
    lab_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.LABORATORIOS, Action.VER)),
) -> list[LabServiceOut]:
    cid = _clinic_id(ctx)
    await _own_lab(db, cid, lab_id)
    rows = (await db.execute(select(LabService).where(LabService.clinic_id == cid, LabService.lab_id == lab_id, LabService.deleted_at.is_(None)).order_by(LabService.nombre))).scalars().all()
    return [_service_out(s) for s in rows]


@router.post("/{lab_id}/servicios", response_model=LabServiceOut, status_code=status.HTTP_201_CREATED)
async def crear_servicio(
    lab_id: uuid.UUID,
    payload: LabServiceIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.LABORATORIOS, Action.CREAR)),
) -> LabServiceOut:
    cid = _clinic_id(ctx)
    await _own_lab(db, cid, lab_id)
    s = LabService(clinic_id=cid, lab_id=lab_id, nombre=payload.nombre, costo=Decimal(str(payload.costo)), precio=Decimal(str(payload.precio)))
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return _service_out(s)


@router.patch("/servicios/{sid}", response_model=LabServiceOut)
async def editar_servicio(
    sid: uuid.UUID,
    payload: LabServiceUpdate,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.LABORATORIOS, Action.EDITAR)),
) -> LabServiceOut:
    cid = _clinic_id(ctx)
    s = await _own_service(db, cid, sid)
    if payload.nombre is not None:
        s.nombre = payload.nombre
    if payload.costo is not None:
        s.costo = Decimal(str(payload.costo))
    if payload.precio is not None:
        s.precio = Decimal(str(payload.precio))
    if payload.activo is not None:
        s.activo = payload.activo
    await db.commit()
    await db.refresh(s)
    return _service_out(s)


@router.delete("/servicios/{sid}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_servicio(
    sid: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.LABORATORIOS, Action.ELIMINAR)),
) -> None:
    cid = _clinic_id(ctx)
    s = await _own_service(db, cid, sid)
    await db.delete(s)
    await db.commit()
