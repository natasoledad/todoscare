"""Rol Aseguradora / Prestador (Spec Aseguradora Prestador).

El tercero pagador se conecta a la plataforma para definir convenios,
autorizar prestaciones y liquidar a las clínicas por las atenciones de sus
afiliados. A diferencia de los demás roles, su alcance NO es un tenant
clínico sino su propia entidad aseguradora: ve los convenios de SU insurer
(que pueden abarcar varias clínicas de la red), nunca los de otra
aseguradora (§3: "Datos de otras aseguradoras — No").

Principios de la spec aplicados aquí:
  · Mínimo dato clínico (§3): la ficha del afiliado expone solo lo
    estrictamente necesario para autorizar/liquidar, y todo acceso queda
    auditado.
  · Liquidaciones trazables en el ledger inmutable (§5.2/§8): generar una
    liquidación asienta 'facturado' y pagarla asienta 'cobrado', que son
    justamente los tipos que el CRM lee para las Cuentas por Cobrar.
"""

import uuid
from datetime import date, datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import CatalogItem
from app.models.clinical import MedicalRecord
from app.models.finance import LedgerEntry
from app.models.identity import User
from app.models.insurance import (
    Affiliate,
    Agreement,
    Arancel,
    Authorization,
    Insurer,
    Settlement,
)
from app.models.patient import Patient
from app.models.scheduling import Appointment
from app.models.tenant import Clinic
from app.services.medico import audit
from app.tenancy.context import TenantContext


def require_insurer(ctx: TenantContext) -> uuid.UUID:
    """La entidad aseguradora que representa el usuario. 400 si no está
    vinculado a ninguna (config incompleta)."""
    ids = ctx.insurer_ids()
    if not ids:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "La cuenta no está vinculada a ninguna aseguradora")
    return next(iter(ids))


async def _agreement_ids(db: AsyncSession, insurer_id: uuid.UUID) -> list[uuid.UUID]:
    return list(
        (await db.execute(select(Agreement.id).where(Agreement.insurer_id == insurer_id, Agreement.deleted_at.is_(None)))).scalars().all()
    )


async def _load_agreement(db: AsyncSession, ctx: TenantContext, agreement_id: uuid.UUID) -> Agreement:
    ag = (await db.execute(select(Agreement).where(Agreement.id == agreement_id, Agreement.deleted_at.is_(None)))).scalar_one_or_none()
    if ag is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Convenio no encontrado")
    if not ctx.has_access_to_insurer(ag.insurer_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Ese convenio es de otra aseguradora")
    return ag


# ─────────────────────────── inicio / KPIs (§4) ───────────────────────────
async def inicio(db: AsyncSession, ctx: TenantContext) -> dict:
    insurer_id = require_insurer(ctx)
    insurer = await db.get(Insurer, insurer_id)
    ag_ids = await _agreement_ids(db, insurer_id)
    today = datetime.now(timezone.utc).date()
    month_start = today.replace(day=1)

    afiliados = (await db.execute(select(func.count(Affiliate.id)).where(Affiliate.insurer_id == insurer_id, Affiliate.deleted_at.is_(None)))).scalar_one()
    pendientes = 0
    atenciones_mes = 0
    por_liquidar = 0.0
    if ag_ids:
        pendientes = (
            await db.execute(select(func.count(Authorization.id)).where(Authorization.agreement_id.in_(ag_ids), Authorization.estado == "pendiente", Authorization.deleted_at.is_(None)))
        ).scalar_one()
        atenciones_mes = (
            await db.execute(
                select(func.count(Authorization.id)).where(
                    Authorization.agreement_id.in_(ag_ids), Authorization.estado == "aprobada", Authorization.deleted_at.is_(None), func.date(Authorization.resuelto_en) >= month_start
                )
            )
        ).scalar_one()
        por_liquidar = float(
            (await db.execute(select(func.coalesce(func.sum(Settlement.monto), 0)).where(Settlement.agreement_id.in_(ag_ids), Settlement.estado == "pendiente", Settlement.deleted_at.is_(None)))).scalar_one()
        )

    return {
        "insurer_nombre": insurer.nombre if insurer else "—",
        "tipo": insurer.tipo if insurer else "—",
        "afiliados": afiliados,
        "autorizaciones_pendientes": pendientes,
        "atenciones_mes": atenciones_mes,
        "por_liquidar": por_liquidar,
    }


# ─────────────────────────── convenios y aranceles (§5.3) ───────────────────────────
async def convenios(db: AsyncSession, ctx: TenantContext) -> list[dict]:
    insurer_id = require_insurer(ctx)
    rows = (
        await db.execute(
            select(Agreement, Clinic.razon_social).join(Clinic, Clinic.id == Agreement.clinic_id).where(Agreement.insurer_id == insurer_id, Agreement.deleted_at.is_(None)).order_by(Clinic.razon_social)
        )
    ).all()
    out = []
    for ag, clinica in rows:
        n_aranceles = (await db.execute(select(func.count(Arancel.id)).where(Arancel.agreement_id == ag.id, Arancel.deleted_at.is_(None)))).scalar_one()
        vigente = _vigente(ag.vigencia_inicio, ag.vigencia_fin)
        out.append(
            {
                "agreement_id": ag.id,
                "clinic_id": ag.clinic_id,
                "clinica": clinica,
                "vigencia_inicio": ag.vigencia_inicio,
                "vigencia_fin": ag.vigencia_fin,
                "vigente": vigente,
                "aranceles": n_aranceles,
            }
        )
    return out


async def aranceles(db: AsyncSession, ctx: TenantContext, agreement_id: uuid.UUID) -> list[dict]:
    await _load_agreement(db, ctx, agreement_id)
    rows = (
        await db.execute(
            select(Arancel, CatalogItem.nombre).join(CatalogItem, CatalogItem.id == Arancel.service_id).where(Arancel.agreement_id == agreement_id, Arancel.deleted_at.is_(None)).order_by(CatalogItem.nombre)
        )
    ).all()
    return [{"arancel_id": a.id, "service_id": a.service_id, "servicio": nombre, "cobertura_pct": float(a.cobertura_pct), "copago": float(a.copago)} for a, nombre in rows]


async def crear_arancel(db: AsyncSession, ctx: TenantContext, agreement_id: uuid.UUID, *, service_id: uuid.UUID, cobertura_pct: float, copago: float) -> dict:
    ag = await _load_agreement(db, ctx, agreement_id)
    service = (await db.execute(select(CatalogItem).where(CatalogItem.id == service_id, CatalogItem.clinic_id == ag.clinic_id, CatalogItem.deleted_at.is_(None)))).scalar_one_or_none()
    if service is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El servicio no pertenece a la clínica del convenio")
    if not (0 <= cobertura_pct <= 100):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "cobertura_pct debe estar entre 0 y 100")
    # Versionar = dar de baja el arancel vigente del servicio y crear el nuevo
    # (el histórico se conserva por la baja lógica; nunca se edita en sitio).
    prev = (await db.execute(select(Arancel).where(Arancel.agreement_id == agreement_id, Arancel.service_id == service_id, Arancel.deleted_at.is_(None)))).scalar_one_or_none()
    if prev is not None:
        await db.delete(prev)  # soft-delete vía listener
    nuevo = Arancel(clinic_id=ag.clinic_id, agreement_id=agreement_id, service_id=service_id, cobertura_pct=cobertura_pct, copago=copago)
    db.add(nuevo)
    audit(db, ctx, clinic_id=ag.clinic_id, accion="versionar_arancel", recurso=f"arancel:{service_id}", despues={"cobertura_pct": cobertura_pct, "copago": copago})
    await db.commit()
    await db.refresh(nuevo)
    return {"arancel_id": nuevo.id, "service_id": service_id, "cobertura_pct": cobertura_pct, "copago": copago}


# ─────────────────────────── padrón de afiliados (§2) ───────────────────────────
async def padron(db: AsyncSession, ctx: TenantContext) -> list[dict]:
    insurer_id = require_insurer(ctx)
    today = datetime.now(timezone.utc).date()
    rows = (
        await db.execute(
            select(Affiliate, User.nombre)
            .join(Patient, Patient.id == Affiliate.patient_id, isouter=True)
            .join(User, User.id == Patient.user_id, isouter=True)
            .where(Affiliate.insurer_id == insurer_id, Affiliate.deleted_at.is_(None))
            .order_by(Affiliate.created_at.desc())
        )
    ).all()
    return [
        {
            "affiliate_id": a.id,
            "patient_id": a.patient_id,
            "nombre": nombre,
            "documento_identidad": a.documento_identidad,
            "plan_cobertura": a.plan_cobertura,
            "vigencia_desde": a.vigencia_desde,
            "vigencia_hasta": a.vigencia_hasta,
            "vigente": _vigente(a.vigencia_desde, a.vigencia_hasta, today),
        }
        for a, nombre in rows
    ]


async def alta_afiliado(db: AsyncSession, ctx: TenantContext, *, documento_identidad: str, plan_cobertura: str | None, vigencia_desde: date | None, vigencia_hasta: date | None) -> dict:
    insurer_id = require_insurer(ctx)
    existe = (await db.execute(select(Affiliate).where(Affiliate.insurer_id == insurer_id, Affiliate.documento_identidad == documento_identidad, Affiliate.deleted_at.is_(None)))).scalar_one_or_none()
    if existe is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe un afiliado con ese documento")
    af = Affiliate(insurer_id=insurer_id, documento_identidad=documento_identidad, plan_cobertura=plan_cobertura, vigencia_desde=vigencia_desde, vigencia_hasta=vigencia_hasta)
    db.add(af)
    await db.commit()
    await db.refresh(af)
    return {"affiliate_id": af.id, "documento_identidad": af.documento_identidad}


async def baja_afiliado(db: AsyncSession, ctx: TenantContext, affiliate_id: uuid.UUID) -> None:
    insurer_id = require_insurer(ctx)
    af = (await db.execute(select(Affiliate).where(Affiliate.id == affiliate_id, Affiliate.deleted_at.is_(None)))).scalar_one_or_none()
    if af is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Afiliado no encontrado")
    if af.insurer_id != insurer_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Ese afiliado es de otra aseguradora")
    await db.delete(af)  # baja lógica
    await db.commit()


# ─────────────────────────── autorizaciones (§5.1) ───────────────────────────
async def autorizaciones(db: AsyncSession, ctx: TenantContext, estado: str | None = None) -> list[dict]:
    insurer_id = require_insurer(ctx)
    ag_ids = await _agreement_ids(db, insurer_id)
    if not ag_ids:
        return []
    q = (
        select(Authorization, User.nombre, CatalogItem.nombre, Clinic.razon_social)
        .join(Patient, Patient.id == Authorization.patient_id)
        .join(User, User.id == Patient.user_id)
        .join(CatalogItem, CatalogItem.id == Authorization.service_id, isouter=True)
        .join(Agreement, Agreement.id == Authorization.agreement_id)
        .join(Clinic, Clinic.id == Agreement.clinic_id)
        .where(Authorization.agreement_id.in_(ag_ids), Authorization.deleted_at.is_(None))
        .order_by(Authorization.created_at.desc())
    )
    if estado:
        q = q.where(Authorization.estado == estado)
    rows = (await db.execute(q)).all()
    return [
        {
            "authorization_id": a.id,
            "agreement_id": a.agreement_id,
            "patient_id": a.patient_id,
            "paciente": paciente,
            "servicio": servicio or "—",
            "clinica": clinica,
            "estado": a.estado,
            "motivo_rechazo": a.motivo_rechazo,
            "resuelto_en": a.resuelto_en,
            "fecha": a.created_at,
        }
        for a, paciente, servicio, clinica in rows
    ]


async def resolver(db: AsyncSession, ctx: TenantContext, authorization_id: uuid.UUID, *, decision: str, motivo: str | None = None) -> dict:
    """Aprobar / rechazar / pedir info (§5.1). Valida vigencia del afiliado
    antes de aprobar; toda resolución queda auditada."""
    if decision not in {"aprobar", "rechazar", "pedir_info"}:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "decision inválida")
    auth = (await db.execute(select(Authorization).where(Authorization.id == authorization_id, Authorization.deleted_at.is_(None)))).scalar_one_or_none()
    if auth is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Autorización no encontrada")
    ag = await _load_agreement(db, ctx, auth.agreement_id)
    if auth.estado in {"aprobada", "rechazada"}:
        raise HTTPException(status.HTTP_409_CONFLICT, "La autorización ya fue resuelta")

    now = datetime.now(timezone.utc)
    if decision == "aprobar":
        # Vigencia del afiliado: si venció, no se puede aprobar (§5.1 error).
        af = (await db.execute(select(Affiliate).where(Affiliate.insurer_id == ag.insurer_id, Affiliate.patient_id == auth.patient_id, Affiliate.deleted_at.is_(None)))).scalar_one_or_none()
        if af is not None and not _vigente(af.vigencia_desde, af.vigencia_hasta, now.date()):
            raise HTTPException(status.HTTP_409_CONFLICT, "El afiliado no tiene cobertura vigente; rechaza con motivo")
        auth.estado = "aprobada"
        auth.resuelto_en = now
        auth.motivo_rechazo = None
    elif decision == "rechazar":
        if not motivo:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "El rechazo requiere un motivo")
        auth.estado = "rechazada"
        auth.resuelto_en = now
        auth.motivo_rechazo = motivo
    else:  # pedir_info
        auth.estado = "pendiente_info"

    audit(db, ctx, clinic_id=ag.clinic_id, accion=f"autorizacion_{auth.estado}", recurso=f"authorization:{auth.id}", despues={"decision": decision, "motivo": motivo})
    await db.commit()
    return {"authorization_id": auth.id, "estado": auth.estado, "motivo_rechazo": auth.motivo_rechazo, "resuelto_en": auth.resuelto_en}


# ─────────────────────────── liquidaciones (§5.2) ───────────────────────────
async def liquidaciones(db: AsyncSession, ctx: TenantContext) -> list[dict]:
    insurer_id = require_insurer(ctx)
    ag_ids = await _agreement_ids(db, insurer_id)
    if not ag_ids:
        return []
    rows = (
        await db.execute(
            select(Settlement, Clinic.razon_social)
            .join(Agreement, Agreement.id == Settlement.agreement_id)
            .join(Clinic, Clinic.id == Agreement.clinic_id)
            .where(Settlement.agreement_id.in_(ag_ids), Settlement.deleted_at.is_(None))
            .order_by(Settlement.created_at.desc())
        )
    ).all()
    return [
        {"settlement_id": s.id, "agreement_id": s.agreement_id, "clinica": clinica, "periodo": s.periodo, "monto": float(s.monto), "estado": s.estado, "pagado_at": s.pagado_at}
        for s, clinica in rows
    ]


async def generar_liquidacion(db: AsyncSession, ctx: TenantContext, agreement_id: uuid.UUID, periodo: str) -> dict:
    """Agrupa las atenciones autorizadas del período y calcula el monto neto
    a la clínica (precio × cobertura). Crea el Settlement y asienta el
    'facturado' en el ledger (que el CRM lee como Cuentas por Cobrar)."""
    ag = await _load_agreement(db, ctx, agreement_id)
    existe = (await db.execute(select(Settlement).where(Settlement.agreement_id == agreement_id, Settlement.periodo == periodo, Settlement.deleted_at.is_(None)))).scalar_one_or_none()
    if existe is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Ya existe una liquidación para {periodo}")

    # monto neto = Σ precio_servicio × cobertura_pct de las autorizaciones
    # aprobadas del convenio (las que la aseguradora debe pagar a la clínica).
    rows = (
        await db.execute(
            select(CatalogItem.precio, Arancel.cobertura_pct)
            .select_from(Authorization)
            .join(CatalogItem, CatalogItem.id == Authorization.service_id)
            .join(Arancel, (Arancel.agreement_id == Authorization.agreement_id) & (Arancel.service_id == Authorization.service_id) & (Arancel.deleted_at.is_(None)))
            .where(Authorization.agreement_id == agreement_id, Authorization.estado == "aprobada", Authorization.deleted_at.is_(None))
        )
    ).all()
    monto = round(sum(float(precio) * float(cobertura) / 100.0 for precio, cobertura in rows), 2)
    if monto <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No hay atenciones autorizadas con arancel para liquidar en el período")

    settlement = Settlement(clinic_id=ag.clinic_id, agreement_id=agreement_id, periodo=periodo, monto=monto, estado="pendiente")
    db.add(settlement)
    await db.flush()
    # 'facturado': la clínica factura a la aseguradora -> sube la CxC del CRM.
    db.add(LedgerEntry(clinic_id=ag.clinic_id, tipo="facturado", monto=monto, ref=f"settlement:{settlement.id}"))
    audit(db, ctx, clinic_id=ag.clinic_id, accion="generar_liquidacion", recurso=f"settlement:{settlement.id}", despues={"periodo": periodo, "monto": monto})
    await db.commit()
    return {"settlement_id": settlement.id, "periodo": periodo, "monto": monto, "estado": settlement.estado}


async def pagar_liquidacion(db: AsyncSession, ctx: TenantContext, settlement_id: uuid.UUID) -> dict:
    """Conciliar y pagar (§5.2): asienta el 'cobrado' inmutable (baja la CxC)
    y marca la liquidación pagada. Idempotente."""
    s = (await db.execute(select(Settlement).where(Settlement.id == settlement_id, Settlement.deleted_at.is_(None)))).scalar_one_or_none()
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Liquidación no encontrada")
    ag = await _load_agreement(db, ctx, s.agreement_id)
    if s.estado == "pagado":
        raise HTTPException(status.HTTP_409_CONFLICT, "La liquidación ya fue pagada")
    s.estado = "pagado"
    s.pagado_at = datetime.now(timezone.utc)
    db.add(LedgerEntry(clinic_id=ag.clinic_id, tipo="cobrado", monto=s.monto, ref=f"settlement:{s.id}"))
    audit(db, ctx, clinic_id=ag.clinic_id, accion="pagar_liquidacion", recurso=f"settlement:{s.id}", despues={"monto": float(s.monto)})
    await db.commit()
    return {"settlement_id": s.id, "estado": s.estado, "pagado_at": s.pagado_at}


# ─────────────────────────── red de prestadores (§4) ───────────────────────────
async def red(db: AsyncSession, ctx: TenantContext) -> list[dict]:
    """Clínicas (y su país) con convenio vigente con esta aseguradora."""
    insurer_id = require_insurer(ctx)
    rows = (
        await db.execute(
            select(Clinic.id, Clinic.razon_social, Clinic.pais, Agreement.vigencia_inicio, Agreement.vigencia_fin)
            .join(Agreement, Agreement.clinic_id == Clinic.id)
            .where(Agreement.insurer_id == insurer_id, Agreement.deleted_at.is_(None), Clinic.deleted_at.is_(None))
            .order_by(Clinic.razon_social)
        )
    ).all()
    return [{"clinic_id": cid, "clinica": nombre, "pais": pais, "vigente": _vigente(vi, vf)} for cid, nombre, pais, vi, vf in rows]


# ─────────────────────────── ficha del afiliado (§3 minimización) ───────────────────────────
async def ficha_afiliado(db: AsyncSession, ctx: TenantContext, patient_id: uuid.UUID) -> dict:
    """Mínimo dato clínico: solo se expone si existe una autorización APROBADA
    de esta aseguradora para el paciente, y solo lo autorizado (servicios y
    diagnóstico de esas atenciones). Cada acceso queda auditado (§3/§8)."""
    insurer_id = require_insurer(ctx)
    ag_ids = await _agreement_ids(db, insurer_id)
    aprobadas = []
    if ag_ids:
        aprobadas = (
            await db.execute(
                select(Authorization, CatalogItem.nombre)
                .join(CatalogItem, CatalogItem.id == Authorization.service_id, isouter=True)
                .where(Authorization.agreement_id.in_(ag_ids), Authorization.patient_id == patient_id, Authorization.estado == "aprobada", Authorization.deleted_at.is_(None))
            )
        ).all()
    if not aprobadas:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Sin autorización aprobada: no hay acceso al dato clínico de este afiliado")

    paciente = (await db.execute(select(User.nombre).join(Patient, Patient.user_id == User.id).where(Patient.id == patient_id))).scalar_one_or_none()
    af = (await db.execute(select(Affiliate).where(Affiliate.insurer_id == insurer_id, Affiliate.patient_id == patient_id, Affiliate.deleted_at.is_(None)))).scalar_one_or_none()

    # Diagnóstico mínimo de las atenciones autorizadas (no el prontuario
    # completo): solo el campo 'diagnostico' del registro clínico.
    diagnosticos = []
    for auth, servicio in aprobadas:
        rec = (
            await db.execute(
                select(MedicalRecord).where(MedicalRecord.patient_id == patient_id, MedicalRecord.deleted_at.is_(None)).order_by(MedicalRecord.created_at.desc()).limit(1)
            )
        ).scalar_one_or_none()
        diagnosticos.append({"servicio": servicio or "—", "diagnostico": (rec.contenido or {}).get("diagnostico") if rec else None})

    # Auditar el acceso a la ficha del afiliado (clinic_id del primer convenio).
    ag0 = await db.get(Agreement, aprobadas[0][0].agreement_id)
    audit(db, ctx, clinic_id=ag0.clinic_id if ag0 else None, accion="ver_ficha_afiliado", recurso=f"patient:{patient_id}")
    await db.commit()

    return {
        "patient_id": patient_id,
        "nombre": paciente or "—",
        "documento_identidad": af.documento_identidad if af else None,
        "plan_cobertura": af.plan_cobertura if af else None,
        "prestaciones_autorizadas": diagnosticos,
    }


# ─────────────────────────── util ───────────────────────────
def _vigente(desde: date | None, hasta: date | None, ref: date | None = None) -> bool:
    ref = ref or datetime.now(timezone.utc).date()
    if desde is not None and ref < desde:
        return False
    if hasta is not None and ref > hasta:
        return False
    return True
