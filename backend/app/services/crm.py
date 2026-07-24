"""CRM / gestión financiera multi-clínica (Spec CRM Clínicas).

Principio rector de la spec (§1): *fuente única de verdad*. El CRM **no
almacena cifras propias, las calcula** a partir del ledger inmutable y de
la agenda. Así el consolidado del Administrador y el KPI de una clínica
nunca divergen. Este módulo es puramente de lectura/cálculo, salvo la
conciliación de liquidaciones (§5.2), que marca un split como pagado y
asienta el egreso inmutable correspondiente en el ledger.

Alcance (§2): el mismo cálculo, distinto `scope`. `scope=None` =>
plataforma completa (super_admin); `scope={clinic_id, ...}` => una o
varias clínicas (clinic_admin / empresa acotada a la suya).

Varias fórmulas dependen de definiciones que la spec deja abiertas (§10:
"costos directos", período por defecto, tratamiento de reembolsos). Se
toman los supuestos más defendibles con los datos existentes y se marcan
con comentarios `# SUPUESTO` para revisarlos cuando producto los cierre.
"""

import uuid
from datetime import date, datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import cast, func, select
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import CatalogItem
from app.models.finance import LedgerEntry, PaymentSplit
from app.models.identity import User
from app.models.marketing import MarketingCampaign
from app.models.patient import Patient
from app.models.scheduling import Appointment, AvailabilityBlock
from app.models.tenant import Clinic
from app.services.medico import audit
from app.tenancy.context import TenantContext

CANALES = {"google_ads", "meta_ads", "instagram", "email", "whatsapp", "seo", "referidos"}

Scope = set[uuid.UUID] | None


# ─────────────────────────── período ───────────────────────────
def month_bounds(period: str | None) -> tuple[date, date]:
    """(inicio inclusivo, fin exclusivo) del mes. `period` = 'YYYY-MM'.
    # SUPUESTO (§10): período por defecto = mes calendario en curso."""
    if period:
        try:
            year, month = (int(x) for x in period.split("-", 1))
            date(year, month, 1)  # valida
        except (ValueError, TypeError) as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "period inválido, use 'YYYY-MM'") from exc
    else:
        today = datetime.now(timezone.utc).date()
        year, month = today.year, today.month
    start = date(year, month, 1)
    end = date(year + (1 if month == 12 else 0), 1 if month == 12 else month + 1, 1)
    return start, end


def prev_month_bounds(start: date) -> tuple[date, date]:
    y, m = (start.year - 1, 12) if start.month == 1 else (start.year, start.month - 1)
    return date(y, m, 1), start


def _scoped(col, scope: Scope):
    """`col IN scope`, o `col IS NOT NULL` (todos los tenants) si scope=None."""
    return col.in_(scope) if scope is not None else col.isnot(None)


# ─────────────────────────── KPIs atómicos ───────────────────────────
async def _ingresos(db: AsyncSession, scope: Scope, start: date, end: date, clinic_id: uuid.UUID | None = None) -> float:
    q = select(func.coalesce(func.sum(LedgerEntry.monto), 0)).where(
        LedgerEntry.tipo == "ingreso",
        LedgerEntry.deleted_at.is_(None),
        func.date(LedgerEntry.created_at) >= start,
        func.date(LedgerEntry.created_at) < end,
        _scoped(LedgerEntry.clinic_id, scope),
    )
    if clinic_id is not None:
        q = q.where(LedgerEntry.clinic_id == clinic_id)
    return float((await db.execute(q)).scalar_one())


async def _ingresos_atenciones(db: AsyncSession, scope: Scope, start: date, end: date, clinic_id: uuid.UUID | None = None) -> float:
    # Solo los ingresos ligados a una atención (ref 'appointment:<id>'); es
    # el numerador correcto del ticket promedio (excluye ingresos manuales o
    # de otras fuentes que no son atenciones).
    q = select(func.coalesce(func.sum(LedgerEntry.monto), 0)).where(
        LedgerEntry.tipo == "ingreso",
        LedgerEntry.deleted_at.is_(None),
        LedgerEntry.ref.like("appointment:%"),
        func.date(LedgerEntry.created_at) >= start,
        func.date(LedgerEntry.created_at) < end,
        _scoped(LedgerEntry.clinic_id, scope),
    )
    if clinic_id is not None:
        q = q.where(LedgerEntry.clinic_id == clinic_id)
    return float((await db.execute(q)).scalar_one())


async def _n_atenciones(db: AsyncSession, scope: Scope, start: date, end: date, clinic_id: uuid.UUID | None = None) -> int:
    # Cada cierre de atención genera exactamente un asiento 'ingreso'
    # ligado a la cita (ref 'appointment:<id>'); ese es el denominador del
    # ticket promedio (§3). Los ingresos 'seed'/manuales no cuentan como
    # atención.
    q = select(func.count(LedgerEntry.id)).where(
        LedgerEntry.tipo == "ingreso",
        LedgerEntry.deleted_at.is_(None),
        LedgerEntry.ref.like("appointment:%"),
        func.date(LedgerEntry.created_at) >= start,
        func.date(LedgerEntry.created_at) < end,
        _scoped(LedgerEntry.clinic_id, scope),
    )
    if clinic_id is not None:
        q = q.where(LedgerEntry.clinic_id == clinic_id)
    return int((await db.execute(q)).scalar_one())


async def _costos_directos(db: AsyncSession, scope: Scope, start: date, end: date, clinic_id: uuid.UUID | None = None) -> float:
    # SUPUESTO (§10, "costos directos" a definir): se usa el split devengado
    # a los profesionales del período como costo directo. Es el único costo
    # variable modelado hoy; centros de costo llegan cuando finanzas los
    # defina.
    q = select(func.coalesce(func.sum(PaymentSplit.monto), 0)).where(
        PaymentSplit.deleted_at.is_(None),
        func.date(PaymentSplit.created_at) >= start,
        func.date(PaymentSplit.created_at) < end,
        _scoped(PaymentSplit.clinic_id, scope),
    )
    if clinic_id is not None:
        q = q.where(PaymentSplit.clinic_id == clinic_id)
    return float((await db.execute(q)).scalar_one())


async def _por_liquidar(db: AsyncSession, scope: Scope, start: date, end: date, clinic_id: uuid.UUID | None = None) -> float:
    q = select(func.coalesce(func.sum(PaymentSplit.monto), 0)).where(
        PaymentSplit.estado == "pendiente",
        PaymentSplit.deleted_at.is_(None),
        func.date(PaymentSplit.created_at) >= start,
        func.date(PaymentSplit.created_at) < end,
        _scoped(PaymentSplit.clinic_id, scope),
    )
    if clinic_id is not None:
        q = q.where(PaymentSplit.clinic_id == clinic_id)
    return float((await db.execute(q)).scalar_one())


async def _cuentas_por_cobrar(db: AsyncSession, scope: Scope, clinic_id: uuid.UUID | None = None) -> float:
    # CxC = Σ facturado − Σ cobrado (§3). Los asientos 'facturado'/'cobrado'
    # los origina el flujo de aseguradoras (Fase 7); hasta entonces es 0.
    # No se filtra por período: una CxC es un saldo, no un flujo del mes.
    facturado = select(func.coalesce(func.sum(LedgerEntry.monto), 0)).where(
        LedgerEntry.tipo == "facturado", LedgerEntry.deleted_at.is_(None), _scoped(LedgerEntry.clinic_id, scope)
    )
    cobrado = select(func.coalesce(func.sum(LedgerEntry.monto), 0)).where(
        LedgerEntry.tipo == "cobrado", LedgerEntry.deleted_at.is_(None), _scoped(LedgerEntry.clinic_id, scope)
    )
    if clinic_id is not None:
        facturado = facturado.where(LedgerEntry.clinic_id == clinic_id)
        cobrado = cobrado.where(LedgerEntry.clinic_id == clinic_id)
    return float((await db.execute(facturado)).scalar_one()) - float((await db.execute(cobrado)).scalar_one())


async def _ocupacion(db: AsyncSession, scope: Scope, start: date, end: date, clinic_id: uuid.UUID | None = None) -> float:
    """slots reservados / slots disponibles (§3), medido en tiempo: Σ
    duración de citas no canceladas sobre Σ duración de bloques de agenda.
    0 si no hay disponibilidad publicada en el período."""
    dur = func.extract("epoch", func.upper(Appointment.slot) - func.lower(Appointment.slot))
    rq = select(func.coalesce(func.sum(dur), 0)).where(
        Appointment.deleted_at.is_(None),
        Appointment.estado != "cancelada",
        func.date(func.lower(Appointment.slot)) >= start,
        func.date(func.lower(Appointment.slot)) < end,
        _scoped(Appointment.clinic_id, scope),
    )
    bdur = func.extract("epoch", func.upper(AvailabilityBlock.rango) - func.lower(AvailabilityBlock.rango))
    aq = select(func.coalesce(func.sum(bdur), 0)).where(
        AvailabilityBlock.deleted_at.is_(None),
        func.date(func.lower(AvailabilityBlock.rango)) >= start,
        func.date(func.lower(AvailabilityBlock.rango)) < end,
        _scoped(AvailabilityBlock.clinic_id, scope),
    )
    if clinic_id is not None:
        rq = rq.where(Appointment.clinic_id == clinic_id)
        aq = aq.where(AvailabilityBlock.clinic_id == clinic_id)
    reservado = float((await db.execute(rq)).scalar_one())
    disponible = float((await db.execute(aq)).scalar_one())
    return round(reservado / disponible, 4) if disponible > 0 else 0.0


def _variacion(actual: float, anterior: float) -> float | None:
    """(actual − anterior) / anterior (§3). None si no hay base anterior."""
    if anterior == 0:
        return None
    return round((actual - anterior) / anterior, 4)


def _margen(ingresos: float, costos: float) -> float | None:
    if ingresos == 0:
        return None
    return round((ingresos - costos) / ingresos, 4)


# ─────────────────────────── marketing / captación ───────────────────────────
# Métricas de crecimiento sobre el mismo ledger. El gasto de marketing se
# asienta como LedgerEntry tipo='gasto_marketing' (egreso); no se inventan
# cifras. Definiciones (borrador, a validar con el equipo de growth):
#   CAC  = gasto de marketing del período / clientes nuevos del período
#   LTV  = ingreso histórico de la clínica / total de pacientes (ARPU
#          histórico como proxy del valor de vida)
#   LTV:CAC = retorno de la inversión en captación (salud del negocio; >3 sano)
#   ROAS = ingresos del período / gasto de marketing del período
async def _gasto_marketing(db: AsyncSession, scope: Scope, start: date, end: date, clinic_id: uuid.UUID | None = None) -> float:
    q = select(func.coalesce(func.sum(LedgerEntry.monto), 0)).where(
        LedgerEntry.tipo == "gasto_marketing",
        LedgerEntry.deleted_at.is_(None),
        func.date(LedgerEntry.created_at) >= start,
        func.date(LedgerEntry.created_at) < end,
        _scoped(LedgerEntry.clinic_id, scope),
    )
    if clinic_id is not None:
        q = q.where(LedgerEntry.clinic_id == clinic_id)
    return float((await db.execute(q)).scalar_one())


async def _nuevos_pacientes(db: AsyncSession, scope: Scope, start: date, end: date, clinic_id: uuid.UUID | None = None) -> int:
    q = select(func.count(Patient.id)).where(
        Patient.deleted_at.is_(None),
        func.date(Patient.created_at) >= start,
        func.date(Patient.created_at) < end,
        _scoped(Patient.clinic_id, scope),
    )
    if clinic_id is not None:
        q = q.where(Patient.clinic_id == clinic_id)
    return int((await db.execute(q)).scalar_one())


async def _marketing(db: AsyncSession, scope: Scope, start: date, end: date, ingresos_periodo: float, clinic_id: uuid.UUID | None = None) -> dict:
    gasto = await _gasto_marketing(db, scope, start, end, clinic_id=clinic_id)
    nuevos = await _nuevos_pacientes(db, scope, start, end, clinic_id=clinic_id)

    # LTV = ingreso histórico / total de pacientes (ARPU histórico).
    hist_q = select(func.coalesce(func.sum(LedgerEntry.monto), 0)).where(LedgerEntry.tipo == "ingreso", LedgerEntry.deleted_at.is_(None), _scoped(LedgerEntry.clinic_id, scope))
    pac_q = select(func.count(Patient.id)).where(Patient.deleted_at.is_(None), _scoped(Patient.clinic_id, scope))
    if clinic_id is not None:
        hist_q = hist_q.where(LedgerEntry.clinic_id == clinic_id)
        pac_q = pac_q.where(Patient.clinic_id == clinic_id)
    ingresos_hist = float((await db.execute(hist_q)).scalar_one())
    total_pac = int((await db.execute(pac_q)).scalar_one())

    cac = round(gasto / nuevos, 2) if nuevos else None
    ltv = round(ingresos_hist / total_pac, 2) if total_pac else None
    ltv_cac = round(ltv / cac, 2) if (ltv is not None and cac) else None
    roas = round(ingresos_periodo / gasto, 2) if gasto else None
    return {
        "gasto_marketing": gasto,
        "nuevos_pacientes": nuevos,
        "cac": cac,
        "ltv": ltv,
        "ltv_cac_ratio": ltv_cac,
        "roas": roas,
    }


# ─────────────────────────── marketing digital: campañas ───────────────────────────
# Elemento de gestión (no solo cálculo): campañas por canal. El gasto de cada
# campaña se asienta en el ledger (tipo='gasto_marketing', ref 'campana:<id>'),
# así el CAC/ROAS de la clínica lo reflejan automáticamente.
def _campana_out(c: MarketingCampaign, conversiones_reales: int = 0) -> dict:
    gasto = float(c.gasto)
    leads = int(c.leads)
    conv = int(c.conversiones)
    return {
        "id": c.id,
        "clinic_id": c.clinic_id,
        "nombre": c.nombre,
        "canal": c.canal,
        "estado": c.estado,
        "presupuesto": float(c.presupuesto),
        "gasto": gasto,
        "leads": leads,
        "conversiones": conv,
        "conversiones_reales": conversiones_reales,  # pacientes atribuidos de verdad
        "fecha_inicio": c.fecha_inicio,
        "fecha_fin": c.fecha_fin,
        # métricas derivadas por campaña
        "cpl": round(gasto / leads, 2) if leads else None,  # costo por lead
        "cac": round(gasto / conv, 2) if conv else None,  # costo por adquisición (meta)
        "cac_real": round(gasto / conversiones_reales, 2) if conversiones_reales else None,
        "conversion_rate": round(conv / leads, 4) if leads else None,
        "presupuesto_usado": round(gasto / float(c.presupuesto), 4) if float(c.presupuesto) else None,
    }


async def campanas(db: AsyncSession, ctx: TenantContext, clinic_id: uuid.UUID | None = None) -> dict:
    """Lista campañas del alcance + un resumen agregado. Si clinic_id se
    pasa (empresa), se acota a esa clínica (validando acceso)."""
    scope = ctx.clinic_ids()
    if clinic_id is not None and not ctx.has_access_to_clinic(clinic_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Sin acceso a esa clínica")
    q = select(MarketingCampaign).where(MarketingCampaign.deleted_at.is_(None))
    if clinic_id is not None:
        q = q.where(MarketingCampaign.clinic_id == clinic_id)
    elif scope is not None:
        q = q.where(MarketingCampaign.clinic_id.in_(scope))
    rows = (await db.execute(q.order_by(MarketingCampaign.created_at.desc()))).scalars().all()
    # Conversiones reales por campaña = pacientes atribuidos (una sola query).
    conv_map = dict(
        (
            await db.execute(
                select(Patient.origen_campana_id, func.count(Patient.id))
                .where(Patient.origen_campana_id.isnot(None), Patient.deleted_at.is_(None))
                .group_by(Patient.origen_campana_id)
            )
        ).all()
    )
    items = [_campana_out(c, conversiones_reales=int(conv_map.get(c.id, 0))) for c in rows]
    activas = [c for c in rows if c.estado == "activa"]
    tot_gasto = sum(float(c.gasto) for c in rows)
    tot_conv = sum(int(c.conversiones) for c in rows)
    tot_leads = sum(int(c.leads) for c in rows)
    tot_conv_real = sum(int(conv_map.get(c.id, 0)) for c in rows)
    resumen = {
        "campanas": len(rows),
        "activas": len(activas),
        "inversion": round(sum(float(c.presupuesto) for c in rows), 2),
        "gasto": round(tot_gasto, 2),
        "leads": tot_leads,
        "conversiones": tot_conv,
        "conversiones_reales": tot_conv_real,
        "cac_promedio": round(tot_gasto / tot_conv, 2) if tot_conv else None,
        "cac_real_promedio": round(tot_gasto / tot_conv_real, 2) if tot_conv_real else None,
        "conversion_rate": round(tot_conv / tot_leads, 4) if tot_leads else None,
    }
    return {"resumen": resumen, "items": items}


async def crear_campana(
    db: AsyncSession,
    ctx: TenantContext,
    *,
    clinic_id: uuid.UUID,
    nombre: str,
    canal: str,
    presupuesto: float,
    gasto: float = 0,
    leads: int = 0,
    conversiones: int = 0,
    fecha_inicio: date | None = None,
    fecha_fin: date | None = None,
) -> dict:
    if not ctx.has_access_to_clinic(clinic_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Sin acceso a esa clínica")
    if canal not in CANALES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"canal inválido; usa uno de {sorted(CANALES)}")
    if conversiones > leads:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "conversiones no puede superar a leads")
    camp = MarketingCampaign(
        clinic_id=clinic_id, nombre=nombre, canal=canal, presupuesto=presupuesto, gasto=0, leads=leads, conversiones=conversiones, fecha_inicio=fecha_inicio, fecha_fin=fecha_fin
    )
    db.add(camp)
    await db.flush()
    if gasto and gasto > 0:
        await _registrar_gasto_campana(db, camp, gasto)
    audit(db, ctx, clinic_id=clinic_id, accion="crear_campana", recurso=f"campana:{camp.id}", despues={"canal": canal, "presupuesto": presupuesto})
    await db.commit()
    await db.refresh(camp)
    return _campana_out(camp)


async def actualizar_campana(
    db: AsyncSession,
    ctx: TenantContext,
    campaign_id: uuid.UUID,
    *,
    estado: str | None = None,
    leads: int | None = None,
    conversiones: int | None = None,
    gasto_adicional: float | None = None,
) -> dict:
    camp = (await db.execute(select(MarketingCampaign).where(MarketingCampaign.id == campaign_id, MarketingCampaign.deleted_at.is_(None)))).scalar_one_or_none()
    if camp is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaña no encontrada")
    if not ctx.has_access_to_clinic(camp.clinic_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Sin acceso a esa campaña")
    if estado is not None:
        if estado not in {"activa", "pausada", "finalizada"}:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "estado inválido")
        camp.estado = estado
    if leads is not None:
        camp.leads = leads
    if conversiones is not None:
        camp.conversiones = conversiones
    if int(camp.conversiones) > int(camp.leads):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "conversiones no puede superar a leads")
    if gasto_adicional and gasto_adicional > 0:
        await _registrar_gasto_campana(db, camp, gasto_adicional)
    audit(db, ctx, clinic_id=camp.clinic_id, accion="actualizar_campana", recurso=f"campana:{camp.id}", despues={"estado": camp.estado})
    await db.commit()
    await db.refresh(camp)
    return _campana_out(camp)


async def eliminar_campana(db: AsyncSession, ctx: TenantContext, campaign_id: uuid.UUID) -> None:
    camp = (await db.execute(select(MarketingCampaign).where(MarketingCampaign.id == campaign_id, MarketingCampaign.deleted_at.is_(None)))).scalar_one_or_none()
    if camp is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaña no encontrada")
    if not ctx.has_access_to_clinic(camp.clinic_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Sin acceso a esa campaña")
    await db.delete(camp)  # baja lógica (el gasto ya asentado en el ledger se conserva)
    await db.commit()


async def atribucion_campana(db: AsyncSession, ctx: TenantContext, campaign_id: uuid.UUID) -> dict:
    """Atribución real: pacientes que se registraron con esta campaña, los
    ingresos que generaron (vía sus atenciones en el ledger) y el CAC/ROI
    reales — cierra el embudo campaña → paciente → ingreso."""
    camp = (await db.execute(select(MarketingCampaign).where(MarketingCampaign.id == campaign_id, MarketingCampaign.deleted_at.is_(None)))).scalar_one_or_none()
    if camp is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaña no encontrada")
    if not ctx.has_access_to_clinic(camp.clinic_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Sin acceso a esa campaña")

    rows = (
        await db.execute(
            select(Patient.id, User.nombre).join(User, User.id == Patient.user_id).where(Patient.origen_campana_id == campaign_id, Patient.deleted_at.is_(None))
        )
    ).all()
    pids = [pid for pid, _ in rows]
    conv_reales = len(pids)

    ingresos_atrib = 0.0
    if pids:
        appt_id = cast(func.split_part(LedgerEntry.ref, ":", 2), PgUUID(as_uuid=True))
        q = (
            select(func.coalesce(func.sum(LedgerEntry.monto), 0))
            .select_from(LedgerEntry)
            .join(Appointment, Appointment.id == appt_id)
            .where(LedgerEntry.tipo == "ingreso", LedgerEntry.ref.like("appointment:%"), LedgerEntry.deleted_at.is_(None), Appointment.patient_id.in_(pids))
        )
        ingresos_atrib = float((await db.execute(q)).scalar_one())

    gasto = float(camp.gasto)
    return {
        "campaign_id": camp.id,
        "nombre": camp.nombre,
        "canal": camp.canal,
        "gasto": gasto,
        "leads": int(camp.leads),
        "conversiones_meta": int(camp.conversiones),
        "conversiones_reales": conv_reales,
        "ingresos_atribuidos": round(ingresos_atrib, 2),
        "cac_real": round(gasto / conv_reales, 2) if conv_reales else None,
        "roi_real": round((ingresos_atrib - gasto) / gasto, 4) if gasto else None,  # (ingreso − gasto) / gasto
        "roas_real": round(ingresos_atrib / gasto, 2) if gasto else None,  # ingreso / gasto
        "pacientes": [nombre for _, nombre in rows],
    }


async def _registrar_gasto_campana(db: AsyncSession, camp: MarketingCampaign, monto: float) -> None:
    """Asienta el gasto en el ledger (gasto_marketing) e incrementa el
    acumulado cacheado de la campaña. El ledger es la fuente de verdad del
    CAC/ROAS; el campo `gasto` es una caché para mostrar por campaña."""
    db.add(LedgerEntry(clinic_id=camp.clinic_id, tipo="gasto_marketing", monto=monto, ref=f"campana:{camp.id}"))
    camp.gasto = float(camp.gasto) + float(monto)


# ─────────────────────────── pantallas ───────────────────────────
async def consolidado(db: AsyncSession, ctx: TenantContext, period: str | None) -> dict:
    """Panel consolidado + lista por clínica (§4). Alcance según ctx."""
    scope = ctx.clinic_ids()
    start, end = month_bounds(period)
    p_start, p_end = prev_month_bounds(start)

    ingresos_tot = await _ingresos(db, scope, start, end)
    ingresos_prev = await _ingresos(db, scope, p_start, p_end)

    n_clinicas = (
        await db.execute(select(func.count(Clinic.id)).where(Clinic.deleted_at.is_(None), _scoped(Clinic.id, scope)))
    ).scalar_one()
    n_pacientes = (
        await db.execute(select(func.count(Patient.id)).where(Patient.deleted_at.is_(None), _scoped(Patient.clinic_id, scope)))
    ).scalar_one()

    # Lista por clínica: ingresos, margen ▲/▼, pacientes (§4).
    clinicas = (
        await db.execute(select(Clinic).where(Clinic.deleted_at.is_(None), _scoped(Clinic.id, scope)).order_by(Clinic.razon_social))
    ).scalars().all()
    filas = []
    for c in clinicas:
        ing = await _ingresos(db, scope, start, end, clinic_id=c.id)
        ing_prev = await _ingresos(db, scope, p_start, p_end, clinic_id=c.id)
        costos = await _costos_directos(db, scope, start, end, clinic_id=c.id)
        pac = (
            await db.execute(select(func.count(Patient.id)).where(Patient.deleted_at.is_(None), Patient.clinic_id == c.id))
        ).scalar_one()
        filas.append(
            {
                "clinic_id": c.id,
                "razon_social": c.razon_social,
                "pais": c.pais,
                "ingresos": ing,
                "margen": _margen(ing, costos),
                "variacion": _variacion(ing, ing_prev),
                "pacientes": pac,
            }
        )

    return {
        "alcance": "plataforma" if scope is None else "clínica",
        "period": start.strftime("%Y-%m"),
        "ingresos_totales": ingresos_tot,
        "variacion": _variacion(ingresos_tot, ingresos_prev),
        "n_clinicas": n_clinicas,
        "n_pacientes": n_pacientes,
        "clinicas": filas,
    }


async def detalle_clinica(db: AsyncSession, ctx: TenantContext, clinic_id: uuid.UUID, period: str | None) -> dict:
    """Detalle de una clínica: KPIs, ocupación, ingresos por servicio (§4)."""
    if not ctx.has_access_to_clinic(clinic_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Sin acceso a esa clínica")
    scope = ctx.clinic_ids()
    start, end = month_bounds(period)
    p_start, p_end = prev_month_bounds(start)

    clinic = (await db.execute(select(Clinic).where(Clinic.id == clinic_id, Clinic.deleted_at.is_(None)))).scalar_one_or_none()
    if clinic is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Clínica no encontrada")

    ingresos = await _ingresos(db, scope, start, end, clinic_id=clinic_id)
    ingresos_prev = await _ingresos(db, scope, p_start, p_end, clinic_id=clinic_id)
    costos = await _costos_directos(db, scope, start, end, clinic_id=clinic_id)
    n_atenciones = await _n_atenciones(db, scope, start, end, clinic_id=clinic_id)
    ingresos_atn = await _ingresos_atenciones(db, scope, start, end, clinic_id=clinic_id)

    # Ingresos por servicio: se agrupa el asiento 'ingreso' por el servicio
    # de su cita (ledger.ref = 'appointment:<uuid>' → catalog_items).
    appt_id = cast(func.split_part(LedgerEntry.ref, ":", 2), PgUUID(as_uuid=True))
    por_servicio_rows = (
        await db.execute(
            select(CatalogItem.nombre, func.coalesce(func.sum(LedgerEntry.monto), 0))
            .join(Appointment, Appointment.id == appt_id)
            .join(CatalogItem, CatalogItem.id == Appointment.service_id)
            .where(
                LedgerEntry.tipo == "ingreso",
                LedgerEntry.deleted_at.is_(None),
                LedgerEntry.ref.like("appointment:%"),
                LedgerEntry.clinic_id == clinic_id,
                func.date(LedgerEntry.created_at) >= start,
                func.date(LedgerEntry.created_at) < end,
            )
            .group_by(CatalogItem.nombre)
            .order_by(func.sum(LedgerEntry.monto).desc())
        )
    ).all()

    return {
        "clinic_id": clinic.id,
        "razon_social": clinic.razon_social,
        "pais": clinic.pais,
        "period": start.strftime("%Y-%m"),
        "ingresos": ingresos,
        "variacion": _variacion(ingresos, ingresos_prev),
        "margen": _margen(ingresos, costos),
        "ticket_promedio": round(ingresos_atn / n_atenciones, 2) if n_atenciones else 0.0,
        "n_atenciones": n_atenciones,
        "cuentas_por_cobrar": await _cuentas_por_cobrar(db, scope, clinic_id=clinic_id),
        "ocupacion": await _ocupacion(db, scope, start, end, clinic_id=clinic_id),
        "por_liquidar": await _por_liquidar(db, scope, start, end, clinic_id=clinic_id),
        "marketing": await _marketing(db, scope, start, end, ingresos, clinic_id=clinic_id),
        "ingresos_por_servicio": [{"servicio": nombre, "monto": float(monto)} for nombre, monto in por_servicio_rows],
    }


async def liquidaciones(db: AsyncSession, ctx: TenantContext, period: str | None) -> list[dict]:
    """Montos por liquidar por clínica/profesional (§4/§5.2). Solo splits
    pendientes del período, con nombre de clínica y prestador."""
    scope = ctx.clinic_ids()
    start, end = month_bounds(period)
    rows = (
        await db.execute(
            select(PaymentSplit, Clinic.razon_social, User.nombre)
            .join(Clinic, Clinic.id == PaymentSplit.clinic_id)
            .outerjoin(User, User.id == PaymentSplit.beneficiario_id)
            .where(
                PaymentSplit.estado == "pendiente",
                PaymentSplit.deleted_at.is_(None),
                func.date(PaymentSplit.created_at) >= start,
                func.date(PaymentSplit.created_at) < end,
                _scoped(PaymentSplit.clinic_id, scope),
            )
            .order_by(PaymentSplit.created_at.desc())
        )
    ).all()
    return [
        {
            "split_id": s.id,
            "clinic_id": s.clinic_id,
            "razon_social": razon_social,
            "prestador": prestador or "—",
            "monto": float(s.monto),
            "fecha": s.created_at,
            "estado": s.estado,
        }
        for s, razon_social, prestador in rows
    ]


async def conciliar(db: AsyncSession, ctx: TenantContext, split_id: uuid.UUID) -> dict:
    """Conciliación (§5.2): marca el split como pagado y asienta el egreso
    inmutable en el ledger. Idempotente-seguro: un split ya conciliado no se
    vuelve a asentar. Deja rastro auditado."""
    split = (await db.execute(select(PaymentSplit).where(PaymentSplit.id == split_id, PaymentSplit.deleted_at.is_(None)))).scalar_one_or_none()
    if split is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Liquidación no encontrada")
    if not ctx.has_access_to_clinic(split.clinic_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Sin acceso a esa clínica")
    if split.estado == "conciliado":
        raise HTTPException(status.HTTP_409_CONFLICT, "La liquidación ya fue conciliada")

    split.estado = "conciliado"
    split.conciliado_at = datetime.now(timezone.utc)
    # El asiento inmutable del pago al prestador (§9: "toda conciliación deja
    # asiento auditado").
    db.add(LedgerEntry(clinic_id=split.clinic_id, tipo="liquidacion_pagada", monto=split.monto, ref=f"split:{split.id}"))
    audit(db, ctx, clinic_id=split.clinic_id, accion="conciliar_liquidacion", recurso=f"split:{split.id}", despues={"monto": float(split.monto)})
    await db.commit()
    return {"split_id": split.id, "estado": split.estado, "conciliado_at": split.conciliado_at}


async def exportar_asientos(db: AsyncSession, ctx: TenantContext, period: str | None) -> list[dict]:
    """Exportación de asientos a ERP/contabilidad (§6 conector de salida).
    Solo Admin (RBAC §7). Devuelve el ledger del período, listo para
    serializar a CSV en el cliente."""
    scope = ctx.clinic_ids()
    start, end = month_bounds(period)
    rows = (
        await db.execute(
            select(LedgerEntry, Clinic.razon_social)
            .join(Clinic, Clinic.id == LedgerEntry.clinic_id)
            .where(
                LedgerEntry.deleted_at.is_(None),
                func.date(LedgerEntry.created_at) >= start,
                func.date(LedgerEntry.created_at) < end,
                _scoped(LedgerEntry.clinic_id, scope),
            )
            .order_by(LedgerEntry.created_at)
        )
    ).all()
    return [
        {
            "fecha": e.created_at,
            "clinica": razon_social,
            "tipo": e.tipo,
            "monto": float(e.monto),
            "moneda": e.moneda,
            "ref": e.ref,
        }
        for e, razon_social in rows
    ]
