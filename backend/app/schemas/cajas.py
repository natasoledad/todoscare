import uuid
from datetime import datetime

from pydantic import BaseModel, Field

MEDIOS = ["efectivo", "debito", "credito", "transferencia", "convenio", "otro"]


class AbrirCajaIn(BaseModel):
    abono_inicial: float = Field(default=0, ge=0)
    branch_id: uuid.UUID | None = None


class CerrarCajaIn(BaseModel):
    fondo_fijo: float = Field(default=0, ge=0)


class MovimientoIn(BaseModel):
    tipo: str = "pago"  # pago | gasto
    medio: str          # efectivo | debito | credito | transferencia | convenio | otro
    monto: float = Field(gt=0)
    patient_id: uuid.UUID | None = None
    appointment_id: uuid.UUID | None = None
    convenio: str | None = None
    referencia: str | None = None
    boleta: str | None = None
    glosa: str | None = None
    # Emisión tributaria (Tanda 7): si el conector 'tributario' está habilitado,
    # al registrar un pago se emite el documento del país (boleta SII / Nota
    # Fiscal Brasil) y su folio queda en `boleta`. tipo_documento se autodetecta
    # por país si no se especifica. Solo aplica a movimientos tipo 'pago'.
    emitir_boleta: bool = False
    tipo_documento: str | None = None
    receptor_tax_id: str | None = None
    receptor_nombre: str | None = None


class MovimientoOut(BaseModel):
    id: uuid.UUID
    tipo: str
    medio: str
    monto: float
    convenio: str | None
    referencia: str | None
    boleta: str | None
    glosa: str | None
    paciente_nombre: str | None
    appointment_id: uuid.UUID | None
    fecha: datetime
    tax_document_id: uuid.UUID | None = None  # documento tributario emitido, si lo hubo


class CajaOut(BaseModel):
    id: uuid.UUID
    responsable_id: uuid.UUID
    responsable_nombre: str
    estado: str
    abono_inicial: float
    fondo_fijo: float | None
    abierta_at: datetime
    cerrada_at: datetime | None
    recaudado: float
    gastos: float
    total: float


class CajaDetalleOut(CajaOut):
    por_medio: dict[str, float]
    transacciones: list[MovimientoOut]
