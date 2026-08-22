import uuid

from sqlalchemy import Boolean, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base, TenantMixin


class CoberturaComplementaria(Base, AuditMixin, TenantMixin):
    """Capa de cobertura que reduce el copago en Chile DESPUÉS del bono de la
    previsión (Fonasa/Isapre). Modela dos realidades del pago de copagos:

      · `seguro_complementario` — seguro privado de salud (Consorcio, Vida
        Cámara, Bice Vida…) que bonifica un % o monto del copago, con tope y
        deducible; suele operar por reembolso o convenio directo.
      · `caja_compensacion` — CCAF (Los Andes, La Araucana, Los Héroes, 18 de
        Septiembre): bonifica el copago de sus afiliados y muchas veces permite
        financiarlo en cuotas.

    La clínica arma su catálogo de coberturas y, al cobrar, la cascada las
    aplica en orden (previsión → seguro complementario → caja) hasta llegar al
    copago final que paga el paciente de su bolsillo."""

    __tablename__ = "coberturas_complementarias"

    tipo: Mapped[str] = mapped_column(String(30), nullable=False)  # seguro_complementario | caja_compensacion
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)  # p. ej. "Consorcio Salud", "CCAF Los Andes"
    modalidad: Mapped[str] = mapped_column(String(20), nullable=False, server_default="porcentaje")  # porcentaje | monto
    # Si modalidad=porcentaje: fracción 0..1 del copago que aporta la capa.
    # Si modalidad=monto: aporte fijo en CLP por prestación.
    valor: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False, server_default="0")
    tope: Mapped[float | None] = mapped_column(Numeric(12, 2))  # aporte máximo por prestación (CLP)
    deducible: Mapped[float | None] = mapped_column(Numeric(12, 2))  # el paciente paga esto antes de que la capa aporte
    permite_cuotas: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")  # típico de CCAF
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
