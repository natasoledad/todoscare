import uuid
from datetime import datetime, time, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.catalog import CatalogItem
from app.models.clinical import (
    ExamOrder,
    ExamResult,
    Hospitalization,
    MedicalRecord,
    Odontogram,
    Prescription,
)
from app.models.identity import User
from app.models.patient import Patient
from app.models.scheduling import Appointment
from app.rbac.deps import require
from app.rbac.permissions import Action, Resource
from app.schemas.medico import (
    AlertaClinica,
    CierreOut,
    CitaMedicoOut,
    EnmiendaInput,
    ExamenFichaOut,
    FichaPacienteOut,
    HospitalizacionFichaOut,
    LiquidacionOut,
    OrdenInput,
    OrdenOut,
    PrescripcionInput,
    PrescripcionOut,
    PrescripcionResult,
    ProntuarioInput,
    ProntuarioOut,
)
from app.services.finance import liquidar_atencion
from app.services.medico import audit, get_own_appointment, get_treated_patient
from app.tenancy.context import TenantContext

router = APIRouter(prefix="/medico", tags=["medico"])


# ─────────────────────────── agenda ───────────────────────────
@router.get("/agenda", response_model=list[CitaMedicoOut])
async def agenda_del_dia(
    fecha: str | None = None,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.OWN_AGENDA, Action.VER)),
) -> list[CitaMedicoOut]:
    q = (
        select(Appointment, User.nombre, CatalogItem.nombre)
        .join(Patient, Patient.id == Appointment.patient_id)
        .join(User, User.id == Patient.user_id)
        .join(CatalogItem, CatalogItem.id == Appointment.service_id, isouter=True)
        .where(Appointment.professional_id == ctx.user_id, Appointment.deleted_at.is_(None))
        .order_by(Appointment.slot)
    )
    rows = (await db.execute(q)).all()

    day = None
    if fecha:
        try:
            day = datetime.fromisoformat(fecha).date()
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Fecha inválida (usa YYYY-MM-DD)") from None

    # which appointments already have a prontuario
    attended_ids = set(
        (await db.execute(select(MedicalRecord.appointment_id).where(MedicalRecord.professional_id == ctx.user_id))).scalars().all()
    )

    out: list[CitaMedicoOut] = []
    for appt, paciente_nombre, servicio_nombre in rows:
        if day is not None and appt.slot.lower.date() != day:
            continue
        out.append(
            CitaMedicoOut(
                id=appt.id,
                patient_id=appt.patient_id,
                paciente_nombre=paciente_nombre,
                servicio_nombre=servicio_nombre or "",
                inicio=appt.slot.lower,
                fin=appt.slot.upper,
                estado=appt.estado,
                atendida=appt.id in attended_ids,
            )
        )
    return out


# ─────────────────────────── ficha del paciente ───────────────────────────
@router.get("/pacientes/{patient_id}/ficha", response_model=FichaPacienteOut)
async def ver_ficha(
    patient_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.PRONTUARIO_ATENDIDOS, Action.VER)),
) -> FichaPacienteOut:
    patient = await get_treated_patient(db, ctx, patient_id)
    user = await db.get(User, patient.user_id)

    audit(db, ctx, clinic_id=patient.clinic_id, accion="ver_ficha_clinica", recurso=f"patient:{patient_id}")
    await db.commit()

    exam_rows = (
        await db.execute(
            select(ExamOrder, ExamResult)
            .join(ExamResult, ExamResult.order_id == ExamOrder.id, isouter=True)
            .where(ExamOrder.patient_id == patient_id, ExamOrder.deleted_at.is_(None))
            .order_by(ExamOrder.created_at.desc())
        )
    ).all()
    examenes = [
        ExamenFichaOut(
            nombre=(r.resultado or {}).get("nombre", o.tipo.capitalize()) if r else o.tipo.capitalize(),
            fecha=o.created_at,
            estado=(r.estado if r else o.estado),
        )
        for o, r in exam_rows
    ]

    hosp = (
        await db.execute(select(Hospitalization).where(Hospitalization.patient_id == patient_id, Hospitalization.deleted_at.is_(None)).order_by(Hospitalization.ingreso.desc()))
    ).scalars().all()

    odo = (await db.execute(select(Odontogram).where(Odontogram.patient_id == patient_id))).scalar_one_or_none()

    return FichaPacienteOut(
        patient_id=patient.id,
        nombre=user.nombre,
        rut=patient.rut,
        nivel=patient.nivel,
        ficha=patient.ficha or {},
        examenes=examenes,
        hospitalizaciones=[HospitalizacionFichaOut(motivo=h.motivo, centro=h.centro, ingreso=h.ingreso) for h in hosp],
        odontograma=(odo.piezas if odo else {}),
    )


# ─────────────────────────── atención / prontuario ───────────────────────────
async def _ensure_record(db: AsyncSession, ctx: TenantContext, appt: Appointment) -> MedicalRecord:
    record = (
        await db.execute(
            select(MedicalRecord).where(MedicalRecord.appointment_id == appt.id, MedicalRecord.professional_id == ctx.user_id).order_by(MedicalRecord.created_at.desc())
        )
    ).scalars().first()
    if record is None:
        record = MedicalRecord(clinic_id=appt.clinic_id, patient_id=appt.patient_id, professional_id=ctx.user_id, appointment_id=appt.id, contenido={})
        db.add(record)
        await db.flush()
    return record


@router.post("/citas/{appointment_id}/atencion", response_model=ProntuarioOut, status_code=status.HTTP_201_CREATED)
async def registrar_atencion(
    appointment_id: uuid.UUID,
    payload: ProntuarioInput,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.PRONTUARIO_ATENDIDOS, Action.CREAR)),
) -> ProntuarioOut:
    appt = await get_own_appointment(db, ctx, appointment_id)
    record = MedicalRecord(
        clinic_id=appt.clinic_id,
        patient_id=appt.patient_id,
        professional_id=ctx.user_id,
        appointment_id=appt.id,
        contenido={
            "motivo": payload.motivo,
            "evolucion": payload.evolucion,
            "diagnostico": payload.diagnostico,
            **(payload.contenido_extra or {}),
            "enmiendas": [],
        },
    )
    db.add(record)
    audit(db, ctx, clinic_id=appt.clinic_id, accion="crear_prontuario", recurso=f"appointment:{appt.id}")
    await db.commit()
    await db.refresh(record)
    return ProntuarioOut(id=record.id, contenido=record.contenido, creado=record.created_at)


@router.get("/citas/{appointment_id}/prontuario", response_model=list[ProntuarioOut])
async def ver_prontuario(
    appointment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.PRONTUARIO_ATENDIDOS, Action.VER)),
) -> list[ProntuarioOut]:
    appt = await get_own_appointment(db, ctx, appointment_id)
    rows = (
        await db.execute(select(MedicalRecord).where(MedicalRecord.appointment_id == appt.id).order_by(MedicalRecord.created_at))
    ).scalars().all()
    return [ProntuarioOut(id=r.id, contenido=r.contenido, creado=r.created_at) for r in rows]


@router.patch("/prontuario/{record_id}/enmienda", response_model=ProntuarioOut)
async def enmendar_prontuario(
    record_id: uuid.UUID,
    payload: EnmiendaInput,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.PRONTUARIO_ATENDIDOS, Action.EDITAR)),
) -> ProntuarioOut:
    """Enmienda auditada — el contenido original nunca se borra ni se
    sobreescribe; cada corrección se apila en `contenido.enmiendas` con
    fecha y autor (Spec Médico §3/§8: "Enmienda auditada", "nunca borrado")."""
    record = await db.get(MedicalRecord, record_id)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Registro no encontrado")
    if record.professional_id != ctx.user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo puedes enmendar tus propios registros")

    contenido = dict(record.contenido)
    enmiendas = list(contenido.get("enmiendas", []))
    enmiendas.append({"nota": payload.nota, "fecha": datetime.now(timezone.utc).isoformat(), "por": str(ctx.user_id)})
    contenido["enmiendas"] = enmiendas
    record.contenido = contenido

    audit(db, ctx, clinic_id=record.clinic_id, accion="enmendar_prontuario", recurso=f"medical_record:{record.id}", despues={"nota": payload.nota})
    await db.commit()
    await db.refresh(record)
    return ProntuarioOut(id=record.id, contenido=record.contenido, creado=record.created_at)


# ─────────────────────────── prescripción ───────────────────────────
def _alertas_alergia(ficha: dict | None, items: list) -> list[AlertaClinica]:
    """Chequeo de alergia placeholder — substring del primer término de la
    alergia declarada contra el nombre del medicamento. Spec Médico §9 deja
    abierta la fuente del vademécum/interacciones; esto es lo mínimo seguro
    y testeable hasta entonces."""
    alertas: list[AlertaClinica] = []
    alergias_raw = (ficha or {}).get("alergias") or ""
    terminos = [t.strip().lower() for t in alergias_raw.replace(",", " ").split() if len(t.strip()) >= 4]
    for item in items:
        med = item.medicamento.lower()
        for termino in terminos:
            if termino in med:
                alertas.append(AlertaClinica(tipo="alergia", medicamento=item.medicamento, detalle=f"El paciente declara alergia a '{alergias_raw}'"))
                break
    return alertas


@router.post("/citas/{appointment_id}/prescripcion", response_model=PrescripcionResult)
async def emitir_prescripcion(
    appointment_id: uuid.UUID,
    payload: PrescripcionInput,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.PRESCRIPCIONES, Action.CREAR)),
) -> PrescripcionResult:
    appt = await get_own_appointment(db, ctx, appointment_id)
    patient = await db.get(Patient, appt.patient_id)

    alertas = _alertas_alergia(patient.ficha, payload.items)
    if alertas and not payload.confirmar_alertas:
        # Bloqueo clínico antes de firmar (Spec Médico §6). No se crea nada.
        return PrescripcionResult(prescripcion=None, alertas=alertas)

    record = await _ensure_record(db, ctx, appt)
    prescription = Prescription(
        clinic_id=appt.clinic_id,
        record_id=record.id,
        items=[i.model_dump() for i in payload.items],
        firmado_por=ctx.user_id,
        firmado_en=datetime.now(timezone.utc),
        estado="vigente",
    )
    db.add(prescription)
    audit(db, ctx, clinic_id=appt.clinic_id, accion="firmar_prescripcion", recurso=f"appointment:{appt.id}", despues={"items": len(payload.items), "alertas_confirmadas": bool(alertas)})
    await db.commit()
    await db.refresh(prescription)
    return PrescripcionResult(
        prescripcion=PrescripcionOut(id=prescription.id, items=prescription.items, estado=prescription.estado, firmado_en=prescription.firmado_en),
        alertas=alertas,
    )


@router.post("/prescripciones/{prescription_id}/reemitir", response_model=PrescripcionResult)
async def reemitir_prescripcion(
    prescription_id: uuid.UUID,
    payload: PrescripcionInput,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.PRESCRIPCIONES, Action.EDITAR)),
) -> PrescripcionResult:
    """Editar = anula + reemite (Spec Médico §3). La prescripción firmada es
    inmutable; corregirla anula la anterior y emite una nueva que la
    referencia (reemplaza_a)."""
    old = await db.get(Prescription, prescription_id)
    if old is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prescripción no encontrada")
    if old.firmado_por != ctx.user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo puedes reemitir tus propias prescripciones")
    if old.estado == "anulada":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Esa prescripción ya está anulada")

    record = await db.get(MedicalRecord, old.record_id)
    patient = await db.get(Patient, record.patient_id)
    alertas = _alertas_alergia(patient.ficha, payload.items)
    if alertas and not payload.confirmar_alertas:
        return PrescripcionResult(prescripcion=None, alertas=alertas)

    old.estado = "anulada"
    nueva = Prescription(
        clinic_id=old.clinic_id,
        record_id=old.record_id,
        items=[i.model_dump() for i in payload.items],
        firmado_por=ctx.user_id,
        firmado_en=datetime.now(timezone.utc),
        estado="vigente",
        reemplaza_a=old.id,
    )
    db.add(nueva)
    audit(db, ctx, clinic_id=old.clinic_id, accion="reemitir_prescripcion", recurso=f"prescription:{old.id}")
    await db.commit()
    await db.refresh(nueva)
    return PrescripcionResult(
        prescripcion=PrescripcionOut(id=nueva.id, items=nueva.items, estado=nueva.estado, firmado_en=nueva.firmado_en),
        alertas=alertas,
    )


# ─────────────────────────── órdenes de examen ───────────────────────────
@router.post("/citas/{appointment_id}/orden-examen", response_model=OrdenOut, status_code=status.HTTP_201_CREATED)
async def crear_orden(
    appointment_id: uuid.UUID,
    payload: OrdenInput,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.ORDENES_EXAMEN, Action.CREAR)),
) -> OrdenOut:
    appt = await get_own_appointment(db, ctx, appointment_id)
    order = ExamOrder(clinic_id=appt.clinic_id, patient_id=appt.patient_id, professional_id=ctx.user_id, tipo=payload.tipo, estado="pendiente")
    db.add(order)
    audit(db, ctx, clinic_id=appt.clinic_id, accion="crear_orden_examen", recurso=f"appointment:{appt.id}", despues={"tipo": payload.tipo})
    await db.commit()
    await db.refresh(order)
    return OrdenOut(id=order.id, tipo=order.tipo, estado=order.estado, creada=order.created_at)


async def _own_pending_order(db: AsyncSession, ctx: TenantContext, order_id: uuid.UUID) -> ExamOrder:
    order = await db.get(ExamOrder, order_id)
    if order is None or order.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Orden no encontrada")
    if order.professional_id != ctx.user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Esta orden no es tuya")
    if order.estado != "pendiente":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Solo se pueden modificar órdenes pendientes")
    return order


@router.patch("/ordenes/{order_id}", response_model=OrdenOut)
async def editar_orden(
    order_id: uuid.UUID,
    payload: OrdenInput,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.ORDENES_EXAMEN, Action.EDITAR)),
) -> OrdenOut:
    order = await _own_pending_order(db, ctx, order_id)
    order.tipo = payload.tipo
    await db.commit()
    await db.refresh(order)
    return OrdenOut(id=order.id, tipo=order.tipo, estado=order.estado, creada=order.created_at)


@router.patch("/ordenes/{order_id}/cancelar", response_model=OrdenOut)
async def cancelar_orden(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.ORDENES_EXAMEN, Action.ELIMINAR)),
) -> OrdenOut:
    order = await _own_pending_order(db, ctx, order_id)
    order.estado = "cancelada"
    await db.commit()
    await db.refresh(order)
    return OrdenOut(id=order.id, tipo=order.tipo, estado=order.estado, creada=order.created_at)


# ─────────────────────────── odontograma ───────────────────────────
@router.put("/pacientes/{patient_id}/odontograma", response_model=dict)
async def actualizar_odontograma(
    patient_id: uuid.UUID,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.PRONTUARIO_ATENDIDOS, Action.EDITAR)),
) -> dict:
    patient = await get_treated_patient(db, ctx, patient_id)
    piezas = payload.get("piezas")
    if not isinstance(piezas, dict):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Se espera { piezas: {...} }")
    odo = (await db.execute(select(Odontogram).where(Odontogram.patient_id == patient_id))).scalar_one_or_none()
    if odo is None:
        odo = Odontogram(clinic_id=patient.clinic_id, patient_id=patient_id, piezas=piezas)
        db.add(odo)
    else:
        odo.piezas = piezas
    audit(db, ctx, clinic_id=patient.clinic_id, accion="actualizar_odontograma", recurso=f"patient:{patient_id}")
    await db.commit()
    return {"piezas": piezas}


# ─────────────────────────── cierre / liquidación ───────────────────────────
@router.post("/citas/{appointment_id}/cerrar", response_model=CierreOut)
async def cerrar_atencion(
    appointment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.OWN_AGENDA, Action.EDITAR)),
) -> CierreOut:
    appt = await get_own_appointment(db, ctx, appointment_id)
    if appt.estado in ("completada", "cancelada", "no_show"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"La cita ya está {appt.estado}")

    appt.estado = "completada"
    service = await db.get(CatalogItem, appt.service_id) if appt.service_id else None
    split = await liquidar_atencion(db, clinic_id=appt.clinic_id, professional_id=ctx.user_id, service=service, appointment_id=appt.id)
    audit(db, ctx, clinic_id=appt.clinic_id, accion="cerrar_atencion", recurso=f"appointment:{appt.id}")
    await db.commit()
    return CierreOut(cita_id=appt.id, estado=appt.estado, split_monto=float(split.monto) if split else None)


@router.patch("/citas/{appointment_id}/no-show", response_model=CierreOut)
async def marcar_no_show(
    appointment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.OWN_AGENDA, Action.EDITAR)),
) -> CierreOut:
    appt = await get_own_appointment(db, ctx, appointment_id)
    if appt.estado in ("completada", "cancelada", "no_show"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"La cita ya está {appt.estado}")
    appt.estado = "no_show"
    audit(db, ctx, clinic_id=appt.clinic_id, accion="no_show", recurso=f"appointment:{appt.id}")
    await db.commit()
    return CierreOut(cita_id=appt.id, estado=appt.estado, split_monto=None)


@router.get("/liquidaciones", response_model=list[LiquidacionOut])
async def mis_liquidaciones(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.LIQUIDACION_PROPIA, Action.VER)),
) -> list[LiquidacionOut]:
    from app.models.finance import LedgerEntry, PaymentSplit

    rows = (
        await db.execute(
            select(PaymentSplit, LedgerEntry)
            .join(LedgerEntry, LedgerEntry.id == PaymentSplit.ledger_entry_id)
            .where(PaymentSplit.beneficiario_id == ctx.user_id, PaymentSplit.deleted_at.is_(None))
            .order_by(PaymentSplit.created_at.desc())
        )
    ).all()
    return [
        LiquidacionOut(
            fecha=split.created_at,
            monto=float(split.monto),
            base=(split.regla or {}).get("base"),
            ref=ledger.ref,
        )
        for split, ledger in rows
    ]
