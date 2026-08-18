import uuid
from datetime import date

from sqlalchemy import Boolean, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base, TenantMixin
from sqlalchemy.dialects.postgresql import UUID


class Specialty(Base, AuditMixin):
    """Platform-wide taxonomy (Cardiología, Odontología, ...) — Admin-managed,
    not tenant-scoped. Clinics attach pricing/duration to it via CatalogItem
    and assign it to a professional's profile (ProfessionalProfile).

    `tipo` (dental | medica) clasifica la especialidad como en Medilink
    ("Tipo de especialidad", 54.3); `activo` permite deshabilitarla del
    catálogo sin borrarla (54.4)."""

    __tablename__ = "specialties"

    nombre: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    icono: Mapped[str | None] = mapped_column(String(10))
    tipo: Mapped[str] = mapped_column(String(20), nullable=False, server_default="medica")  # medica | dental
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")


class MotivoAtencion(Base, AuditMixin, TenantMixin):
    """Motivo de consulta que la clínica ofrece (Medilink §especialidades →
    "Motivo De Atención", 54.9). Puede colgar de una especialidad o ser
    general; identifica el porqué de la cita y luego alimenta la agenda
    online y los reportes. Tenant-scoped: cada clínica arma su propio set."""

    __tablename__ = "motivos_atencion"

    specialty_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("specialties.id"), index=True)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")


class CatalogItem(Base, AuditMixin, TenantMixin):
    """A clinic's priced offering — either a bookable service (tied to a
    specialty, with duration) or a product (e.g. a monthly plan add-on).
    Spec Empresa Cliente §2/§5.2."""

    __tablename__ = "catalog_items"

    specialty_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("specialties.id"), index=True)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)  # servicio | producto
    nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    precio: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    duracion_min: Mapped[int | None] = mapped_column()
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    # ¿La prestación está afecta a IVA? (Tanda 7). En Chile las prestaciones
    # médicas/odontológicas son EXENTAS (Art. 12 letra E, D.L. 825) y solo
    # algunos exámenes diagnósticos particulares son afectos; este flag decide
    # si la línea lleva IVA o va como exenta (IndExe) al emitir el documento.
    afecto_iva: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    # ¿La prestación comisiona al profesional tratante? (57.10 / 62.7). Las
    # acciones clínicas comisionan; el laboratorio y los insumos se cobran al
    # paciente pero NO cargan en la liquidación del profesional.
    comisiona: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")


class Promotion(Base, AuditMixin, TenantMixin):
    __tablename__ = "promotions"

    nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    descuento: Mapped[str | None] = mapped_column(String(50))
    vigencia_inicio: Mapped[date | None] = mapped_column()
    vigencia_fin: Mapped[date | None] = mapped_column()
    segmento: Mapped[str | None] = mapped_column(String(100))
    estado: Mapped[str] = mapped_column(String(20), nullable=False, server_default="Borrador")  # Activa | Borrador
