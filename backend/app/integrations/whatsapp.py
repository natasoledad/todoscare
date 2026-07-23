"""Conector WhatsApp / IA — el asistente que corre en el webview de WhatsApp.

Enganche real: webhook de la WhatsApp Business Cloud API (verificación de
firma X-Hub-Signature-256) + un LLM para clasificar intención y redactar la
respuesta. Aquí la intención se resuelve con reglas deterministas sobre el
texto y las respuestas se arman con datos reales del paciente (su próxima
cita, su ficha), de modo que el flujo end-to-end sea verificable sin red.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.base import ensure_enabled, log_event
from app.models.patient import Patient
from app.models.scheduling import Appointment
from app.models.tenant import Clinic
from app.tenancy.context import TenantContext


def _clasificar(texto: str) -> str:
    t = texto.lower()
    if any(w in t for w in ("hola", "buenas", "buenos días", "buenas tardes")):
        return "saludo"
    # 'agendar/reservar' se evalúa antes que 'próxima cita' porque "agendar"
    # contiene el substring "agenda".
    if any(w in t for w in ("agendar", "reservar", "sacar", "nueva cita")):
        return "agendar"
    if any(w in t for w in ("próxima", "proxima", "cuándo", "cuando", "cita", "turno", "mi agenda")):
        return "proxima_cita"
    if any(w in t for w in ("ficha", "salud", "examen", "exámen", "resultado")):
        return "salud"
    if any(w in t for w in ("receta", "farmacia", "medicamento", "remedio")):
        return "farmacia"
    return "ayuda"


async def _patient_of(db: AsyncSession, ctx: TenantContext) -> Patient | None:
    return (await db.execute(select(Patient).where(Patient.user_id == ctx.user_id, Patient.deleted_at.is_(None)))).scalar_one_or_none()


async def handle_inbound(db: AsyncSession, ctx: TenantContext, texto: str) -> dict:
    """Procesa un mensaje entrante del paciente y devuelve la respuesta del
    asistente. Requiere que la clínica del paciente tenga el conector activo."""
    patient = await _patient_of(db, ctx)
    if patient is None:
        raise_no_patient()
    await ensure_enabled(db, patient.clinic_id, "whatsapp")

    intent = _clasificar(texto)
    nombre = (await db.execute(select(Clinic.razon_social).where(Clinic.id == patient.clinic_id))).scalar_one_or_none() or "tu clínica"

    if intent == "saludo":
        reply = "¡Hola! Soy el asistente de TODOSCARE. Puedo contarte tu próxima cita, ayudarte a agendar o mostrarte tu ficha. ¿Qué necesitas?"
    elif intent == "proxima_cita":
        reply = await _proxima_cita(db, patient)
    elif intent == "agendar":
        reply = "Para agendar, abre la sección Agenda de la app: elige servicio y horario disponible. Te confirmo la reserva al instante. 🗓️"
    elif intent == "salud":
        reply = "En Mi Salud encuentras tu ficha, exámenes y odontograma. Completar tu ficha te da puntos. ¿Quieres que te lleve ahí?"
    elif intent == "farmacia":
        reply = "Tus recetas vigentes aparecen en Farmacia, con la opción de envío a domicilio. 💊"
    else:
        reply = f"Estoy aquí para ayudarte con {nombre}: tu próxima cita, agendar, tu ficha de salud o tus recetas. ¿Con cuál seguimos?"

    log_event(db, clinic_id=patient.clinic_id, tipo="whatsapp", direccion="inbound", ref=f"user:{ctx.user_id}", payload={"texto": texto, "intent": intent}, resultado={"reply": reply})
    await db.commit()
    return {"intent": intent, "reply": reply}


async def _proxima_cita(db: AsyncSession, patient: Patient) -> str:
    now = datetime.now(timezone.utc)
    appt = (
        await db.execute(
            select(Appointment).where(Appointment.patient_id == patient.id, Appointment.deleted_at.is_(None), Appointment.estado != "cancelada").order_by(Appointment.slot)
        )
    ).scalars().first()
    if appt is None:
        return "No veo citas próximas. ¿Quieres agendar una? Entra a la sección Agenda. 🗓️"
    inicio = appt.slot.lower
    cuando = inicio.strftime("%d/%m a las %H:%M") if inicio else "próximamente"
    estado = "confirmada" if appt.estado == "confirmada" else appt.estado
    return f"Tu próxima cita está {estado} para el {cuando}. Si necesitas reagendar o cancelar, lo puedes hacer desde Mis citas. ✅"


def raise_no_patient() -> None:
    from fastapi import HTTPException, status

    raise HTTPException(status.HTTP_403_FORBIDDEN, "El asistente de WhatsApp es para pacientes")
