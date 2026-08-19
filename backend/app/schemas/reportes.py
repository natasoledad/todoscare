from pydantic import BaseModel


# ---- biblioteca de reportes (68.14) ----
class ReporteItem(BaseModel):
    id: str
    nombre: str
    categoria: str
    descripcion: str
    exportable: bool


# ---- KPIs de agenda (68.8 · 68.10 · 68.12) ----
class AgendaKpisOut(BaseModel):
    dias: int
    total_citas: int
    completadas: int
    no_shows: int
    no_show_pct: float
    ocupacion_pct: float
    tiempo_espera_prom_min: float
    atendidas_con_espera: int
