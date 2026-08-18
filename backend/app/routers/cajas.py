"""Módulo de Cajas (Tanda 2): arqueo diario por colaborador.

Cada movimiento de caja (pago o gasto) asienta además un LedgerEntry inmutable
('cobro' o 'egreso'); la caja es el control operativo del día, el ledger sigue
siendo la fuente de verdad financiera. Un pago puede ligarse a una cita, lo que
conecta con la 'situación de pago' de la agenda de gerencia (Tanda 1).
"""

import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.database import get_db
from app.integrations import tributario as tributario_conn
from app.models.finance import CashPayment, CashRegister, LedgerEntry
from app.models.identity import User
from app.models.patient import Patient
from app.models.scheduling import Appointment
from app.models.tenant import Clinic
from app.rbac.deps import require
from app.rbac.permissions import Action, Resource
from app.routers.empresa import empresa_clinic_id
from app.schemas.cajas import (
    MEDIOS,
    AbrirCajaIn,
    AnularPagoIn,
    CajaDetalleOut,
    CajaOut,
    CerrarCajaIn,
    MovimientoIn,
    MovimientoOut,
    PagoAnuladoOut,
)
from app.services.medico import audit
from app.tenancy.context import TenantContext

router = APIRouter(prefix="/empresa/cajas", tags=["cajas"])


async def _totales(db: AsyncSession, caja_id: uuid.UUID) -> tuple[float, float, dict[str, float]]:
    rows = (
        await db.execute(
            select(CashPayment.tipo, CashPayment.medio, func.coalesce(func.sum(CashPayment.monto), 0))
            .where(CashPayment.cash_register_id == caja_id, CashPayment.deleted_at.is_(None), CashPayment.anulado.is_(False))
            .group_by(CashPayment.tipo, CashPayment.medio)
        )
    ).all()
    recaudado = 0.0
    gastos = 0.0
    por_medio: dict[str, float] = {}
    for tipo, medio, monto in rows:
        m = float(monto)
        if tipo == "gasto":
            gastos += m
        else:
            recaudado += m
            por_medio[medio] = por_medio.get(medio, 0.0) + m
    return recaudado, gastos, por_medio


async def _caja_out(db: AsyncSession, caja: CashRegister, *, detalle: bool = False) -> CajaOut | CajaDetalleOut:
    resp = await db.get(User, caja.responsable_id)
    recaudado, gastos, por_medio = await _totales(db, caja.id)
    total = float(caja.abono_inicial) + recaudado - gastos
    base = dict(
        id=caja.id,
        responsable_id=caja.responsable_id,
        responsable_nombre=resp.nombre if resp else "",
        estado=caja.estado,
        abono_inicial=float(caja.abono_inicial),
        fondo_fijo=float(caja.fondo_fijo) if caja.fondo_fijo is not None else None,
        abierta_at=caja.created_at,
        cerrada_at=caja.cerrada_at,
        recaudado=recaudado,
        gastos=gastos,
        total=total,
    )
    if not detalle:
        return CajaOut(**base)

    mov_rows = (
        await db.execute(
            select(CashPayment, User.nombre)
            .outerjoin(Patient, Patient.id == CashPayment.patient_id)
            .outerjoin(User, User.id == Patient.user_id)
            .where(CashPayment.cash_register_id == caja.id, CashPayment.deleted_at.is_(None), CashPayment.anulado.is_(False))
            .order_by(CashPayment.created_at.desc())
        )
    ).all()
    transacciones = [
        MovimientoOut(
            id=p.id,
            tipo=p.tipo,
            medio=p.medio,
            monto=float(p.monto),
            convenio=p.convenio,
            referencia=p.referencia,
            boleta=p.boleta,
            glosa=p.glosa,
            paciente_nombre=nombre,
            appointment_id=p.appointment_id,
            fecha=p.created_at,
        )
        for p, nombre in mov_rows
    ]
    return CajaDetalleOut(**base, por_medio=por_medio, transacciones=transacciones)


async def _own_caja(db: AsyncSession, clinic_id: uuid.UUID, caja_id: uuid.UUID) -> CashRegister:
    caja = await db.get(CashRegister, caja_id)
    if caja is None or caja.deleted_at is not None or caja.clinic_id != clinic_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Caja no encontrada")
    return caja


@router.get("", response_model=list[CajaOut])
async def listar_cajas(
    estado: str | None = None,
    fecha: date | None = None,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CAJAS, Action.VER)),
) -> list[CajaOut]:
    clinic_id = empresa_clinic_id(ctx)
    q = select(CashRegister).where(CashRegister.clinic_id == clinic_id, CashRegister.deleted_at.is_(None))
    if estado in ("abierta", "cerrada"):
        q = q.where(CashRegister.estado == estado)
    if fecha:
        q = q.where(func.date(CashRegister.created_at) == fecha)
    cajas = (await db.execute(q.order_by(CashRegister.created_at.desc()))).scalars().all()
    return [await _caja_out(db, c) for c in cajas]  # type: ignore[misc]


@router.get("/mi-caja", response_model=CajaDetalleOut | None)
async def mi_caja(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CAJAS, Action.VER)),
) -> CajaDetalleOut | None:
    clinic_id = empresa_clinic_id(ctx)
    caja = (
        await db.execute(
            select(CashRegister).where(
                CashRegister.clinic_id == clinic_id,
                CashRegister.responsable_id == ctx.user_id,
                CashRegister.estado == "abierta",
                CashRegister.deleted_at.is_(None),
            )
        )
    ).scalars().first()
    if caja is None:
        return None
    return await _caja_out(db, caja, detalle=True)  # type: ignore[return-value]


@router.post("", response_model=CajaDetalleOut, status_code=status.HTTP_201_CREATED)
async def abrir_caja(
    payload: AbrirCajaIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CAJAS, Action.CREAR)),
) -> CajaDetalleOut:
    clinic_id = empresa_clinic_id(ctx)
    ya = (
        await db.execute(
            select(CashRegister).where(
                CashRegister.clinic_id == clinic_id,
                CashRegister.responsable_id == ctx.user_id,
                CashRegister.estado == "abierta",
                CashRegister.deleted_at.is_(None),
            )
        )
    ).scalars().first()
    if ya is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya tienes una caja abierta; ciérrala antes de abrir otra")
    caja = CashRegister(
        clinic_id=clinic_id,
        branch_id=payload.branch_id,
        responsable_id=ctx.user_id,
        estado="abierta",
        abono_inicial=payload.abono_inicial,
    )
    db.add(caja)
    audit(db, ctx, clinic_id=clinic_id, accion="abrir_caja", recurso="cash_register")
    await db.commit()
    await db.refresh(caja)
    return await _caja_out(db, caja, detalle=True)  # type: ignore[return-value]


@router.get("/{caja_id}", response_model=CajaDetalleOut)
async def detalle_caja(
    caja_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CAJAS, Action.VER)),
) -> CajaDetalleOut:
    clinic_id = empresa_clinic_id(ctx)
    caja = await _own_caja(db, clinic_id, caja_id)
    return await _caja_out(db, caja, detalle=True)  # type: ignore[return-value]


@router.post("/{caja_id}/movimientos", response_model=MovimientoOut, status_code=status.HTTP_201_CREATED)
async def registrar_movimiento(
    caja_id: uuid.UUID,
    payload: MovimientoIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CAJAS, Action.CREAR)),
) -> MovimientoOut:
    clinic_id = empresa_clinic_id(ctx)
    caja = await _own_caja(db, clinic_id, caja_id)
    if caja.estado != "abierta":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "La caja está cerrada")
    if payload.tipo not in ("pago", "gasto"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Tipo inválido (pago | gasto)")
    if payload.medio not in MEDIOS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Medio de pago inválido: {payload.medio}")

    # validar cita/paciente si vienen (deben ser de la clínica)
    if payload.appointment_id:
        appt = await db.get(Appointment, payload.appointment_id)
        if appt is None or appt.clinic_id != clinic_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cita inválida")
    if payload.patient_id:
        pac = await db.get(Patient, payload.patient_id)
        if pac is None or pac.clinic_id != clinic_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Paciente inválido")

    # asiento inmutable en el ledger. El ledger es INSERT-only (sin UPDATE a
    # nivel de BD), así que fijamos el id del movimiento ANTES para poder
    # referenciarlo en el asiento sin tener que actualizarlo luego.
    mov_id = uuid.uuid4()
    tipo_ledger = "egreso" if payload.tipo == "gasto" else "cobro"
    ledger = LedgerEntry(clinic_id=clinic_id, tipo=tipo_ledger, monto=payload.monto, ref=f"cash_payment:{mov_id}")
    db.add(ledger)
    await db.flush()

    mov = CashPayment(
        id=mov_id,
        clinic_id=clinic_id,
        cash_register_id=caja.id,
        patient_id=payload.patient_id,
        appointment_id=payload.appointment_id,
        ledger_entry_id=ledger.id,
        tipo=payload.tipo,
        medio=payload.medio,
        convenio=payload.convenio,
        monto=payload.monto,
        referencia=payload.referencia,
        boleta=payload.boleta,
        glosa=payload.glosa,
    )
    db.add(mov)
    await db.flush()

    # Emisión tributaria (Tanda 7): un pago puede emitir su documento (boleta
    # SII en Chile / Nota Fiscal en Brasil) en la misma transacción. El conector
    # valida que esté habilitado (409 si no). El folio queda en mov.boleta.
    tax_document_id = None
    if payload.emitir_boleta and payload.tipo == "pago":
        tipo_doc = payload.tipo_documento
        if tipo_doc is None:
            clinic = await db.get(Clinic, clinic_id)
            pais = clinic.pais if clinic else ""
            # En Chile una prestación exenta (médica/odontológica) emite boleta
            # exenta (41); una afecta, boleta electrónica (39).
            defaults = {"CL": "boleta_exenta" if payload.exento else "boleta_electronica", "BR": "nfse", "MX": "factura"}
            tipo_doc = defaults.get(pais, "")
        receptor = None
        if payload.receptor_tax_id or payload.receptor_nombre:
            receptor = {"tax_id": payload.receptor_tax_id, "nombre": payload.receptor_nombre}
        doc = await tributario_conn.emitir(
            db,
            clinic_id,
            tipo_documento=tipo_doc,
            items=[{"descripcion": payload.glosa or "Atención", "cantidad": 1, "precio_unitario": float(payload.monto), "exento": payload.exento}],
            receptor=receptor,
            appointment_id=mov.appointment_id,
            cash_payment_id=mov.id,
            ledger_entry_id=mov.ledger_entry_id,
            actor_id=ctx.user_id,
        )
        mov.boleta = f"{doc.tipo_documento} #{doc.folio}"
        tax_document_id = doc.id

    audit(db, ctx, clinic_id=clinic_id, accion=f"caja_{payload.tipo}", recurso=f"cash_payment:{mov.id}")
    await db.commit()
    await db.refresh(mov)

    nombre = None
    if mov.patient_id:
        pac = await db.get(Patient, mov.patient_id)
        u = await db.get(User, pac.user_id) if pac else None
        nombre = u.nombre if u else None
    return MovimientoOut(
        id=mov.id, tipo=mov.tipo, medio=mov.medio, monto=float(mov.monto), convenio=mov.convenio,
        referencia=mov.referencia, boleta=mov.boleta, glosa=mov.glosa, paciente_nombre=nombre,
        appointment_id=mov.appointment_id, fecha=mov.created_at, tax_document_id=tax_document_id,
    )


@router.post("/{caja_id}/cerrar", response_model=CajaDetalleOut)
async def cerrar_caja(
    caja_id: uuid.UUID,
    payload: CerrarCajaIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CAJAS, Action.EDITAR)),
) -> CajaDetalleOut:
    clinic_id = empresa_clinic_id(ctx)
    caja = await _own_caja(db, clinic_id, caja_id)
    if caja.estado != "abierta":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "La caja ya está cerrada")
    caja.estado = "cerrada"
    caja.fondo_fijo = payload.fondo_fijo
    caja.cerrada_at = datetime.now(timezone.utc)
    caja.cerrada_por = ctx.user_id
    audit(db, ctx, clinic_id=clinic_id, accion="cerrar_caja", recurso=f"cash_register:{caja.id}")
    await db.commit()
    await db.refresh(caja)
    return await _caja_out(db, caja, detalle=True)  # type: ignore[return-value]


# ─────────────────────────── anulación de pagos (67) ───────────────────────────
@router.post("/pagos/{payment_id}/anular", response_model=PagoAnuladoOut)
async def anular_pago(
    payment_id: uuid.UUID,
    payload: AnularPagoIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CAJAS, Action.EDITAR)),
) -> PagoAnuladoOut:
    """Anula un pago dejando traza (67.1/67.2). El pago no se borra: se marca
    anulado (sale de los totales de la caja) y se asienta un reverso inmutable
    en el ledger. Solo sobre una caja abierta, para no alterar un arqueo cerrado."""
    clinic_id = empresa_clinic_id(ctx)
    mov = await db.get(CashPayment, payment_id)
    if mov is None or mov.deleted_at is not None or mov.clinic_id != clinic_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pago no encontrado")
    if mov.anulado:
        raise HTTPException(status.HTTP_409_CONFLICT, "El pago ya está anulado")
    caja = await db.get(CashRegister, mov.cash_register_id)
    if caja is None or caja.estado != "abierta":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Solo se pueden anular pagos de una caja abierta")

    mov.anulado = True
    mov.anulado_por = ctx.user_id
    mov.anulado_at = datetime.now(timezone.utc)
    mov.motivo_anulacion = payload.motivo
    tipo_rev = "egreso_anulado" if mov.tipo == "gasto" else "cobro_anulado"
    db.add(LedgerEntry(clinic_id=clinic_id, tipo=tipo_rev, monto=mov.monto, ref=f"cash_payment:{mov.id}:anulacion"))
    audit(db, ctx, clinic_id=clinic_id, accion="anular_pago", recurso=f"cash_payment:{mov.id}", despues={"motivo": payload.motivo, "monto": float(mov.monto)})
    await db.commit()

    autor = await db.get(User, mov.anulado_por)
    return PagoAnuladoOut(
        id=mov.id, tipo=mov.tipo, medio=mov.medio, monto=float(mov.monto), paciente_nombre=None,
        appointment_id=mov.appointment_id, fecha=mov.created_at, anulado_at=mov.anulado_at,
        anulado_por=autor.nombre if autor else None, motivo=mov.motivo_anulacion,
    )


@router.get("/pagos/anulados", response_model=list[PagoAnuladoOut])
async def pagos_anulados(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CAJAS, Action.VER)),
) -> list[PagoAnuladoOut]:
    clinic_id = empresa_clinic_id(ctx)
    pat_user = aliased(User)
    anul_user = aliased(User)
    rows = (
        await db.execute(
            select(CashPayment, pat_user.nombre, anul_user.nombre)
            .outerjoin(Patient, Patient.id == CashPayment.patient_id)
            .outerjoin(pat_user, pat_user.id == Patient.user_id)
            .outerjoin(anul_user, anul_user.id == CashPayment.anulado_por)
            .where(CashPayment.clinic_id == clinic_id, CashPayment.deleted_at.is_(None), CashPayment.anulado.is_(True))
            .order_by(CashPayment.anulado_at.desc())
        )
    ).all()
    return [
        PagoAnuladoOut(
            id=p.id, tipo=p.tipo, medio=p.medio, monto=float(p.monto), paciente_nombre=pac,
            appointment_id=p.appointment_id, fecha=p.created_at, anulado_at=p.anulado_at, anulado_por=anulador, motivo=p.motivo_anulacion,
        )
        for p, pac, anulador in rows
    ]
