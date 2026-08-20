import uuid
from datetime import datetime, time, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.catalog import CatalogItem, Specialty
from app.models.clinical import (
    Cie10Code,
    ClinicalDiagnosis,
    ClinicalDocument,
    DocumentTemplate,
    ExamOrder,
    ExamResult,
    Hospitalization,
    MedicalRecord,
    Odontogram,
    Periodontogram,
    Prescription,
    TreatmentPlan,
    TreatmentPlanItem,
    VitalSigns,
)
from app.models.identity import User
from app.models.patient import Patient
from app.models.professional import ProfessionalProfile
from app.models.scheduling import Appointment
from app.rbac.deps import require
from app.rbac.permissions import Action, Resource
from app.schemas.medico import (
    AlertaClinica,
    CierreOut,
    CitaMedicoOut,
    BloqueDoc,
    DocumentoIn,
    DocumentoOut,
    PlantillaDocIn,
    PlantillaDocOut,
    PlantillaDocUpdate,
    EnmiendaInput,
    PerioCatalogoOut,
    PeriodontogramaIn,
    PeriodontogramaOut,
    ExamenFichaOut,
    FichaPacienteOut,
    HospitalizacionFichaOut,
    Cie10Out,
    DiagnosticoIn,
    DiagnosticoOut,
    LiquidacionOut,
    MiFirmaIn,
    MiFirmaOut,
    OdontogramaCatalogoOut,
    OdontogramaUpdateInput,
    OrdenInput,
    OrdenOut,
    PlanEstadoIn,
    PlanResumen,
    PlanUpdate,
    PlanIn,
    PlanItemEstadoIn,
    PlanItemOut,
    PlanOut,
    PrescripcionInput,
    PrescripcionOut,
    PrescripcionResult,
    ProntuarioInput,
    ProntuarioOut,
    SignosVitalesIn,
    SignosVitalesOut,
    TimelineEvento,
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


# ─────────────────────────── odontograma (70.11) ───────────────────────────
# Catálogo de marcas del odontograma: caras de la pieza, diagnósticos y
# tratamientos por cara, estado de la pieza completa y estado del tratamiento.
ODO_CARAS = {"V": "Vestibular", "L": "Lingual / Palatino", "M": "Mesial", "D": "Distal", "O": "Oclusal / Incisal"}
ODO_DX = {
    "caries": "Caries", "fractura": "Fractura", "desgaste": "Desgaste",
    "rest_deficiente": "Restauración deficiente", "mancha": "Mancha / pigmentación",
}
ODO_TX = {
    "obturacion": "Obturación", "sellante": "Sellante", "corona": "Corona",
    "endodoncia": "Endodoncia", "extraccion": "Extracción", "implante": "Implante",
    "protesis": "Prótesis", "carilla": "Carilla",
}
ODO_PIEZA = {
    "sano": "Sano", "ausente": "Ausente", "extraccion_indicada": "Extracción indicada",
    "corona": "Corona", "implante": "Implante", "endodoncia": "Endodoncia",
    "resto_radicular": "Resto radicular",
}
ODO_TX_ESTADO = {"planificado": "Planificado", "realizado": "Realizado"}
# Dentición permanente FDI: cuadrantes 1–4, posiciones 1–8 (11–18, 21–28, 31–38, 41–48).
ODO_PIEZAS_VALIDAS = {f"{cuad}{pos}" for cuad in (1, 2, 3, 4) for pos in range(1, 9)}


def _marcas(catalogo: dict[str, str]) -> list[dict]:
    return [{"codigo": k, "label": v} for k, v in catalogo.items()]


@router.get("/odontograma/catalogo", response_model=OdontogramaCatalogoOut)
async def odontograma_catalogo(
    ctx: TenantContext = Depends(require(Resource.PRONTUARIO_ATENDIDOS, Action.VER)),
) -> OdontogramaCatalogoOut:
    return OdontogramaCatalogoOut(
        caras=_marcas(ODO_CARAS), diagnosticos=_marcas(ODO_DX), tratamientos=_marcas(ODO_TX),
        pieza_estados=_marcas(ODO_PIEZA), tx_estados=_marcas(ODO_TX_ESTADO),
    )


@router.put("/pacientes/{patient_id}/odontograma", response_model=dict)
async def actualizar_odontograma(
    patient_id: uuid.UUID,
    payload: OdontogramaUpdateInput,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.PRONTUARIO_ATENDIDOS, Action.EDITAR)),
) -> dict:
    patient = await get_treated_patient(db, ctx, patient_id)

    piezas: dict[str, dict] = {}
    for num, p in payload.piezas.items():
        if num not in ODO_PIEZAS_VALIDAS:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Pieza FDI inválida: {num}")
        if p.pieza is not None and p.pieza not in ODO_PIEZA:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Estado de pieza inválido: {p.pieza}")
        if p.estado is not None and p.estado not in ("pendiente", "tratada"):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Estado (legacy) inválido: {p.estado}")
        entrada: dict = {}
        if p.pieza is not None:
            entrada["pieza"] = p.pieza
        if p.estado is not None:
            entrada["estado"] = p.estado
        caras: dict[str, dict] = {}
        for cara, m in (p.caras or {}).items():
            if cara not in ODO_CARAS:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Cara inválida: {cara}")
            if m.dx is not None and m.dx not in ODO_DX:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Diagnóstico inválido: {m.dx}")
            if m.tx is not None and m.tx not in ODO_TX:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Tratamiento inválido: {m.tx}")
            if m.tx_estado is not None and m.tx_estado not in ODO_TX_ESTADO:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Estado de tratamiento inválido: {m.tx_estado}")
            marca = {k: v for k, v in (("dx", m.dx), ("tx", m.tx), ("tx_estado", m.tx_estado)) if v is not None}
            if marca:
                caras[cara] = marca
        if caras:
            entrada["caras"] = caras
        if entrada:  # no persistimos piezas vacías
            piezas[num] = entrada

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


# ═══════════════════════ Tanda 3: signos vitales ═══════════════════════
@router.post("/pacientes/{patient_id}/signos-vitales", response_model=SignosVitalesOut, status_code=status.HTTP_201_CREATED)
async def registrar_signos(
    patient_id: uuid.UUID,
    payload: SignosVitalesIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.PRONTUARIO_ATENDIDOS, Action.CREAR)),
) -> SignosVitalesOut:
    patient = await get_treated_patient(db, ctx, patient_id)
    v = VitalSigns(clinic_id=patient.clinic_id, patient_id=patient_id, professional_id=ctx.user_id, **payload.model_dump())
    db.add(v)
    audit(db, ctx, clinic_id=patient.clinic_id, accion="registrar_signos_vitales", recurso=f"patient:{patient_id}")
    await db.commit()
    await db.refresh(v)
    return _signos_out(v)


@router.get("/pacientes/{patient_id}/signos-vitales", response_model=list[SignosVitalesOut])
async def listar_signos(
    patient_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.PRONTUARIO_ATENDIDOS, Action.VER)),
) -> list[SignosVitalesOut]:
    patient = await get_treated_patient(db, ctx, patient_id)
    rows = (
        await db.execute(
            select(VitalSigns).where(VitalSigns.patient_id == patient_id, VitalSigns.deleted_at.is_(None)).order_by(VitalSigns.created_at.desc())
        )
    ).scalars().all()
    audit(db, ctx, clinic_id=patient.clinic_id, accion="ver_signos_vitales", recurso=f"patient:{patient_id}")
    await db.commit()
    return [_signos_out(v) for v in rows]


def _signos_out(v: VitalSigns) -> SignosVitalesOut:
    return SignosVitalesOut(
        id=v.id, fecha=v.created_at, appointment_id=v.appointment_id,
        presion_sistolica=v.presion_sistolica, presion_diastolica=v.presion_diastolica,
        fc_ppm=v.fc_ppm, fr_rpm=v.fr_rpm, spo2=v.spo2, glicemia=v.glicemia, eva=v.eva,
        peso_kg=float(v.peso_kg) if v.peso_kg is not None else None,
        talla_cm=float(v.talla_cm) if v.talla_cm is not None else None,
        temperatura=float(v.temperatura) if v.temperatura is not None else None,
        notas=v.notas,
    )


# ═══════════════════════ Timeline clínico unificado (70.1) ═══════════════════════
@router.get("/pacientes/{patient_id}/timeline", response_model=list[TimelineEvento])
async def timeline_clinico(
    patient_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.PRONTUARIO_ATENDIDOS, Action.VER)),
) -> list[TimelineEvento]:
    """Línea de tiempo del paciente: unifica en orden cronológico prontuarios,
    prescripciones, órdenes de examen (con su resultado), planes de tratamiento,
    periodontogramas, documentos clínicos y signos vitales — la historia clínica
    de un vistazo (70.1)."""
    patient = await get_treated_patient(db, ctx, patient_id)
    ev: list[TimelineEvento] = []

    # Prontuarios / evoluciones
    records = (
        await db.execute(
            select(MedicalRecord).where(MedicalRecord.patient_id == patient_id, MedicalRecord.deleted_at.is_(None))
        )
    ).scalars().all()
    for r in records:
        c = r.contenido or {}
        resumen = c.get("diagnostico") or c.get("evolucion") or None
        ev.append(TimelineEvento(tipo="prontuario", fecha=r.created_at, icono="📝",
                                  titulo=c.get("motivo") or "Atención clínica", resumen=resumen))

    # Prescripciones (vía el prontuario del paciente)
    record_ids = [r.id for r in records]
    if record_ids:
        pres = (
            await db.execute(
                select(Prescription).where(Prescription.record_id.in_(record_ids), Prescription.deleted_at.is_(None))
            )
        ).scalars().all()
        for p in pres:
            items = p.items if isinstance(p.items, list) else (p.items or {}).get("items", [])
            n = len(items) if isinstance(items, list) else 0
            ev.append(TimelineEvento(tipo="prescripcion", fecha=p.firmado_en or p.created_at, icono="💊",
                                     titulo="Receta médica", resumen=f"{n} medicamento(s)", estado=p.estado))

    # Órdenes de examen + resultado
    ordenes = (
        await db.execute(
            select(ExamOrder).where(ExamOrder.patient_id == patient_id, ExamOrder.deleted_at.is_(None))
        )
    ).scalars().all()
    for o in ordenes:
        res = (
            await db.execute(
                select(ExamResult).where(ExamResult.order_id == o.id, ExamResult.deleted_at.is_(None)).order_by(ExamResult.created_at.desc()).limit(1)
            )
        ).scalars().first()
        resumen = None
        if res is not None:
            nombre = (res.resultado or {}).get("nombre") if isinstance(res.resultado, dict) else None
            resumen = f"Resultado: {nombre}" if nombre else "Resultado disponible"
        ev.append(TimelineEvento(tipo="orden_examen", fecha=o.created_at, icono="🔬",
                                 titulo=f"Orden de {o.tipo}", resumen=resumen, estado=o.estado))

    # Planes de tratamiento
    planes = (
        await db.execute(
            select(TreatmentPlan).where(TreatmentPlan.patient_id == patient_id, TreatmentPlan.deleted_at.is_(None))
        )
    ).scalars().all()
    for pl in planes:
        n = (
            await db.execute(
                select(func.count(TreatmentPlanItem.id)).where(TreatmentPlanItem.plan_id == pl.id, TreatmentPlanItem.deleted_at.is_(None))
            )
        ).scalar_one()
        ev.append(TimelineEvento(tipo="plan", fecha=pl.created_at, icono="🦷",
                                 titulo=f"Plan: {pl.titulo}", resumen=f"{n} ítem(s)", estado=pl.estado))

    # Periodontogramas
    perios = (
        await db.execute(
            select(Periodontogram).where(Periodontogram.patient_id == patient_id, Periodontogram.deleted_at.is_(None))
        )
    ).scalars().all()
    for pe in perios:
        n = len(pe.datos or {})
        ev.append(TimelineEvento(tipo="periodontograma", fecha=pe.created_at, icono="🦷",
                                 titulo="Periodontograma", resumen=f"{n} pieza(s) registradas"))

    # Documentos clínicos
    docs = (
        await db.execute(
            select(ClinicalDocument).where(ClinicalDocument.patient_id == patient_id, ClinicalDocument.deleted_at.is_(None))
        )
    ).scalars().all()
    for d in docs:
        ev.append(TimelineEvento(tipo="documento", fecha=d.created_at, icono="📄",
                                 titulo=d.titulo, resumen=d.tipo.capitalize(), estado=d.estado))

    # Signos vitales
    signos = (
        await db.execute(
            select(VitalSigns).where(VitalSigns.patient_id == patient_id, VitalSigns.deleted_at.is_(None))
        )
    ).scalars().all()
    for s in signos:
        partes = []
        if s.presion_sistolica and s.presion_diastolica:
            partes.append(f"PA {s.presion_sistolica}/{s.presion_diastolica}")
        if s.fc_ppm:
            partes.append(f"FC {s.fc_ppm}")
        if s.spo2:
            partes.append(f"SpO₂ {s.spo2}%")
        if s.temperatura is not None:
            partes.append(f"T {float(s.temperatura)}°")
        ev.append(TimelineEvento(tipo="signos", fecha=s.created_at, icono="❤️",
                                 titulo="Signos vitales", resumen=" · ".join(partes) or None))

    audit(db, ctx, clinic_id=patient.clinic_id, accion="ver_timeline", recurso=f"patient:{patient_id}")
    await db.commit()

    ev.sort(key=lambda e: e.fecha, reverse=True)
    return ev


# ═══════════════════════ Tanda 3: planes de tratamiento ═══════════════════════
PLAN_ESTADOS = {"propuesto", "aceptado", "en_curso", "completado", "rechazado"}


async def _plan_out(db: AsyncSession, plan: TreatmentPlan) -> PlanOut:
    items = (
        await db.execute(
            select(TreatmentPlanItem).where(TreatmentPlanItem.plan_id == plan.id, TreatmentPlanItem.deleted_at.is_(None)).order_by(TreatmentPlanItem.created_at)
        )
    ).scalars().all()
    items_out = [
        PlanItemOut(
            id=i.id, descripcion=i.descripcion, pieza=i.pieza, cantidad=i.cantidad,
            precio_unit=float(i.precio_unit), service_id=i.service_id, estado=i.estado,
            subtotal=round(i.cantidad * float(i.precio_unit), 2),
        )
        for i in items
    ]
    total = round(sum(x.subtotal for x in items_out), 2)
    realizado = round(sum(x.subtotal for x in items_out if x.estado == "realizado"), 2)
    descuento_pct = float(plan.descuento_pct or 0)
    descuento = round(total * descuento_pct, 2)
    total_neto = round(total - descuento, 2)

    from app.models.finance import CashPayment
    abonado = (
        await db.execute(
            select(func.coalesce(func.sum(CashPayment.monto), 0)).where(
                CashPayment.treatment_plan_id == plan.id,
                CashPayment.deleted_at.is_(None),
                CashPayment.anulado.is_(False),
                CashPayment.tipo == "pago",
            )
        )
    ).scalar_one()
    abonado = round(float(abonado), 2)
    resumen = PlanResumen(
        total_bruto=total, descuento_pct=descuento_pct, descuento=descuento, total_neto=total_neto,
        realizado=realizado, abonado=abonado, saldo=round(total_neto - abonado, 2),
        progreso_pct=round(realizado / total, 4) if total > 0 else 0.0,
    )
    return PlanOut(
        id=plan.id, titulo=plan.titulo, estado=plan.estado, notas=plan.notas, total=total,
        descuento_pct=descuento_pct, items=items_out, resumen=resumen, fecha=plan.created_at,
    )


async def _own_plan(db: AsyncSession, ctx: TenantContext, plan_id: uuid.UUID) -> TreatmentPlan:
    plan = await db.get(TreatmentPlan, plan_id)
    if plan is None or plan.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Plan no encontrado")
    await get_treated_patient(db, ctx, plan.patient_id)  # valida relación de tratamiento + clínica
    return plan


@router.get("/pacientes/{patient_id}/planes", response_model=list[PlanOut])
async def listar_planes(
    patient_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.PRONTUARIO_ATENDIDOS, Action.VER)),
) -> list[PlanOut]:
    patient = await get_treated_patient(db, ctx, patient_id)
    planes = (
        await db.execute(
            select(TreatmentPlan).where(TreatmentPlan.patient_id == patient_id, TreatmentPlan.deleted_at.is_(None)).order_by(TreatmentPlan.created_at.desc())
        )
    ).scalars().all()
    audit(db, ctx, clinic_id=patient.clinic_id, accion="ver_planes_tratamiento", recurso=f"patient:{patient_id}")
    await db.commit()
    return [await _plan_out(db, p) for p in planes]


@router.post("/pacientes/{patient_id}/planes", response_model=PlanOut, status_code=status.HTTP_201_CREATED)
async def crear_plan(
    patient_id: uuid.UUID,
    payload: PlanIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.PRONTUARIO_ATENDIDOS, Action.CREAR)),
) -> PlanOut:
    patient = await get_treated_patient(db, ctx, patient_id)
    plan = TreatmentPlan(clinic_id=patient.clinic_id, patient_id=patient_id, professional_id=ctx.user_id, titulo=payload.titulo, notas=payload.notas)
    db.add(plan)
    await db.flush()
    for it in payload.items:
        db.add(TreatmentPlanItem(clinic_id=patient.clinic_id, plan_id=plan.id, **it.model_dump()))
    audit(db, ctx, clinic_id=patient.clinic_id, accion="crear_plan_tratamiento", recurso=f"patient:{patient_id}")
    await db.commit()
    await db.refresh(plan)
    return await _plan_out(db, plan)


@router.patch("/planes/{plan_id}", response_model=PlanOut)
async def editar_plan(
    plan_id: uuid.UUID,
    payload: PlanUpdate,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.PRONTUARIO_ATENDIDOS, Action.EDITAR)),
) -> PlanOut:
    """Edita el plan: título, notas y **descuento comercial** (69.7)."""
    plan = await _own_plan(db, ctx, plan_id)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(plan, k, v)
    audit(db, ctx, clinic_id=plan.clinic_id, accion="editar_plan_tratamiento", recurso=f"treatment_plan:{plan.id}")
    await db.commit()
    await db.refresh(plan)
    return await _plan_out(db, plan)


@router.patch("/planes/{plan_id}/estado", response_model=PlanOut)
async def cambiar_estado_plan(
    plan_id: uuid.UUID,
    payload: PlanEstadoIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.PRONTUARIO_ATENDIDOS, Action.EDITAR)),
) -> PlanOut:
    if payload.estado not in PLAN_ESTADOS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Estado inválido: {payload.estado}")
    plan = await _own_plan(db, ctx, plan_id)
    plan.estado = payload.estado
    audit(db, ctx, clinic_id=plan.clinic_id, accion="cambiar_estado_plan", recurso=f"treatment_plan:{plan.id}")
    await db.commit()
    await db.refresh(plan)
    return await _plan_out(db, plan)


@router.patch("/planes/{plan_id}/items/{item_id}/estado", response_model=PlanOut)
async def cambiar_estado_item(
    plan_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: PlanItemEstadoIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.PRONTUARIO_ATENDIDOS, Action.EDITAR)),
) -> PlanOut:
    if payload.estado not in ("pendiente", "realizado"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Estado inválido (pendiente | realizado)")
    plan = await _own_plan(db, ctx, plan_id)
    item = await db.get(TreatmentPlanItem, item_id)
    if item is None or item.plan_id != plan.id or item.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ítem no encontrado")
    item.estado = payload.estado
    audit(db, ctx, clinic_id=plan.clinic_id, accion="cambiar_estado_item_plan", recurso=f"treatment_plan_item:{item.id}")
    await db.commit()
    await db.refresh(plan)
    return await _plan_out(db, plan)


# ═══════════════════════ Tanda 5 / punto 64: documentos clínicos ═══════════════════════
DOC_TIPOS = {"consentimiento", "licencia", "interconsulta", "certificado", "otro"}


def _doc_out(d: ClinicalDocument) -> DocumentoOut:
    return DocumentoOut(
        id=d.id, tipo=d.tipo, titulo=d.titulo, contenido=d.contenido, estado=d.estado, fecha=d.created_at,
        requiere_firma=d.requiere_firma, firmado_paciente=d.firmado_paciente, firmado_at=d.firmado_at,
        firma_profesional=d.firma_profesional,
    )


async def _mi_firma(db: AsyncSession, ctx: TenantContext) -> str | None:
    """Firma manuscrita del profesional (48), tomada de su perfil profesional
    (cualquiera de sus clínicas). None si aún no la ha dibujado."""
    row = (
        await db.execute(
            select(ProfessionalProfile.firma).where(
                ProfessionalProfile.user_id == ctx.user_id,
                ProfessionalProfile.firma.isnot(None),
                ProfessionalProfile.deleted_at.is_(None),
            ).limit(1)
        )
    ).scalar_one_or_none()
    return row


def _medico_clinic_id(ctx: TenantContext) -> uuid.UUID:
    ids = ctx.clinic_ids()
    if not ids:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "La cuenta no tiene una clínica asignada")
    return next(iter(ids))


def _render_bloques(bloques: list, campos: dict | None) -> str:
    """Arma el contenido del documento desde los bloques de la plantilla,
    rellenando los campos con los valores provistos (64.3)."""
    campos = campos or {}
    partes: list[str] = []
    for b in bloques or []:
        b = b if isinstance(b, dict) else dict(b)
        if b.get("tipo") == "campo":
            clave = b.get("clave") or b.get("label") or ""
            valor = campos.get(clave, "")
            partes.append(f"{b.get('label') or clave}: {valor}".strip())
        else:
            partes.append((b.get("texto") or "").strip())
    return "\n\n".join(p for p in partes if p)


def _plantilla_out(t: DocumentTemplate) -> PlantillaDocOut:
    return PlantillaDocOut(
        id=t.id, nombre=t.nombre, tipo=t.tipo,
        bloques=[BloqueDoc(**b) if isinstance(b, dict) else b for b in (t.bloques or [])],
        requiere_firma=t.requiere_firma, activo=t.activo,
    )


@router.get("/plantillas-documento", response_model=list[PlantillaDocOut])
async def listar_plantillas_doc(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.PRONTUARIO_ATENDIDOS, Action.VER)),
) -> list[PlantillaDocOut]:
    cid = _medico_clinic_id(ctx)
    rows = (await db.execute(select(DocumentTemplate).where(DocumentTemplate.clinic_id == cid, DocumentTemplate.deleted_at.is_(None)).order_by(DocumentTemplate.nombre))).scalars().all()
    return [_plantilla_out(t) for t in rows]


@router.post("/plantillas-documento", response_model=PlantillaDocOut, status_code=status.HTTP_201_CREATED)
async def crear_plantilla_doc(
    payload: PlantillaDocIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.PRONTUARIO_ATENDIDOS, Action.CREAR)),
) -> PlantillaDocOut:
    cid = _medico_clinic_id(ctx)
    t = DocumentTemplate(
        clinic_id=cid, nombre=payload.nombre, tipo=payload.tipo,
        bloques=[b.model_dump() for b in payload.bloques], requiere_firma=payload.requiere_firma,
    )
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return _plantilla_out(t)


async def _own_plantilla(db: AsyncSession, cid: uuid.UUID, tid: uuid.UUID) -> DocumentTemplate:
    t = await db.get(DocumentTemplate, tid)
    if t is None or t.clinic_id != cid or t.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Plantilla no encontrada")
    return t


@router.patch("/plantillas-documento/{tid}", response_model=PlantillaDocOut)
async def editar_plantilla_doc(
    tid: uuid.UUID,
    payload: PlantillaDocUpdate,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.PRONTUARIO_ATENDIDOS, Action.EDITAR)),
) -> PlantillaDocOut:
    cid = _medico_clinic_id(ctx)
    t = await _own_plantilla(db, cid, tid)
    if payload.nombre is not None:
        t.nombre = payload.nombre
    if payload.tipo is not None:
        t.tipo = payload.tipo
    if payload.bloques is not None:
        t.bloques = [b.model_dump() for b in payload.bloques]
    if payload.requiere_firma is not None:
        t.requiere_firma = payload.requiere_firma
    if payload.activo is not None:
        t.activo = payload.activo
    await db.commit()
    await db.refresh(t)
    return _plantilla_out(t)


@router.delete("/plantillas-documento/{tid}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_plantilla_doc(
    tid: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.PRONTUARIO_ATENDIDOS, Action.EDITAR)),
) -> None:
    cid = _medico_clinic_id(ctx)
    t = await _own_plantilla(db, cid, tid)
    await db.delete(t)  # baja lógica vía listener global
    await db.commit()


@router.get("/pacientes/{patient_id}/documentos", response_model=list[DocumentoOut])
async def listar_documentos(
    patient_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.PRONTUARIO_ATENDIDOS, Action.VER)),
) -> list[DocumentoOut]:
    patient = await get_treated_patient(db, ctx, patient_id)
    rows = (
        await db.execute(
            select(ClinicalDocument).where(ClinicalDocument.patient_id == patient_id, ClinicalDocument.deleted_at.is_(None)).order_by(ClinicalDocument.created_at.desc())
        )
    ).scalars().all()
    audit(db, ctx, clinic_id=patient.clinic_id, accion="ver_documentos_clinicos", recurso=f"patient:{patient_id}")
    await db.commit()
    return [_doc_out(d) for d in rows]


@router.post("/pacientes/{patient_id}/documentos", response_model=DocumentoOut, status_code=status.HTTP_201_CREATED)
async def crear_documento(
    patient_id: uuid.UUID,
    payload: DocumentoIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.PRONTUARIO_ATENDIDOS, Action.CREAR)),
) -> DocumentoOut:
    patient = await get_treated_patient(db, ctx, patient_id)

    tipo = payload.tipo
    contenido = payload.contenido
    requiere_firma = bool(payload.requiere_firma)
    if payload.template_id is not None:
        tmpl = await db.get(DocumentTemplate, payload.template_id)
        if tmpl is None or tmpl.clinic_id != patient.clinic_id or tmpl.deleted_at is not None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Plantilla inválida")
        tipo = tmpl.tipo
        if not contenido:
            contenido = _render_bloques(tmpl.bloques, payload.campos)
        requiere_firma = payload.requiere_firma if payload.requiere_firma is not None else tmpl.requiere_firma

    if tipo not in DOC_TIPOS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Tipo inválido: {tipo}")
    doc = ClinicalDocument(
        clinic_id=patient.clinic_id, patient_id=patient_id, professional_id=ctx.user_id,
        tipo=tipo, titulo=payload.titulo, contenido=contenido,
        template_id=payload.template_id, requiere_firma=requiere_firma,
        firma_profesional=await _mi_firma(db, ctx),  # instantánea inmutable de la firma
    )
    db.add(doc)
    audit(db, ctx, clinic_id=patient.clinic_id, accion="crear_documento_clinico", recurso=f"patient:{patient_id}")
    await db.commit()
    await db.refresh(doc)
    return _doc_out(doc)


@router.patch("/documentos/{doc_id}/anular", response_model=DocumentoOut)
async def anular_documento(
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.PRONTUARIO_ATENDIDOS, Action.EDITAR)),
) -> DocumentoOut:
    doc = await db.get(ClinicalDocument, doc_id)
    if doc is None or doc.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento no encontrado")
    await get_treated_patient(db, ctx, doc.patient_id)  # valida tratamiento + clínica
    doc.estado = "anulado"
    audit(db, ctx, clinic_id=doc.clinic_id, accion="anular_documento_clinico", recurso=f"clinical_document:{doc.id}")
    await db.commit()
    await db.refresh(doc)
    return _doc_out(doc)


# ═══════════════════════ Firma manuscrita del profesional (48) ═══════════════════════
async def _mis_perfiles(db: AsyncSession, ctx: TenantContext) -> list[ProfessionalProfile]:
    return list(
        (
            await db.execute(
                select(ProfessionalProfile).where(
                    ProfessionalProfile.user_id == ctx.user_id, ProfessionalProfile.deleted_at.is_(None)
                )
            )
        ).scalars().all()
    )


@router.get("/mi-firma", response_model=MiFirmaOut)
async def ver_mi_firma(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.OWN_AGENDA, Action.VER)),
) -> MiFirmaOut:
    """El profesional consulta su firma manuscrita y su especialidad."""
    perfiles = await _mis_perfiles(db, ctx)
    firma = next((p.firma for p in perfiles if p.firma), None)
    especialidad = None
    spec_id = next((p.specialty_id for p in perfiles if p.specialty_id), None)
    if spec_id is not None:
        especialidad = (await db.execute(select(Specialty.nombre).where(Specialty.id == spec_id))).scalar_one_or_none()
    return MiFirmaOut(firma=firma, especialidad=especialidad)


@router.put("/mi-firma", response_model=MiFirmaOut)
async def guardar_mi_firma(
    payload: MiFirmaIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.OWN_AGENDA, Action.EDITAR)),
) -> MiFirmaOut:
    """El profesional dibuja su firma en la app y la guarda. Se aplica a su
    perfil en cada clínica donde trabaja; si aún no tenía perfil, se crea uno."""
    if payload.firma is not None and len(payload.firma) > 2_000_000:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "La firma es demasiado grande")
    perfiles = await _mis_perfiles(db, ctx)
    if perfiles:
        for p in perfiles:
            p.firma = payload.firma
    else:
        ids = ctx.clinic_ids()
        if not ids:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "La cuenta no tiene una clínica asignada")
        for cid in ids:
            db.add(ProfessionalProfile(clinic_id=cid, user_id=ctx.user_id, firma=payload.firma))
    await db.commit()
    return MiFirmaOut(firma=payload.firma, especialidad=None)


# ═══════════════════════ Diagnóstico CIE-10 (71.20) ═══════════════════════
_DX_TIPOS = {"principal", "secundario"}


@router.get("/cie10", response_model=list[Cie10Out])
async def buscar_cie10(
    q: str = "",
    limit: int = 30,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.PRONTUARIO_ATENDIDOS, Action.VER)),
) -> list[Cie10Out]:
    """Busca en el catálogo CIE-10 por código o descripción (71.20)."""
    limit = max(1, min(limit, 100))
    stmt = select(Cie10Code).where(Cie10Code.activo.is_(True), Cie10Code.deleted_at.is_(None))
    q = q.strip()
    if q:
        patron = f"%{q}%"
        stmt = stmt.where(or_(Cie10Code.codigo.ilike(patron), Cie10Code.descripcion.ilike(patron)))
    rows = (await db.execute(stmt.order_by(Cie10Code.codigo).limit(limit))).scalars().all()
    return [Cie10Out(id=c.id, codigo=c.codigo, descripcion=c.descripcion, categoria=c.categoria) for c in rows]


def _dx_out(d: ClinicalDiagnosis, code: Cie10Code) -> DiagnosticoOut:
    return DiagnosticoOut(
        id=d.id, codigo=code.codigo, descripcion=code.descripcion, categoria=code.categoria,
        tipo=d.tipo, observacion=d.observacion, fecha=d.created_at,
    )


@router.get("/pacientes/{patient_id}/diagnosticos", response_model=list[DiagnosticoOut])
async def listar_diagnosticos(
    patient_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.PRONTUARIO_ATENDIDOS, Action.VER)),
) -> list[DiagnosticoOut]:
    await get_treated_patient(db, ctx, patient_id)
    rows = (
        await db.execute(
            select(ClinicalDiagnosis, Cie10Code)
            .join(Cie10Code, Cie10Code.id == ClinicalDiagnosis.cie10_id)
            .where(ClinicalDiagnosis.patient_id == patient_id, ClinicalDiagnosis.deleted_at.is_(None))
            .order_by(ClinicalDiagnosis.created_at.desc())
        )
    ).all()
    return [_dx_out(d, c) for d, c in rows]


@router.post("/pacientes/{patient_id}/diagnosticos", response_model=DiagnosticoOut, status_code=status.HTTP_201_CREATED)
async def agregar_diagnostico(
    patient_id: uuid.UUID,
    payload: DiagnosticoIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.PRONTUARIO_ATENDIDOS, Action.CREAR)),
) -> DiagnosticoOut:
    patient = await get_treated_patient(db, ctx, patient_id)
    if payload.tipo not in _DX_TIPOS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Tipo inválido (principal | secundario)")
    code = (await db.execute(select(Cie10Code).where(Cie10Code.codigo == payload.codigo, Cie10Code.deleted_at.is_(None)))).scalar_one_or_none()
    if code is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Código CIE-10 inexistente: {payload.codigo}")
    if payload.record_id is not None:
        rec = await db.get(MedicalRecord, payload.record_id)
        if rec is None or rec.patient_id != patient_id or rec.deleted_at is not None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Atención inválida")
    dx = ClinicalDiagnosis(
        clinic_id=patient.clinic_id, patient_id=patient_id, professional_id=ctx.user_id,
        record_id=payload.record_id, cie10_id=code.id, tipo=payload.tipo, observacion=payload.observacion,
    )
    db.add(dx)
    audit(db, ctx, clinic_id=patient.clinic_id, accion="agregar_diagnostico_cie10", recurso=f"patient:{patient_id}", despues={"codigo": code.codigo})
    await db.commit()
    await db.refresh(dx)
    return _dx_out(dx, code)


@router.delete("/diagnosticos/{dx_id}", status_code=status.HTTP_204_NO_CONTENT)
async def quitar_diagnostico(
    dx_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.PRONTUARIO_ATENDIDOS, Action.EDITAR)),
) -> None:
    dx = await db.get(ClinicalDiagnosis, dx_id)
    if dx is None or dx.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Diagnóstico no encontrado")
    await get_treated_patient(db, ctx, dx.patient_id)  # valida atención + clínica
    await db.delete(dx)  # baja lógica vía listener global
    audit(db, ctx, clinic_id=dx.clinic_id, accion="quitar_diagnostico_cie10", recurso=f"clinical_diagnosis:{dx.id}")
    await db.commit()


# ═══════════════════════ Periodontograma completo (70.5) ═══════════════════════
# 6 sitios por pieza: mesio/centro/disto por vestibular (mv/v/dv) y por
# palatino/lingual (mp/p/dp).
PERIO_SITIOS = {
    "mv": "Mesio-vestibular", "v": "Vestibular", "dv": "Disto-vestibular",
    "mp": "Mesio-palatino/lingual", "p": "Palatino/Lingual", "dp": "Disto-palatino/lingual",
}
PERIO_PS_MAX = 15
PERIO_MOV_MAX = 3
PERIO_FURCA_MAX = 3
_FDI_PERIO = {f"{q}.{p}" for q in (1, 2, 3, 4) for p in range(1, 9)}


@router.get("/periodontograma/catalogo", response_model=PerioCatalogoOut)
async def periodontograma_catalogo(
    ctx: TenantContext = Depends(require(Resource.PRONTUARIO_ATENDIDOS, Action.VER)),
) -> PerioCatalogoOut:
    return PerioCatalogoOut(
        sitios=[{"codigo": k, "label": v} for k, v in PERIO_SITIOS.items()],
        ps_max=PERIO_PS_MAX, movilidad_max=PERIO_MOV_MAX, furca_max=PERIO_FURCA_MAX,
    )


def _validar_perio(datos) -> dict:
    """Valida y normaliza los datos del periodontograma (70.5)."""
    def _rango(v, lo, hi, etiqueta):
        if v is not None and not (lo <= v <= hi):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"{etiqueta} fuera de rango ({lo}–{hi}): {v}")

    out: dict[str, dict] = {}
    for pieza, p in datos.items():
        if pieza not in _FDI_PERIO:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Pieza FDI inválida: {pieza}")
        _rango(p.movilidad, 0, PERIO_MOV_MAX, "Movilidad")
        _rango(p.furca, 0, PERIO_FURCA_MAX, "Furca")
        _rango(p.ps, 0, PERIO_PS_MAX, "Profundidad")
        entrada: dict = {}
        for campo, val in (("ps", p.ps), ("sangrado", p.sangrado), ("movilidad", p.movilidad), ("furca", p.furca)):
            if val is not None:
                entrada[campo] = val
        sitios: dict[str, dict] = {}
        for sitio, s in (p.sitios or {}).items():
            if sitio not in PERIO_SITIOS:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Sitio inválido: {sitio}")
            _rango(s.ps, 0, PERIO_PS_MAX, "Profundidad")
            _rango(s.rec, -5, PERIO_PS_MAX, "Recesión")
            marca = {k: v for k, v in (("ps", s.ps), ("rec", s.rec), ("sangrado", s.sangrado), ("placa", s.placa), ("supuracion", s.supuracion)) if v is not None}
            if marca:
                sitios[sitio] = marca
        if sitios:
            entrada["sitios"] = sitios
        if entrada:
            out[pieza] = entrada
    return out


@router.get("/pacientes/{patient_id}/periodontograma", response_model=PeriodontogramaOut | None)
async def ultimo_periodontograma(
    patient_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.PRONTUARIO_ATENDIDOS, Action.VER)),
) -> PeriodontogramaOut | None:
    patient = await get_treated_patient(db, ctx, patient_id)
    rows = (
        await db.execute(
            select(Periodontogram).where(Periodontogram.patient_id == patient_id, Periodontogram.deleted_at.is_(None)).order_by(Periodontogram.created_at.desc())
        )
    ).scalars().all()
    audit(db, ctx, clinic_id=patient.clinic_id, accion="ver_periodontograma", recurso=f"patient:{patient_id}")
    await db.commit()
    if not rows:
        return None
    p = rows[0]
    return PeriodontogramaOut(id=p.id, datos=p.datos, notas=p.notas, fecha=p.created_at, tomas_anteriores=len(rows) - 1)


@router.post("/pacientes/{patient_id}/periodontograma", response_model=PeriodontogramaOut, status_code=status.HTTP_201_CREATED)
async def guardar_periodontograma(
    patient_id: uuid.UUID,
    payload: PeriodontogramaIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.PRONTUARIO_ATENDIDOS, Action.CREAR)),
) -> PeriodontogramaOut:
    patient = await get_treated_patient(db, ctx, patient_id)
    datos = _validar_perio(payload.datos)
    p = Periodontogram(clinic_id=patient.clinic_id, patient_id=patient_id, professional_id=ctx.user_id, datos=datos, notas=payload.notas)
    db.add(p)
    audit(db, ctx, clinic_id=patient.clinic_id, accion="guardar_periodontograma", recurso=f"patient:{patient_id}")
    await db.commit()
    await db.refresh(p)
    prev = (
        await db.execute(select(func.count(Periodontogram.id)).where(Periodontogram.patient_id == patient_id, Periodontogram.deleted_at.is_(None)))
    ).scalar_one()
    return PeriodontogramaOut(id=p.id, datos=p.datos, notas=p.notas, fecha=p.created_at, tomas_anteriores=int(prev) - 1)
