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
    firma_profesional: str | None = None  # firma manuscrita del profesional emisor


# ---- exportar / descargar la ficha del paciente (72.2) ----
class FichaExportExamen(BaseModel):
    nombre: str
    fecha: datetime
    estado: str


class FichaExportDoc(BaseModel):
    titulo: str
    tipo: str
    fecha: datetime


class FichaExportOut(BaseModel):
    nombre: str
    rut: str
    clinica: str | None = None
    prevision: str | None = None
    prevision_nombre: str | None = None
    tramo_fonasa: str | None = None
    nacionalidad: str | None = None
    comuna: str | None = None
    ges: bool = False
    ges_detalle: str | None = None
    ficha: dict
    examenes: list[FichaExportExamen]
    documentos: list[FichaExportDoc]
    generado: datetime
