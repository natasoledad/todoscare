import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base, TenantMixin


class KnowledgeSource(Base, AuditMixin, TenantMixin):
    """Fuente de la base de conocimiento de la clínica (72): un PDF o texto que
    la clínica sube para que la IA lo use como referencia al conversar. El
    contenido se parte en `KnowledgeChunk` con su vector."""

    __tablename__ = "knowledge_sources"

    nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False, server_default="texto")  # pdf | texto
    archivo_url: Mapped[str | None] = mapped_column(String(500))
    estado: Mapped[str] = mapped_column(String(20), nullable=False, server_default="listo")  # procesando | listo | error
    n_chunks: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")


class KnowledgeChunk(Base, AuditMixin, TenantMixin):
    """Fragmento de una fuente con su vector de embedding (lista de floats en
    JSONB, dentro del propio Postgres — sin depender de un almacén externo). La
    búsqueda por similitud se resuelve en la app (coseno)."""

    __tablename__ = "knowledge_chunks"

    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("knowledge_sources.id"), nullable=False, index=True)
    orden: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list] = mapped_column(JSONB, nullable=False)
