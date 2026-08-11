import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class EmisorIn(BaseModel):
    tax_id: str = Field(min_length=1, max_length=20)  # RUT (CL) | CNPJ (BR)
    razon_social: str = Field(min_length=1, max_length=255)
    giro: str | None = None
    direccion: str | None = None
    config: dict | None = None  # extras del régimen (ver TaxEmitter.config)


class EmisorOut(BaseModel):
    id: uuid.UUID
    pais: str
    tax_id: str
    razon_social: str
    giro: str | None
    direccion: str | None
    config: dict | None


class FolioRangeIn(BaseModel):
    tipo_documento: str
    serie: str | None = None
    desde: int = Field(ge=1)
    hasta: int = Field(ge=1)
    caf_ref: str | None = None


class FolioRangeOut(BaseModel):
    id: uuid.UUID
    tipo_documento: str
    serie: str | None
    desde: int
    hasta: int
    siguiente: int
    disponibles: int
    caf_ref: str | None
    activo: bool


class ItemIn(BaseModel):
    descripcion: str = Field(min_length=1)
    cantidad: float = Field(gt=0)
    precio_unitario: float = Field(ge=0)
    exento: bool = False  # línea exenta de IVA (Chile): prestación no afecta (IndExe)


class ReceptorIn(BaseModel):
    tax_id: str | None = None
    nombre: str | None = None


class EmitirIn(BaseModel):
    tipo_documento: str  # CL: boleta_electronica|factura_electronica ; BR: nfse|nfe|nfce
    items: list[ItemIn] = Field(min_length=1)
    receptor: ReceptorIn | None = None
    serie: str | None = None
    appointment_id: uuid.UUID | None = None
    cash_payment_id: uuid.UUID | None = None


class AnularIn(BaseModel):
    motivo: str = Field(min_length=3, max_length=500)


class DocumentoResumen(BaseModel):
    id: uuid.UUID
    pais: str
    jurisdiccion: str
    organo: str
    tipo_documento: str
    codigo: str | None
    serie: str | None
    folio: int
    receptor_nombre: str | None
    neto: float
    impuesto: float
    total: float
    moneda: str
    estado: str
    track_id: str | None
    emitido_at: datetime


class DocumentoOut(DocumentoResumen):
    receptor_tax_id: str | None
    exento: float
    impuesto_detalle: dict | None
    items: list | None
    sello: str | None
    motivo: str | None
    referencia_id: uuid.UUID | None
    xml: str | None
