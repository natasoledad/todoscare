"""Reportería / BI (punto 68) — visión Empresa/Cliente.

Biblioteca de reportes por categoría (68.14), KPIs de agenda —ocupación,
no-show (68.8/68.10) y tiempo de espera (68.12)— y export a CSV UTF-8 para BI
(68.17). Todo se calcula sobre datos ya existentes; sin tablas nuevas salvo
las marcas de tiempo de espera de la cita.
"""

import csv
import io
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.catalog import CatalogItem
from app.models.finance import CashPayment
from app.models.identity import User
from app.models.patient import Patient
from app.models.scheduling import Appointment, AvailabilityBlock
from app.rbac.deps import require
from app.rbac.permissions import Action, Resource
from app.schemas.reportes import AgendaKpisOut, ReporteItem
from app.tenancy.context import TenantContext

router = APIRouter(prefix="/empresa/reportes", tags=["reportes"])

# Biblioteca de reportes por categoría (68.14).
BIBLIOTECA = [
    ReporteItem(id="agenda", nombre="Citas del período", categoria="Agenda", descripcion="Listado de citas con estado, profesional y paciente.", exportable=True),
    ReporteItem(id="no_show", nombre="Inasistencias (no-show)", categoria="Agenda", descripcion="Citas marcadas como no-show en el período.", exportable=True),
    ReporteItem(id="gastos", nombre="Gastos de caja", categoria="Finanzas", descripcion="Egresos registrados en caja en el período.", exportable=True),
    ReporteItem(id="pagos", nombre="Pagos recibidos", categoria="Finanzas", descripcion="Pagos de caja recibidos en el período.", exportable=True),
]
_IDS = {r.id for r in BIBLIOTECA}


def _clinic_id(ctx: TenantContext) -> uuid.UUID:
    ids = ctx.clinic_ids()
    if not ids:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "La cuenta no tiene una clínica asignada")
    return next(iter(ids))


def _minutos(lo: datetime, hi: datetime) -> float:
    return max(0.0, (hi - lo).total_seconds() / 60.0)


@router.get("", response_model=list[ReporteItem])
async def biblioteca(
    ctx: TenantContext = Depends(require(Resource.CLINIC_AGENDAS, Action.VER)),
) -> list[ReporteItem]:
    return BIBLIOTECA


@router.get("/agenda-kpis", response_model=AgendaKpisOut)
async def agenda_kpis(
    dias: int = 30,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CLINIC_AGENDAS, Action.VER)),
) -> AgendaKpisOut:
    cid = _clinic_id(ctx)
    dias = max(1, min(dias, 365))
    now = datetime.now(timezone.utc)
    desde = now - timedelta(days=dias)
    # Se incluye todo el día de hoy (las citas de hoy pueden estar programadas
    # más tarde que la hora actual): el período es [desde, fin de hoy].
    fin = now.replace(hour=23, minute=59, second=59, microsecond=0)

    citas = (
        await db.execute(
            select(Appointment).where(
                Appointment.clinic_id == cid, Appointment.deleted_at.is_(None),
            )
        )
    ).scalars().all()
    citas = [c for c in citas if c.slot.lower is not None and desde <= c.slot.lower <= fin]

    activas = [c for c in citas if c.estado != "cancelada"]
    completadas = sum(1 for c in citas if c.estado == "completada")
    no_shows = sum(1 for c in citas if c.estado == "no_show")
    base_nsh = completadas + no_shows

    appt_min = sum(_minutos(c.slot.lower, c.slot.upper) for c in activas)

    blocks = (
        await db.execute(
            select(AvailabilityBlock).where(AvailabilityBlock.clinic_id == cid, AvailabilityBlock.deleted_at.is_(None))
        )
    ).scalars().all()
    disp_min = 0.0
    for b in blocks:
        lo = max(b.rango.lower, desde)
        hi = min(b.rango.upper, fin)
        if lo < hi:
            disp_min += _minutos(lo, hi)

    esperas = [_minutos(c.sala_espera_at, c.atencion_at) for c in citas if c.sala_espera_at and c.atencion_at and c.atencion_at >= c.sala_espera_at]

    return AgendaKpisOut(
        dias=dias,
        total_citas=len(activas),
        completadas=completadas,
        no_shows=no_shows,
        no_show_pct=round(no_shows / base_nsh, 4) if base_nsh else 0.0,
        ocupacion_pct=round(min(appt_min / disp_min, 1.0), 4) if disp_min else 0.0,
        tiempo_espera_prom_min=round(sum(esperas) / len(esperas), 1) if esperas else 0.0,
        atendidas_con_espera=len(esperas),
    )


def _csv_response(nombre: str, columnas: list[str], filas: list[list]) -> Response:
    buf = io.StringIO()
    buf.write("﻿")  # BOM para que Excel abra el UTF-8 correctamente (68.17)
    w = csv.writer(buf)
    w.writerow(columnas)
    for f in filas:
        w.writerow(f)
    return Response(
        content=buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nombre}.csv"'},
    )


@router.get("/{report_id}/export")
async def exportar(
    report_id: str,
    dias: int = 30,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CLINIC_AGENDAS, Action.VER)),
) -> Response:
    if report_id not in _IDS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reporte no encontrado")
    cid = _clinic_id(ctx)
    dias = max(1, min(dias, 365))
    now = datetime.now(timezone.utc)
    desde = now - timedelta(days=dias)
    fin = now.replace(hour=23, minute=59, second=59, microsecond=0)

    if report_id in ("agenda", "no_show"):
        citas = (await db.execute(select(Appointment).where(Appointment.clinic_id == cid, Appointment.deleted_at.is_(None)))).scalars().all()
        citas = [c for c in citas if c.slot.lower and desde <= c.slot.lower <= fin]
        if report_id == "no_show":
            citas = [c for c in citas if c.estado == "no_show"]
        citas.sort(key=lambda c: c.slot.lower)
        filas = []
        for c in citas:
            pac = await db.get(Patient, c.patient_id)
            pac_u = await db.get(User, pac.user_id) if pac else None
            prof = await db.get(User, c.professional_id)
            svc = await db.get(CatalogItem, c.service_id) if c.service_id else None
            filas.append([
                c.slot.lower.strftime("%Y-%m-%d %H:%M"), c.estado,
                pac_u.nombre if pac_u else "", prof.nombre if prof else "", svc.nombre if svc else "",
            ])
        return _csv_response(f"{report_id}_{dias}d", ["Fecha", "Estado", "Paciente", "Profesional", "Servicio"], filas)

    # finanzas: pagos / gastos de caja
    tipo = "gasto" if report_id == "gastos" else "pago"
    pagos = (
        await db.execute(
            select(CashPayment).where(
                CashPayment.clinic_id == cid, CashPayment.deleted_at.is_(None), CashPayment.tipo == tipo,
                CashPayment.anulado.is_(False), CashPayment.created_at >= desde,
            ).order_by(CashPayment.created_at)
        )
    ).scalars().all()
    filas = [[p.created_at.strftime("%Y-%m-%d %H:%M"), p.medio, float(p.monto), p.glosa or ""] for p in pagos]
    return _csv_response(f"{report_id}_{dias}d", ["Fecha", "Medio", "Monto", "Glosa"], filas)
