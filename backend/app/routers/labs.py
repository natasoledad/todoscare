"""Laboratorios dentales (punto 57) — visión Empresa/Cliente.

Catálogo de laboratorios (57.1) y sus prestaciones con costo (lo que se paga
al lab) vs precio (lo que se cobra al paciente) (57.3b). Las órdenes de trabajo
y las cuentas por pagar llegan en PR-S.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.clinical import TreatmentPlan
from app.models.identity import User
from app.models.laboratory import DentalLab, LabOrder, LabService
from app.models.patient import Patient
from app.rbac.deps import require
from app.rbac.permissions import Action, Resource
from app.schemas.labs import (
    CuentaPorPagarOut,
    LabIn,
    LabOrderEstadoIn,
    LabOrderIn,
    LabOrderOut,
    LabOrderUpdate,
    LabOut,
    LabServiceIn,
    LabServiceOut,
    LabServiceUpdate,
    LabUpdate,
)
from app.tenancy.context import TenantContext

router = APIRouter(prefix="/empresa/labs", tags=["laboratorios"])

# Flujo de estados de una orden (57.11).
_TRANSICIONES: dict[str, set[str]] = {
    "solicitado": {"en_proceso", "cancelado"},
    "en_proceso": {"en_revision", "cancelado"},
    "en_revision": {"terminado", "en_proceso", "cancelado"},
    "terminado": set(),
    "cancelado": set(),
}


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


# ─────────────────────────── órdenes de trabajo (57.11 · 57.12) ───────────────────────────
async def _paciente_nombre(db: AsyncSession, patient_id: uuid.UUID | None) -> str | None:
    if patient_id is None:
        return None
    row = (
        await db.execute(
            select(User.nombre).join(Patient, Patient.user_id == User.id).where(Patient.id == patient_id)
        )
    ).scalars().first()
    return row


async def _order_out(db: AsyncSession, o: LabOrder) -> LabOrderOut:
    lab = await db.get(DentalLab, o.lab_id)
    return LabOrderOut(
        id=o.id, lab_id=o.lab_id, lab_nombre=lab.nombre if lab else None,
        descripcion=o.descripcion, pieza=o.pieza, costo=float(o.costo), precio=float(o.precio),
        estado=o.estado, fecha_entrega=o.fecha_entrega, pagado=o.pagado,
        patient_id=o.patient_id, paciente_nombre=await _paciente_nombre(db, o.patient_id),
        treatment_plan_id=o.treatment_plan_id, notas=o.notas, creada=o.created_at,
    )


async def _own_order(db: AsyncSession, cid: uuid.UUID, oid: uuid.UUID) -> LabOrder:
    o = await db.get(LabOrder, oid)
    if o is None or o.clinic_id != cid or o.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Orden no encontrada")
    return o


@router.get("/ordenes", response_model=list[LabOrderOut])
async def list_ordenes(
    estado: str | None = None,
    lab_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.LABORATORIOS, Action.VER)),
) -> list[LabOrderOut]:
    cid = _clinic_id(ctx)
    q = select(LabOrder).where(LabOrder.clinic_id == cid, LabOrder.deleted_at.is_(None))
    if estado:
        q = q.where(LabOrder.estado == estado)
    if lab_id:
        q = q.where(LabOrder.lab_id == lab_id)
    q = q.order_by(LabOrder.created_at.desc())
    rows = (await db.execute(q)).scalars().all()
    return [await _order_out(db, o) for o in rows]


@router.post("/ordenes", response_model=LabOrderOut, status_code=status.HTTP_201_CREATED)
async def crear_orden(
    payload: LabOrderIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.LABORATORIOS, Action.CREAR)),
) -> LabOrderOut:
    cid = _clinic_id(ctx)
    await _own_lab(db, cid, payload.lab_id)

    costo = Decimal(str(payload.costo)) if payload.costo is not None else None
    precio = Decimal(str(payload.precio)) if payload.precio is not None else None
    if payload.lab_service_id is not None:
        svc = await _own_service(db, cid, payload.lab_service_id)
        if svc.lab_id != payload.lab_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "La prestación no pertenece a ese laboratorio")
        if costo is None:
            costo = Decimal(svc.costo)
        if precio is None:
            precio = Decimal(svc.precio)

    # Origen desde el tratamiento (57.12): hereda paciente y profesional del plan.
    patient_id = payload.patient_id
    professional_id = None
    if payload.treatment_plan_id is not None:
        plan = await db.get(TreatmentPlan, payload.treatment_plan_id)
        if plan is None or plan.clinic_id != cid or plan.deleted_at is not None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Plan de tratamiento inválido")
        patient_id = patient_id or plan.patient_id
        professional_id = plan.professional_id
    if patient_id is not None:
        pac = await db.get(Patient, patient_id)
        if pac is None or pac.clinic_id != cid or pac.deleted_at is not None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Paciente inválido")

    o = LabOrder(
        clinic_id=cid, lab_id=payload.lab_id, lab_service_id=payload.lab_service_id,
        patient_id=patient_id, treatment_plan_id=payload.treatment_plan_id, professional_id=professional_id,
        descripcion=payload.descripcion, pieza=payload.pieza,
        costo=costo or Decimal(0), precio=precio or Decimal(0),
        estado="solicitado", fecha_entrega=payload.fecha_entrega, notas=payload.notas,
    )
    db.add(o)
    await db.commit()
    await db.refresh(o)
    return await _order_out(db, o)


@router.patch("/ordenes/{oid}", response_model=LabOrderOut)
async def editar_orden(
    oid: uuid.UUID,
    payload: LabOrderUpdate,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.LABORATORIOS, Action.EDITAR)),
) -> LabOrderOut:
    cid = _clinic_id(ctx)
    o = await _own_order(db, cid, oid)
    if o.estado in ("terminado", "cancelado"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"La orden está {o.estado} y no se puede editar")
    if payload.descripcion is not None:
        o.descripcion = payload.descripcion
    if payload.pieza is not None:
        o.pieza = payload.pieza
    if payload.costo is not None:
        o.costo = Decimal(str(payload.costo))
    if payload.precio is not None:
        o.precio = Decimal(str(payload.precio))
    if payload.fecha_entrega is not None:
        o.fecha_entrega = payload.fecha_entrega
    if payload.notas is not None:
        o.notas = payload.notas
    await db.commit()
    await db.refresh(o)
    return await _order_out(db, o)


@router.patch("/ordenes/{oid}/estado", response_model=LabOrderOut)
async def cambiar_estado(
    oid: uuid.UUID,
    payload: LabOrderEstadoIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.LABORATORIOS, Action.EDITAR)),
) -> LabOrderOut:
    cid = _clinic_id(ctx)
    o = await _own_order(db, cid, oid)
    if payload.estado not in _TRANSICIONES.get(o.estado, set()):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"No se puede pasar de '{o.estado}' a '{payload.estado}'")
    o.estado = payload.estado
    await db.commit()
    await db.refresh(o)
    return await _order_out(db, o)


@router.post("/ordenes/{oid}/pagar", response_model=LabOrderOut)
async def pagar_orden(
    oid: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.LABORATORIOS, Action.EDITAR)),
) -> LabOrderOut:
    cid = _clinic_id(ctx)
    o = await _own_order(db, cid, oid)
    if o.estado == "cancelado":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Una orden cancelada no se paga")
    if o.pagado:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "La orden ya está pagada")
    o.pagado = True
    o.pagado_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(o)
    return await _order_out(db, o)


@router.get("/cuentas-por-pagar", response_model=list[CuentaPorPagarOut])
async def cuentas_por_pagar(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.LABORATORIOS, Action.VER)),
) -> list[CuentaPorPagarOut]:
    """Saldo pendiente por laboratorio (57.6): órdenes no pagadas y no
    canceladas, agrupadas por lab."""
    cid = _clinic_id(ctx)
    rows = (
        await db.execute(
            select(LabOrder.lab_id, func.count(LabOrder.id), func.coalesce(func.sum(LabOrder.costo), 0))
            .where(
                LabOrder.clinic_id == cid, LabOrder.deleted_at.is_(None),
                LabOrder.pagado.is_(False), LabOrder.estado != "cancelado",
            )
            .group_by(LabOrder.lab_id)
        )
    ).all()
    out: list[CuentaPorPagarOut] = []
    for lab_id, cant, total in rows:
        lab = await db.get(DentalLab, lab_id)
        out.append(CuentaPorPagarOut(lab_id=lab_id, lab_nombre=lab.nombre if lab else "", cantidad_ordenes=cant, total=float(total)))
    out.sort(key=lambda c: c.total, reverse=True)
    return out
