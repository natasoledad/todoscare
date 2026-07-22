from pydantic import BaseModel


class MedicamentoOut(BaseModel):
    nombre: str
    cantidad: str
    indicaciones: str | None = None
    precio: float | None = None
