import uuid
from datetime import datetime

from pydantic import BaseModel


# ── estado / traza (Admin) ──
class ConectorEstado(BaseModel):
    id: uuid.UUID
    tipo: str
    activo: bool


class EventoOut(BaseModel):
    tipo: str
    direccion: str
    estado: str
    ref: str | None
    resultado: dict | None
    fecha: datetime


class IntegracionesEstado(BaseModel):
    conectores: list[ConectorEstado]
    eventos_recientes: list[EventoOut]


# ── WhatsApp / IA ──
class MensajeIn(BaseModel):
    texto: str


class MensajeOut(BaseModel):
    intent: str
    reply: str


# ── Pago ──
class PagoIntentIn(BaseModel):
    appointment_id: uuid.UUID


class PagoIntentOut(BaseModel):
    intent_id: str
    appointment_id: str
    estado: str


class PagoConfirmarIn(BaseModel):
    appointment_id: uuid.UUID


class PagoConfirmadoOut(BaseModel):
    appointment_id: str
    monto: float
    split: float
    estado: str


# ── Laboratorio ──
class LabResultadoIn(BaseModel):
    order_id: uuid.UUID
    resultado: dict


class LabResultadoOut(BaseModel):
    order_id: str
    estado: str


# ── Farmacia ──
class FarmaciaEstadoIn(BaseModel):
    prescription_id: uuid.UUID
    estado: str


class FarmaciaEstadoOut(BaseModel):
    prescription_id: str
    estado: str


# ── Mapas ──
class SucursalCercana(BaseModel):
    branch_id: uuid.UUID
    clinic_id: uuid.UUID
    nombre: str
    direccion: str | None
    geo: dict | None
    distancia_km: float | None


# ── Push ──
class SuscribirIn(BaseModel):
    endpoint: str


class SuscripcionOut(BaseModel):
    subscription_id: str
    estado: str


class EnviarPushIn(BaseModel):
    titulo: str
    cuerpo: str


class EnvioOut(BaseModel):
    entregas: int
    titulo: str


class NotificacionOut(BaseModel):
    titulo: str | None
    cuerpo: str | None
    fecha: datetime
