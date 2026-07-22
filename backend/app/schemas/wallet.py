from datetime import datetime

from pydantic import BaseModel, Field


class WalletBalanceOut(BaseModel):
    puntos: int
    cashback: float


class MovimientoOut(BaseModel):
    tipo: str
    fecha: datetime
    puntos: int | None
    cashback: float | None
    motivo: str | None


class PagarCashbackInput(BaseModel):
    monto: float = Field(gt=0)


class CanjearPuntosInput(BaseModel):
    puntos: int = Field(gt=0)
