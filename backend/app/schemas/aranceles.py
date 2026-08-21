import uuid

from pydantic import BaseModel, Field


# ---- arancel ----
class ArancelIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    tipo: str = Field(default="particular", pattern="^(base|particular|empresa)$")
    es_base: bool = False


class ArancelUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=120)
    tipo: str | None = Field(default=None, pattern="^(base|particular|empresa)$")
    es_base: bool | None = None
    activo: bool | None = None


class ArancelOut(BaseModel):
    id: uuid.UUID
    nombre: str
    tipo: str
    es_base: bool
    activo: bool
    n_items: int


# ---- categoría ----
class CategoriaIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    orden: int = 0


class CategoriaUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=120)
    orden: int | None = None


class CategoriaOut(BaseModel):
    id: uuid.UUID
    arancel_id: uuid.UUID
    nombre: str
    orden: int


# ---- ítem (prestación) ----
class ItemIn(BaseModel):
    categoria_id: uuid.UUID | None = None
    codigo: str | None = Field(default=None, max_length=40)
    nombre: str = Field(min_length=1, max_length=255)
    precio: float = Field(ge=0)
    precio_referencia: float | None = Field(default=None, ge=0)
    permite_descuento: bool = True
    comisiona: bool = True


class ItemUpdate(BaseModel):
    categoria_id: uuid.UUID | None = None
    codigo: str | None = Field(default=None, max_length=40)
    nombre: str | None = Field(default=None, min_length=1, max_length=255)
    precio: float | None = Field(default=None, ge=0)
    precio_referencia: float | None = Field(default=None, ge=0)
    permite_descuento: bool | None = None
    comisiona: bool | None = None
    activo: bool | None = None


class ItemOut(BaseModel):
    id: uuid.UUID
    arancel_id: uuid.UUID
    categoria_id: uuid.UUID | None
    categoria_nombre: str | None
    codigo: str | None
    nombre: str
    precio: float
    precio_referencia: float | None
    permite_descuento: bool
    comisiona: bool
    activo: bool


# ---- acciones ----
class IncrementarIn(BaseModel):
    pct: float = Field(ge=-0.9, le=10)  # +0.10 = +10%; admite negativos


class IncrementarOut(BaseModel):
    afectados: int


class CopiarBaseOut(BaseModel):
    copiados: int


# ---- carga masiva (62.8) ----
class ImportarArancelIn(BaseModel):
    contenido: str = Field(min_length=1)          # texto CSV pegado o de archivo
    separador: str | None = None                  # None = autodetecta (, o ;)
    tiene_encabezado: bool = True


class ImportErrorItem(BaseModel):
    fila: int
    motivo: str


class ImportarArancelOut(BaseModel):
    creados: int
    actualizados: int
    total_filas: int
    errores: list[ImportErrorItem]
