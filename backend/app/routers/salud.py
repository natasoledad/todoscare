import secrets
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.integrations import ia_clinica
from app.integrations.base import log_event
from app.models.clinical import AiFichaSuggestion, ClinicalDocument, EmergencyQr, ExamOrder, ExamResult, Hospitalization, Odontogram, QrAccessLog
from app.models.identity import User
from app.rbac.deps import require, require_any_medico
from app.rbac.permissions import Action, Resource
from app.routers.patients import get_own_patient
from app.schemas.salud import (
    DocumentoPacienteOut,
    EmergencyQrOut,
    ExamenOut,
    HospitalizacionOut,
    OdontogramaOut,
    QrAccessLogOut,
    QrResolveOut,
)
from app.services.gamification import award
from app.tenancy.context import TenantContext

router = APIRouter(prefix="/salud", tags=["salud"])

UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


@router.get("/examenes", response_model=list[ExamenOut])
async def list_examenes(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.OWN_EXAM_RESULTS, Action.VER)),
) -> list[ExamenOut]:
    patient = await get_own_patient(db, ctx)
    rows = (
        await db.execute(
            select(ExamOrder, ExamResult)
            .join(ExamResult, ExamResult.order_id == ExamOrder.id, isouter=True)
            .where(ExamOrder.patient_id == patient.id, ExamOrder.deleted_at.is_(None))
            .order_by(ExamOrder.created_at.desc())
        )
    ).all()
    out = []
    for order, result in rows:
        out.append(
            ExamenOut(
                id=order.id,
                nombre=(result.resultado or {}).get("nombre", order.tipo.capitalize()) if result else order.tipo.capitalize(),
                fecha=order.created_at,
                estado=(result.estado if result else order.estado),
                archivo_url=result.archivo_url if result else None,
            )
        )
    return out


@router.post("/examenes/subir", response_model=ExamenOut, status_code=status.HTTP_201_CREATED)
async def subir_examen(
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.OWN_EXAM_RESULTS, Action.CREAR)),
) -> ExamenOut:
    """Real file upload; the "IA extrae los datos" step from Spec Paciente
    §5.2 is not implemented (no OCR/IA integration exists yet — that's Fase
    8). The upload itself is real and immediately visible in "Mis exámenes"."""
    patient = await get_own_patient(db, ctx)

    safe_name = f"{uuid.uuid4().hex}_{Path(file.filename or 'archivo').name}"
    dest = UPLOAD_DIR / safe_name
    contents = await file.read()
    dest.write_bytes(contents)

    order = ExamOrder(clinic_id=patient.clinic_id, patient_id=patient.id, professional_id=ctx.user_id, tipo="subido_por_paciente", estado="listo")
    db.add(order)
    await db.flush()

    result = ExamResult(
        clinic_id=patient.clinic_id,
        order_id=order.id,
        archivo_url=f"/files/{safe_name}",
        resultado={"nombre": file.filename or "Documento subido"},
        estado="listo",
    )
    db.add(result)

    wallet = await _get_wallet(db, patient.id)
    await award(db, wallet=wallet, patient=patient, tipo="examen_subido", puntos=20, motivo="Subiste un documento a tu ficha", ref_id=order.id)

    # IA clínica (72): si la clínica tiene el conector activo, analiza el
    # documento y deja una sugerencia (parche de ficha + próximo control) que
    # el paciente confirmará. No auto-aplica: queda trazable y reversible.
    if await ia_clinica.config_activa(db, patient.clinic_id):
        analisis = await ia_clinica.analizar_examen(file.filename or "", contenido=contents, content_type=file.content_type)
        meses = analisis["proximo_control_meses"]
        proximo = (datetime.now(timezone.utc).date() + timedelta(days=30 * meses))
        db.add(AiFichaSuggestion(
            clinic_id=patient.clinic_id, patient_id=patient.id, exam_order_id=order.id,
            resumen=analisis["resumen"], hallazgos=analisis["hallazgos"], proximo_control=proximo, estado="pendiente",
        ))
        log_event(db, clinic_id=patient.clinic_id, tipo=ia_clinica.TIPO, direccion="inbound",
                  ref=f"exam:{order.id}", payload={"nombre": file.filename}, resultado=analisis)

    await db.commit()
    await db.refresh(order)
    return ExamenOut(id=order.id, nombre=file.filename or "Documento subido", fecha=order.created_at, estado="listo", archivo_url=result.archivo_url)


@router.get("/dental", response_model=OdontogramaOut)
async def get_dental(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.OWN_MEDICAL_RECORD, Action.VER)),
) -> OdontogramaOut:
    patient = await get_own_patient(db, ctx)
    row = (await db.execute(select(Odontogram).where(Odontogram.patient_id == patient.id))).scalar_one_or_none()
    if row is None:
        return OdontogramaOut(piezas={})
    return OdontogramaOut(piezas=row.piezas)


@router.get("/hospitalizaciones", response_model=list[HospitalizacionOut])
async def list_hospitalizaciones(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.OWN_MEDICAL_RECORD, Action.VER)),
) -> list[HospitalizacionOut]:
    patient = await get_own_patient(db, ctx)
    rows = (
        await db.execute(
            select(Hospitalization)
            .where(Hospitalization.patient_id == patient.id, Hospitalization.deleted_at.is_(None))
            .order_by(Hospitalization.ingreso.desc())
        )
    ).scalars().all()
    return [HospitalizacionOut(id=h.id, motivo=h.motivo, centro=h.centro, ingreso=h.ingreso, egreso=h.egreso) for h in rows]


# ---- documentos clínicos del paciente + firma (64.8) ----
def _doc_pac_out(d: ClinicalDocument) -> DocumentoPacienteOut:
    return DocumentoPacienteOut(
        id=d.id, tipo=d.tipo, titulo=d.titulo, contenido=d.contenido, estado=d.estado,
        requiere_firma=d.requiere_firma, firmado_paciente=d.firmado_paciente, firmado_at=d.firmado_at, fecha=d.created_at,
        firma_profesional=d.firma_profesional,
    )


@router.get("/documentos", response_model=list[DocumentoPacienteOut])
async def list_documentos(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.OWN_MEDICAL_RECORD, Action.VER)),
) -> list[DocumentoPacienteOut]:
    patient = await get_own_patient(db, ctx)
    rows = (
        await db.execute(
            select(ClinicalDocument)
            .where(ClinicalDocument.patient_id == patient.id, ClinicalDocument.estado == "emitido", ClinicalDocument.deleted_at.is_(None))
            .order_by(ClinicalDocument.created_at.desc())
        )
    ).scalars().all()
    return [_doc_pac_out(d) for d in rows]


@router.post("/documentos/{doc_id}/firmar", response_model=DocumentoPacienteOut)
async def firmar_documento(
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.OWN_MEDICAL_RECORD, Action.EDITAR)),
) -> DocumentoPacienteOut:
    """El paciente firma su propio consentimiento (64.8)."""
    patient = await get_own_patient(db, ctx)
    doc = await db.get(ClinicalDocument, doc_id)
    if doc is None or doc.patient_id != patient.id or doc.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento no encontrado")
    if doc.estado != "emitido":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"El documento está {doc.estado}")
    if not doc.requiere_firma:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Este documento no requiere firma")
    if doc.firmado_paciente:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El documento ya está firmado")
    doc.firmado_paciente = True
    doc.firmado_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(doc)
    return _doc_pac_out(doc)


async def _get_wallet(db: AsyncSession, patient_id):
    from app.models.wallet import WalletAccount

    return (await db.execute(select(WalletAccount).where(WalletAccount.patient_id == patient_id))).scalar_one()


@router.get("/qr", response_model=EmergencyQrOut)
async def get_or_create_qr(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.OWN_MEDICAL_RECORD, Action.VER)),
) -> EmergencyQrOut:
    patient = await get_own_patient(db, ctx)
    qr = (await db.execute(select(EmergencyQr).where(EmergencyQr.patient_id == patient.id))).scalar_one_or_none()
    if qr is None:
        ficha = patient.ficha or {}
        qr = EmergencyQr(
            clinic_id=patient.clinic_id,
            patient_id=patient.id,
            token=secrets.token_urlsafe(24),
            resumen={"grupo_sanguineo": ficha.get("grupo_sanguineo"), "alergias": ficha.get("alergias")},
        )
        db.add(qr)
        await db.commit()
        await db.refresh(qr)
    return EmergencyQrOut(token=qr.token, resumen=qr.resumen, activo=qr.activo)


@router.get("/qr/mis-accesos", response_model=list[QrAccessLogOut])
async def list_qr_accesos(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.OWN_MEDICAL_RECORD, Action.VER)),
) -> list[QrAccessLogOut]:
    patient = await get_own_patient(db, ctx)
    qr = (await db.execute(select(EmergencyQr).where(EmergencyQr.patient_id == patient.id))).scalar_one_or_none()
    if qr is None:
        return []
    rows = (
        await db.execute(select(QrAccessLog).where(QrAccessLog.qr_id == qr.id).order_by(QrAccessLog.fecha.desc()))
    ).scalars().all()
    return [QrAccessLogOut(fecha=r.fecha, profesional_nombre=r.profesional_nombre) for r in rows]


@router.get("/qr/resolver/{token}", response_model=QrResolveOut)
async def resolver_qr(
    token: str,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_any_medico),
) -> QrResolveOut:
    """Público solo en el sentido de "no requiere ser el propio paciente" —
    sigue exigiendo un JWT de un médico (require_any_medico) y cada acceso
    se audita (fecha, hora, profesional) por Spec Paciente §5.3."""
    qr = (await db.execute(select(EmergencyQr).where(EmergencyQr.token == token, EmergencyQr.activo.is_(True)))).scalar_one_or_none()
    if qr is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "QR inválido o inactivo")

    from app.models.patient import Patient

    patient = await db.get(Patient, qr.patient_id)
    user = await db.get(User, patient.user_id)
    medico = await db.get(User, ctx.user_id)

    db.add(
        QrAccessLog(
            clinic_id=qr.clinic_id,
            qr_id=qr.id,
            accedido_por=ctx.user_id,
            profesional_nombre=medico.nombre,
            fecha=datetime.now(timezone.utc),
        )
    )
    await db.commit()

    return QrResolveOut(patient_nombre=user.nombre, resumen=qr.resumen)
