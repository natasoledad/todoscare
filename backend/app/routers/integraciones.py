"""Conectores externos (Fase 8) — frontera tipada con el mundo exterior.

Gates RBAC:
  · Bandeja de estado y webhooks de proveedor (pago/lab/farmacia): las
    gestiona/observa el rol Administrador (Resource.INTEGRACIONES). En
    producción los webhooks entran sin sesión pero con firma del proveedor;
    aquí los dispara un admin/clinic_admin de la clínica (misma frontera).
  · Asistente de WhatsApp y pago del paciente: rol Paciente.
  · Mapas y push: cualquier usuario autenticado, sobre su propio alcance.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.integrations import farmacia as farmacia_conn
from app.integrations import lab as lab_conn
from app.integrations import mapas as mapas_conn
from app.integrations import pago as pago_conn
from app.integrations import push as push_conn
from app.integrations import whatsapp as whatsapp_conn
from app.models.integrations import IntegrationConfig, IntegrationEvent
from app.models.patient import Patient
from app.rbac.deps import require
from app.rbac.permissions import Action, Resource
from app.schemas.integraciones import (
    ConectorEstado,
    EnviarPushIn,
    EnvioOut,
    EventoOut,
    FarmaciaEstadoIn,
    FarmaciaEstadoOut,
    IntegracionesEstado,
    LabResultadoIn,
    LabResultadoOut,
    MensajeIn,
    MensajeOut,
    NotificacionOut,
    PagoConfirmadoOut,
    PagoConfirmarIn,
    PagoIntentIn,
    PagoIntentOut,
    SucursalCercana,
    SuscribirIn,
    SuscripcionOut,
)
from app.tenancy.context import TenantContext
from app.tenancy.deps import get_current_ctx

router = APIRouter(prefix="/integraciones", tags=["integraciones"])


# ─────────── estado / traza (Admin) ───────────
@router.get("/estado", response_model=IntegracionesEstado)
async def estado(db: AsyncSession = Depends(get_db), ctx: TenantContext = Depends(require(Resource.INTEGRACIONES, Action.VER))) -> IntegracionesEstado:
    scope = ctx.clinic_ids()
    cq = select(IntegrationConfig).where(IntegrationConfig.deleted_at.is_(None))
    eq = select(IntegrationEvent).where(IntegrationEvent.deleted_at.is_(None)).order_by(IntegrationEvent.created_at.desc()).limit(20)
    if scope is not None:
        cq = cq.where(IntegrationConfig.clinic_id.in_(scope))
        eq = eq.where(IntegrationEvent.clinic_id.in_(scope))
    conectores = (await db.execute(cq.order_by(IntegrationConfig.tipo))).scalars().all()
    eventos = (await db.execute(eq)).scalars().all()
    return IntegracionesEstado(
        conectores=[ConectorEstado(id=c.id, tipo=c.tipo, activo=c.activo) for c in conectores],
        eventos_recientes=[EventoOut(tipo=e.tipo, direccion=e.direccion, estado=e.estado, ref=e.ref, resultado=e.resultado, fecha=e.created_at) for e in eventos],
    )


# ─────────── WhatsApp / IA (Paciente) ───────────
@router.post("/whatsapp/mensaje", response_model=MensajeOut)
async def whatsapp_mensaje(body: MensajeIn, db: AsyncSession = Depends(get_db), ctx: TenantContext = Depends(require(Resource.OWN_APPOINTMENTS, Action.VER))) -> MensajeOut:
    return MensajeOut(**await whatsapp_conn.handle_inbound(db, ctx, body.texto))


# ─────────── Pago (Paciente inicia; proveedor confirma) ───────────
@router.post("/pago/intent", response_model=PagoIntentOut, status_code=201)
async def pago_intent(body: PagoIntentIn, db: AsyncSession = Depends(get_db), ctx: TenantContext = Depends(require(Resource.OWN_APPOINTMENTS, Action.VER))) -> PagoIntentOut:
    return PagoIntentOut(**await pago_conn.crear_intent(db, body.appointment_id, ctx.clinic_ids()))


@router.post("/pago/webhook", response_model=PagoConfirmadoOut)
async def pago_webhook(body: PagoConfirmarIn, db: AsyncSession = Depends(get_db), ctx: TenantContext = Depends(require(Resource.INTEGRACIONES, Action.EDITAR))) -> PagoConfirmadoOut:
    return PagoConfirmadoOut(**await pago_conn.confirmar(db, body.appointment_id))


# ─────────── Laboratorio (webhook de resultado) ───────────
@router.post("/lab/webhook", response_model=LabResultadoOut)
async def lab_webhook(body: LabResultadoIn, db: AsyncSession = Depends(get_db), ctx: TenantContext = Depends(require(Resource.INTEGRACIONES, Action.EDITAR))) -> LabResultadoOut:
    return LabResultadoOut(**await lab_conn.resultado_webhook(db, body.order_id, body.resultado))


# ─────────── Farmacia (webhook de estado) ───────────
@router.post("/farmacia/webhook", response_model=FarmaciaEstadoOut)
async def farmacia_webhook(body: FarmaciaEstadoIn, db: AsyncSession = Depends(get_db), ctx: TenantContext = Depends(require(Resource.INTEGRACIONES, Action.EDITAR))) -> FarmaciaEstadoOut:
    return FarmaciaEstadoOut(**await farmacia_conn.estado_webhook(db, body.prescription_id, body.estado))


# ─────────── Mapas (cualquier usuario autenticado) ───────────
@router.get("/mapas/sucursales", response_model=list[SucursalCercana])
async def mapas_sucursales(lat: float, lng: float, db: AsyncSession = Depends(get_db), ctx: TenantContext = Depends(get_current_ctx)) -> list[SucursalCercana]:
    return [SucursalCercana(**s) for s in await mapas_conn.sucursales_cercanas(db, ctx.clinic_ids(), lat, lng)]


# ─────────── Push (propio del usuario) ───────────
@router.post("/push/suscribir", response_model=SuscripcionOut, status_code=201)
async def push_suscribir(body: SuscribirIn, db: AsyncSession = Depends(get_db), ctx: TenantContext = Depends(get_current_ctx)) -> SuscripcionOut:
    return SuscripcionOut(**await push_conn.suscribir(db, ctx.user_id, body.endpoint))


@router.post("/push/enviar", response_model=EnvioOut)
async def push_enviar(body: EnviarPushIn, db: AsyncSession = Depends(get_db), ctx: TenantContext = Depends(get_current_ctx)) -> EnvioOut:
    # Auto-envío de demostración: notifica al propio usuario en su clínica.
    clinic_id = await _clinic_of_ctx(db, ctx)
    return EnvioOut(**await push_conn.enviar(db, clinic_id=clinic_id, user_id=ctx.user_id, titulo=body.titulo, cuerpo=body.cuerpo))


@router.get("/push/mis-notificaciones", response_model=list[NotificacionOut])
async def push_mis_notificaciones(db: AsyncSession = Depends(get_db), ctx: TenantContext = Depends(get_current_ctx)) -> list[NotificacionOut]:
    return [NotificacionOut(**n) for n in await push_conn.mis_notificaciones(db, ctx.user_id)]


async def _clinic_of_ctx(db: AsyncSession, ctx: TenantContext) -> uuid.UUID:
    ids = ctx.clinic_ids()
    if ids:
        return next(iter(ids))
    # paciente: su clínica vía Patient
    patient = (await db.execute(select(Patient).where(Patient.user_id == ctx.user_id, Patient.deleted_at.is_(None)))).scalar_one_or_none()
    if patient is not None:
        return patient.clinic_id
    from fastapi import HTTPException, status

    raise HTTPException(status.HTTP_400_BAD_REQUEST, "El usuario no tiene una clínica asociada para notificaciones")
