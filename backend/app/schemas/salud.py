import uuid
from datetime import date, datetime

from pydantic import BaseModel


class ExamenOut(BaseModel):
    id: uuid.UUID
    nombre: str
    fecha: datetime
    estado: str
    archivo_url: str | None


class OdontogramaOut(BaseModel):
    piezas: dict


class HospitalizacionOut(BaseModel):
    id: uuid.UUID
    motivo: str
    centro: str | None
    ingreso: date | None
    egreso: date | None


class EmergencyQrOut(BaseModel):
    token: str
    resumen: dict
    activo: bool


class QrAccessLogOut(BaseModel):
    fecha: datetime
    profesional_nombre: str | None


class QrResolveOut(BaseModel):
    patient_nombre: str
    resumen: dict


# ---- documentos clínicos del paciente / firma (64.8) ----
class DocumentoPacienteOut(BaseModel):
    id: uuid.UUID
    tipo: str
    titulo: str
    contenido: str | None
    estado: str
    requiere_firma: bool
    firmado_paciente: bool
    firmado_at: datetime | None
    fecha: datetime
