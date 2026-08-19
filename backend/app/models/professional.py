import uuid
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base, TenantMixin


class ProfessionalProfile(Base, AuditMixin, TenantMixin):
    """Perfil del profesional dentro de una clínica — el ancla que faltaba.

    Hasta ahora un "profesional" era solo un `User` con un RoleAssignment
    médico en la clínica: no había dónde guardar su especialidad, su duración
    de cita ni su estado. Este perfil lo resuelve y es la base de varios
    features del análisis Higia vs Medilink:

      · `specialty_id`  — la especialidad que aparece en su perfil (54.1b),
                          usada luego para filtrar agenda, agenda online y
                          reportes.
      · `duracion_min`  — intervalo de cita por defecto del profesional
                          (base para el horario recurrente, punto 52).
      · `modalidad`     — presencial | videoconsulta | ambas (51.5 / 52.7).
      · `activo`        — habilita/inhabilita al profesional en ESTA clínica
                          (55) sin borrarlo: un profesional inactivo no debe
                          poder operar ni recibir nuevas citas, pero su
                          historial se conserva.

    Un profesional puede trabajar en varias clínicas, por eso hay un perfil
    por (clinic_id, user_id)."""

    __tablename__ = "professional_profiles"
    __table_args__ = (UniqueConstraint("clinic_id", "user_id", name="uq_profprofile_clinic_user"),)

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    specialty_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("specialties.id"), index=True)
    duracion_min: Mapped[int | None] = mapped_column(Integer)  # intervalo de cita por defecto (min)
    modalidad: Mapped[str] = mapped_column(String(20), nullable=False, server_default="presencial")  # presencial | videoconsulta | ambas
    color: Mapped[str | None] = mapped_column(String(9))  # color opcional en la agenda (#RRGGBB)
    # % de comisión del profesional sobre las prestaciones que comisionan (58).
    # NULL = usar el % por defecto de la clínica (PROFESSIONAL_SPLIT_PCT).
    comision_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))  # 0.0000–1.0000
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    # Firma manuscrita del profesional (48): imagen dibujada en la app por el
    # propio profesional (data URL PNG). Se estampa en los documentos que emite.
    firma: Mapped[str | None] = mapped_column(Text)
