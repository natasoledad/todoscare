"""Diferenciadores IA (punto 72) — cara al paciente.

Reúne las capacidades de IA clínica sobre la ficha del paciente:
  · sugerencias generadas al subir un examen (aplicar/descartar a la ficha),
  · próxima fecha de control,
  · recordatorios (próxima cita + control),
  · chatbot que responde y agenda por el paciente.

Todo pasa por el conector 'ia_clinica' (gobernado por el Administrador) y deja
traza en integration_events.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import Range
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.integrations import ia_clinica
from app.integrations.base import ensure_enabled, log_event
from app.integrations.whatsapp import _clasificar, _proxima_cita
from app.models.catalog import CatalogItem
from app.models.clinical import AiFichaSuggestion, ExamResult
from app.models.scheduling import Appointment, AvailabilityBlock
from app.models.tenant import Branch
from app.rbac.deps import require
from app.rbac.permissions import Action, Resource
from app.routers.patients import get_own_patient
from app.integrations import asistente
from app.schemas.ia import (
    AgendarIAIn,
    AgendarIAOut,
    ChatIn,
    ChatOut,
    ConsultaIn,
    ConsultaOut,
    FichaAplicadaOut,
    RecordatorioOut,
    SugerenciaIAOut,
)
from app.services.scheduling import generate_slots, overlaps_exception
from app.tenancy.context import TenantContext

router = APIRouter(prefix="/ia", tags=["ia"])


async def _own_suggestion(db: AsyncSession, patient_id: uuid.UUID, sug_id: uuid.UUID) -> AiFichaSuggestion:
    sug = await db.get(AiFichaSuggestion, sug_id)
    if sug is None or sug.patient_id != patient_id or sug.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sugerencia no encontrada")
    return sug


@router.get("/sugerencias", response_model=list[SugerenciaIAOut])
async def list_sugerencias(
    estado: str | None = None,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.OWN_MEDICAL_RECORD, Action.VER)),
) -> list[SugerenciaIAOut]:
    patient = await get_own_patient(db, ctx)
    q = select(AiFichaSuggestion).where(AiFichaSuggestion.patient_id == patient.id, AiFichaSuggestion.deleted_at.is_(None))
    if estado:
        q = q.where(AiFichaSuggestion.estado == estado)
    q = q.order_by(AiFichaSuggestion.created_at.desc())
    rows = (await db.execute(q)).scalars().all()
    out: list[SugerenciaIAOut] = []
    for s in rows:
        nombre = None
        if s.exam_order_id:
            res = (
                await db.execute(
                    select(ExamResult).where(ExamResult.order_id == s.exam_order_id, ExamResult.deleted_at.is_(None)).limit(1)
                )
            ).scalars().first()
            if res and isinstance(res.resultado, dict):
                nombre = res.resultado.get("nombre")
        out.append(SugerenciaIAOut(
            id=s.id, resumen=s.resumen, hallazgos=s.hallazgos, proximo_control=s.proximo_control,
            estado=s.estado, examen_nombre=nombre, fecha=s.created_at,
        ))
    return out


@router.post("/sugerencias/{sug_id}/aplicar", response_model=FichaAplicadaOut)
async def aplicar_sugerencia(
    sug_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.OWN_MEDICAL_RECORD, Action.EDITAR)),
) -> FichaAplicadaOut:
    patient = await get_own_patient(db, ctx)
    sug = await _own_suggestion(db, patient.id, sug_id)
    if sug.estado != "pendiente":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"La sugerencia ya está {sug.estado}")

    # Merge del parche de la IA en la ficha + fecha de próximo control.
    ficha = dict(patient.ficha or {})
    ficha.update(sug.hallazgos or {})
    if sug.proximo_control:
        ficha["proximo_control"] = sug.proximo_control.isoformat()
    patient.ficha = ficha
    sug.estado = "aplicada"

    log_event(db, clinic_id=patient.clinic_id, tipo=ia_clinica.TIPO, direccion="outbound",
              ref=f"suggestion:{sug.id}", resultado={"aplicada": True, "hallazgos": sug.hallazgos})
    await db.commit()
    return FichaAplicadaOut(aplicada=True, ficha=patient.ficha, proximo_control=sug.proximo_control)


@router.post("/sugerencias/{sug_id}/descartar", response_model=SugerenciaIAOut)
async def descartar_sugerencia(
    sug_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.OWN_MEDICAL_RECORD, Action.EDITAR)),
) -> SugerenciaIAOut:
    patient = await get_own_patient(db, ctx)
    sug = await _own_suggestion(db, patient.id, sug_id)
    if sug.estado != "pendiente":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"La sugerencia ya está {sug.estado}")
    sug.estado = "descartada"
    await db.commit()
    return SugerenciaIAOut(id=sug.id, resumen=sug.resumen, hallazgos=sug.hallazgos, proximo_control=sug.proximo_control,
                           estado=sug.estado, examen_nombre=None, fecha=sug.created_at)


@router.get("/recordatorios", response_model=list[RecordatorioOut])
async def recordatorios(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.OWN_APPOINTMENTS, Action.VER)),
) -> list[RecordatorioOut]:
    patient = await get_own_patient(db, ctx)
    now = datetime.now(timezone.utc)
    recs: list[RecordatorioOut] = []

    appt = (
        await db.execute(
            select(Appointment).where(
                Appointment.patient_id == patient.id, Appointment.deleted_at.is_(None),
                Appointment.estado != "cancelada", Appointment.slot.op("&&")(Range(now, None)),
            ).order_by(Appointment.slot)
        )
    ).scalars().first()
    if appt is not None:
        inicio = appt.slot.lower
        recs.append(RecordatorioOut(tipo="cita", titulo="Próxima cita", fecha=inicio,
                                    mensaje=f"Tienes una cita {appt.estado} el {inicio.strftime('%d/%m a las %H:%M')}. Te esperamos. ✅"))

    proximo = (patient.ficha or {}).get("proximo_control")
    if proximo:
        recs.append(RecordatorioOut(tipo="control", titulo="Próximo control sugerido", fecha=None,
                                    mensaje=f"La IA sugiere un control de seguimiento hacia el {proximo}. ¿Quieres agendarlo? 🗓️"))

    log_event(db, clinic_id=patient.clinic_id, tipo=ia_clinica.TIPO, direccion="outbound",
              ref=f"user:{ctx.user_id}", resultado={"recordatorios": len(recs)})
    await db.commit()
    return recs


@router.post("/chat", response_model=ChatOut)
async def chat(
    body: ChatIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.OWN_APPOINTMENTS, Action.VER)),
) -> ChatOut:
    patient = await get_own_patient(db, ctx)
    await ensure_enabled(db, patient.clinic_id, ia_clinica.TIPO)

    intent = _clasificar(body.texto)
    accion = None
    if intent == "proxima_cita":
        reply = await _proxima_cita(db, patient)
    elif intent == "agendar":
        reply = "Puedo agendarte la próxima hora disponible. Dime el servicio o elígelo en Agenda y confirmo al instante. 🗓️"
        accion = "agendar"
    elif intent == "salud":
        pend = (
            await db.execute(
                select(AiFichaSuggestion).where(
                    AiFichaSuggestion.patient_id == patient.id, AiFichaSuggestion.estado == "pendiente",
                    AiFichaSuggestion.deleted_at.is_(None),
                )
            )
        ).scalars().all()
        reply = (f"Tengo {len(pend)} sugerencia(s) de la IA para tu ficha a partir de tus exámenes. "
                 "Revísalas en Mi Salud para aplicarlas.") if pend else "Tu ficha está al día. Sube un examen y la IA la actualizará por ti. 📄"
    else:
        reply = ("Soy tu asistente con IA: puedo recordarte tu próxima cita, agendar una hora, "
                 "o actualizar tu ficha desde tus exámenes. ¿Con cuál seguimos?")

    log_event(db, clinic_id=patient.clinic_id, tipo=ia_clinica.TIPO, direccion="inbound",
              ref=f"user:{ctx.user_id}", payload={"texto": body.texto, "intent": intent}, resultado={"reply": reply})
    await db.commit()
    return ChatOut(intent=intent, reply=reply, accion=accion)


@router.post("/consultar", response_model=ConsultaOut)
async def consultar(
    body: ConsultaIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.OWN_MEDICAL_RECORD, Action.VER)),
) -> ConsultaOut:
    """El paciente le pregunta al asistente; responde con la base de conocimiento
    de su clínica (RAG), citando fuentes y con guardrails (72)."""
    patient = await get_own_patient(db, ctx)
    await ensure_enabled(db, patient.clinic_id, ia_clinica.TIPO)
    r = await asistente.responder(db, patient.clinic_id, body.pregunta)
    log_event(db, clinic_id=patient.clinic_id, tipo=ia_clinica.TIPO, direccion="inbound",
              ref=f"user:{ctx.user_id}", payload={"pregunta": body.pregunta}, resultado={"fuentes": r["fuentes"], "uso_ia": r["uso_ia"]})
    await db.commit()
    return ConsultaOut(**r)


@router.post("/agendar", response_model=AgendarIAOut, status_code=status.HTTP_201_CREATED)
async def agendar_ia(
    body: AgendarIAIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.OWN_APPOINTMENTS, Action.CREAR)),
) -> AgendarIAOut:
    """El chatbot agenda por el paciente: toma la próxima hora libre del
    servicio pedido y crea la cita (con la garantía anti doble-reserva de
    Postgres)."""
    patient = await get_own_patient(db, ctx)
    await ensure_enabled(db, patient.clinic_id, ia_clinica.TIPO)

    service = await db.get(CatalogItem, body.service_id)
    if service is None or service.clinic_id != patient.clinic_id or not service.activo:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Servicio no disponible")

    now = datetime.now(timezone.utc)
    dur = service.duracion_min or 30
    blocks = (
        await db.execute(
            select(AvailabilityBlock).where(
                AvailabilityBlock.clinic_id == patient.clinic_id,
                AvailabilityBlock.deleted_at.is_(None),
                (AvailabilityBlock.specialty_id == service.specialty_id) | (AvailabilityBlock.specialty_id.is_(None)),
            )
        )
    ).scalars().all()

    mejor: tuple[datetime, datetime, AvailabilityBlock] | None = None
    for block in blocks:
        start = max(block.rango.lower, now)
        if start >= block.rango.upper:
            continue
        booked = [
            (r.lower, r.upper) for r in (
                await db.execute(
                    select(Appointment.slot).where(
                        Appointment.professional_id == block.professional_id,
                        Appointment.deleted_at.is_(None), Appointment.estado != "cancelada",
                    )
                )
            ).scalars().all()
        ]
        for s, e in generate_slots(start, block.rango.upper, dur, booked):
            if await overlaps_exception(db, patient.clinic_id, block.professional_id, s, e, block.branch_id):
                continue
            if mejor is None or s < mejor[0]:
                mejor = (s, e, block)
            break

    if mejor is None:
        return AgendarIAOut(agendada=False, appointment_id=None, servicio_nombre=service.nombre,
                            inicio=None, fin=None, mensaje="No encontré horas disponibles próximamente. Intenta más tarde.")

    inicio, fin, block = mejor
    appt = Appointment(
        clinic_id=patient.clinic_id, branch_id=block.branch_id, professional_id=block.professional_id,
        patient_id=patient.id, service_id=service.id, room_id=block.room_id,
        slot=Range(inicio, fin), estado="confirmada",
    )
    db.add(appt)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Esa hora ya se ocupó — intenta de nuevo.") from None

    log_event(db, clinic_id=patient.clinic_id, tipo=ia_clinica.TIPO, direccion="outbound",
              ref=f"appointment:{appt.id}", resultado={"agendada": True, "inicio": inicio.isoformat()})
    await db.commit()

    branch = await db.get(Branch, block.branch_id)
    cuando = inicio.strftime("%d/%m a las %H:%M")
    return AgendarIAOut(agendada=True, appointment_id=appt.id, servicio_nombre=service.nombre,
                        inicio=inicio, fin=fin,
                        mensaje=f"¡Listo! Agendé tu {service.nombre} para el {cuando}"
                                + (f" en {branch.nombre}." if branch else ".") + " ✅")
