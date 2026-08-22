import uuid

from pydantic import BaseModel, Field

TIPOS = {"seguro_complementario", "caja_compensacion"}
MODALIDADES = {"porcentaje", "monto"}


class CoberturaIn(BaseModel):
    tipo: str = Field(pattern="^(seguro_complementario|caja_compensacion)$")
    nombre: str = Field(min_length=2, max_length=120)
    modalidad: str = Field(default="porcentaje", pattern="^(porcentaje|monto)$")
    valor: float = Field(ge=0)  # fracción 0..1 si porcentaje; CLP si monto
    tope: float | None = Field(default=None, ge=0)
    deducible: float | None = Field(default=None, ge=0)
    permite_cuotas: bool = False


class CoberturaUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=120)
    modalidad: str | None = Field(default=None, pattern="^(porcentaje|monto)$")
    valor: float | None = Field(default=None, ge=0)
    tope: float | None = Field(default=None, ge=0)
    deducible: float | None = Field(default=None, ge=0)
    permite_cuotas: bool | None = None
    activo: bool | None = None


class CoberturaOut(BaseModel):
    id: uuid.UUID
    tipo: str
    nombre: str
    modalidad: str
    valor: float
    tope: float | None
    deducible: float | None
    permite_cuotas: bool
    activo: bool


class CalcularCopagoIn(BaseModel):
    precio: float = Field(gt=0)
    prevision_pct: float = Field(default=0.0, ge=0, le=1)  # fracción que bonifica Fonasa/Isapre
    prevision_bono: float | None = Field(default=None, ge=0)  # bono fijo (tiene prioridad sobre el %)
    cobertura_ids: list[uuid.UUID] = Field(default_factory=list)  # capas a aplicar, en orden


class AporteOut(BaseModel):
    tipo: str
    nombre: str
    aporte: float


class CalcularCopagoOut(BaseModel):
    precio: float
    bono_prevision: float
    prevision_pct: float | None
    copago_inicial: float  # copago tras la previsión, antes de las capas
    aportes: list[AporteOut]
    copago_final: float
    permite_cuotas: bool
