"""Documentos tributarios electrónicos (Tanda 7).

El emisor de cada clínica declara su identidad fiscal (`TaxEmitter`) y, según
el país de la clínica (`clinics.pais`), la plataforma emite el documento que
corresponde a ese régimen:

  · **Chile** — Documento Tributario Electrónico (DTE) ante el **SII**: boleta
    electrónica (código 39), factura electrónica (33) y nota de crédito (61,
    para anular). Cada DTE consume un **folio** de un CAF autorizado por el SII
    (`TaxFolioRange`) y lleva su timbre electrónico (TED).

  · **Brasil** — Nota Fiscal eletrônica según el hecho gravado y el órgano
    competente: **NFS-e** (serviço → prefeitura/**município**, ISS), **NF-e**
    (mercadoria → **SEFAZ estadual**, ICMS) o **NFC-e** (consumidor final). El
    número es secuencial por emisor/serie y la autorización devuelve un
    protocolo del órgano.

El documento emitido (`TaxDocument`) es un registro casi inmutable: nace
`pendiente`, pasa a `aceptado`/`rechazado` según la respuesta del órgano y solo
puede `anular`-se emitiendo el documento inverso (nota de crédito en Chile,
cancelamento en Brasil) — nunca se borra ni se reescribe.
"""

import datetime
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base, TenantMixin


class TaxEmitter(Base, AuditMixin, TenantMixin):
    """Identidad fiscal del emisor (la clínica) ante su órgano tributario. Uno
    por clínica. Los datos comunes (identificador, razón social, giro) son
    columnas tipadas; lo específico de cada régimen vive en `config` (JSONB):

      · Chile: {"acteco": "...", "resolucion_sii_numero": 80,
                "resolucion_sii_fecha": "2014-08-22", "comuna": "..."}
      · Brasil: {"inscricao_municipal": "...", "inscricao_estadual": "...",
                 "cnae": "...", "regime_tributario": "simples|normal",
                 "municipio_ibge": "3550308", "uf": "SP", "iss_aliquota": 0.05}
    """

    __tablename__ = "tax_emitters"
    __table_args__ = (UniqueConstraint("clinic_id", name="uq_tax_emitter_clinic"),)

    pais: Mapped[str] = mapped_column(String(2), nullable=False)  # CL | BR (espejo de clinics.pais)
    tax_id: Mapped[str] = mapped_column(String(20), nullable=False)  # RUT (CL) | CNPJ (BR)
    razon_social: Mapped[str] = mapped_column(String(255), nullable=False)
    giro: Mapped[str | None] = mapped_column(String(255))  # giro (CL) | descrição da atividade (BR)
    direccion: Mapped[str | None] = mapped_column(String(500))
    config: Mapped[dict | None] = mapped_column(JSONB)  # extras del régimen (ver docstring)


class TaxFolioRange(Base, AuditMixin, TenantMixin):
    """Rango de numeración disponible para un tipo de documento.

    En **Chile** representa un CAF (Código de Asignación de Folios) que el SII
    autoriza por tipo de DTE: folios [desde, hasta] y el próximo a consumir. En
    **Brasil** es la serie/numeración secuencial del emisor (RPS→NFS-e). El
    contador `siguiente` sí se actualiza (no es ledger inmutable): asignar un
    folio avanza el puntero de forma atómica.
    """

    __tablename__ = "tax_folio_ranges"

    emitter_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tax_emitters.id"), nullable=False, index=True)
    tipo_documento: Mapped[str] = mapped_column(String(30), nullable=False)  # boleta_electronica | factura_electronica | nota_credito | nfse | nfe | nfce
    serie: Mapped[str | None] = mapped_column(String(10))  # serie (BR); NULL en Chile
    desde: Mapped[int] = mapped_column(Integer, nullable=False)
    hasta: Mapped[int] = mapped_column(Integer, nullable=False)
    siguiente: Mapped[int] = mapped_column(Integer, nullable=False)  # próximo folio/número a asignar
    caf_ref: Mapped[str | None] = mapped_column(String(120))  # referencia al CAF/autorización del órgano
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")


class TaxDocument(Base, AuditMixin, TenantMixin):
    """Documento tributario emitido (DTE en Chile, Nota Fiscal en Brasil).

    Casi inmutable: solo se actualiza su `estado` (respuesta del órgano) y, al
    anular, se cruza con el documento inverso vía `referencia_id`. El XML
    generado y el sello (`sello`) se fijan en la emisión y no se reescriben.
    """

    __tablename__ = "tax_documents"
    __table_args__ = (
        UniqueConstraint("emitter_id", "tipo_documento", "serie", "folio", name="uq_tax_doc_folio"),
    )

    emitter_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tax_emitters.id"), nullable=False, index=True)

    pais: Mapped[str] = mapped_column(String(2), nullable=False)  # CL | BR
    # Órgano/jurisdicción que autoriza: federal (SII Chile), estatal (SEFAZ BR),
    # municipal (prefeitura BR). Enrutado según país + tipo de hecho gravado.
    jurisdiccion: Mapped[str] = mapped_column(String(12), nullable=False)  # federal | estatal | municipal
    organo: Mapped[str] = mapped_column(String(60), nullable=False)  # "SII" | "SEFAZ-SP" | "Prefeitura de São Paulo" ...

    tipo_documento: Mapped[str] = mapped_column(String(30), nullable=False)  # boleta_electronica | factura_electronica | nota_credito | nfse | nfe | nfce
    codigo: Mapped[str | None] = mapped_column(String(10))  # código SII (39/33/61) o modelo BR (55/65)
    serie: Mapped[str | None] = mapped_column(String(10))
    folio: Mapped[int] = mapped_column(Integer, nullable=False)  # folio (CL) / número (BR)

    receptor_tax_id: Mapped[str | None] = mapped_column(String(20))  # RUT/CPF/CNPJ del receptor (NULL = consumidor final)
    receptor_nombre: Mapped[str | None] = mapped_column(String(255))

    neto: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, server_default="0")
    exento: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, server_default="0")
    impuesto: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, server_default="0")  # IVA (CL) | ISS/ICMS (BR)
    total: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    moneda: Mapped[str] = mapped_column(String(3), nullable=False, server_default="CLP")
    impuesto_detalle: Mapped[dict | None] = mapped_column(JSONB)  # {"tipo": "IVA", "tasa": 0.19, ...}
    items: Mapped[list | None] = mapped_column(JSONB)  # líneas del documento

    estado: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pendiente")  # pendiente | aceptado | rechazado | anulado
    track_id: Mapped[str | None] = mapped_column(String(120))  # TrackID SII / protocolo SEFAZ / protocolo prefeitura
    sello: Mapped[str | None] = mapped_column(String(255))  # TED (Chile) / código de verificação (Brasil)
    motivo: Mapped[str | None] = mapped_column(String(500))  # motivo de rechazo o de anulación
    xml: Mapped[str | None] = mapped_column(String)  # representación del documento firmado (forma real)

    # Anulación: una nota de crédito / cancelamento apunta al documento que anula.
    referencia_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("tax_documents.id"))

    # Trazabilidad con el resto de la plataforma (opcional).
    appointment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("appointments.id"))
    cash_payment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("cash_payments.id"))
    ledger_entry_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("ledger_entries.id"))

    emitido_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
