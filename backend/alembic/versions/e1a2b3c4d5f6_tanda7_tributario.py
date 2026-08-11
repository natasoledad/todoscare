"""Tanda 7: documentos tributarios electrónicos (SII Chile / Nota Fiscal Brasil)

tax_emitters + tax_folio_ranges + tax_documents. El emisor fiscal por clínica,
sus folios/CAF (Chile) o serie (Brasil), y el documento emitido (DTE / NF-e /
NFS-e) casi inmutable.

Revision ID: e1a2b3c4d5f6
Revises: d0f5a6b7c8de
Create Date: 2026-08-10
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e1a2b3c4d5f6"
down_revision = "d0f5a6b7c8de"
branch_labels = None
depends_on = None


def _audit_cols() -> list[sa.Column]:
    return [
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "tax_emitters",
        *_audit_cols(),
        sa.Column("pais", sa.String(length=2), nullable=False),
        sa.Column("tax_id", sa.String(length=20), nullable=False),
        sa.Column("razon_social", sa.String(length=255), nullable=False),
        sa.Column("giro", sa.String(length=255), nullable=True),
        sa.Column("direccion", sa.String(length=500), nullable=True),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("clinic_id", name="uq_tax_emitter_clinic"),
    )
    op.create_index(op.f("ix_tax_emitters_clinic_id"), "tax_emitters", ["clinic_id"], unique=False)

    op.create_table(
        "tax_folio_ranges",
        *_audit_cols(),
        sa.Column("emitter_id", sa.UUID(), nullable=False),
        sa.Column("tipo_documento", sa.String(length=30), nullable=False),
        sa.Column("serie", sa.String(length=10), nullable=True),
        sa.Column("desde", sa.Integer(), nullable=False),
        sa.Column("hasta", sa.Integer(), nullable=False),
        sa.Column("siguiente", sa.Integer(), nullable=False),
        sa.Column("caf_ref", sa.String(length=120), nullable=True),
        sa.Column("activo", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["emitter_id"], ["tax_emitters.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tax_folio_ranges_clinic_id"), "tax_folio_ranges", ["clinic_id"], unique=False)
    op.create_index(op.f("ix_tax_folio_ranges_emitter_id"), "tax_folio_ranges", ["emitter_id"], unique=False)

    op.create_table(
        "tax_documents",
        *_audit_cols(),
        sa.Column("emitter_id", sa.UUID(), nullable=False),
        sa.Column("pais", sa.String(length=2), nullable=False),
        sa.Column("jurisdiccion", sa.String(length=12), nullable=False),
        sa.Column("organo", sa.String(length=60), nullable=False),
        sa.Column("tipo_documento", sa.String(length=30), nullable=False),
        sa.Column("codigo", sa.String(length=10), nullable=True),
        sa.Column("serie", sa.String(length=10), nullable=True),
        sa.Column("folio", sa.Integer(), nullable=False),
        sa.Column("receptor_tax_id", sa.String(length=20), nullable=True),
        sa.Column("receptor_nombre", sa.String(length=255), nullable=True),
        sa.Column("neto", sa.Numeric(14, 2), server_default="0", nullable=False),
        sa.Column("exento", sa.Numeric(14, 2), server_default="0", nullable=False),
        sa.Column("impuesto", sa.Numeric(14, 2), server_default="0", nullable=False),
        sa.Column("total", sa.Numeric(14, 2), nullable=False),
        sa.Column("moneda", sa.String(length=3), server_default="CLP", nullable=False),
        sa.Column("impuesto_detalle", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("items", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("estado", sa.String(length=20), server_default="pendiente", nullable=False),
        sa.Column("track_id", sa.String(length=120), nullable=True),
        sa.Column("sello", sa.String(length=255), nullable=True),
        sa.Column("motivo", sa.String(length=500), nullable=True),
        sa.Column("xml", sa.String(), nullable=True),
        sa.Column("referencia_id", sa.UUID(), nullable=True),
        sa.Column("appointment_id", sa.UUID(), nullable=True),
        sa.Column("cash_payment_id", sa.UUID(), nullable=True),
        sa.Column("ledger_entry_id", sa.UUID(), nullable=True),
        sa.Column("emitido_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["emitter_id"], ["tax_emitters.id"]),
        sa.ForeignKeyConstraint(["referencia_id"], ["tax_documents.id"]),
        sa.ForeignKeyConstraint(["appointment_id"], ["appointments.id"]),
        sa.ForeignKeyConstraint(["cash_payment_id"], ["cash_payments.id"]),
        sa.ForeignKeyConstraint(["ledger_entry_id"], ["ledger_entries.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("emitter_id", "tipo_documento", "serie", "folio", name="uq_tax_doc_folio"),
    )
    op.create_index(op.f("ix_tax_documents_clinic_id"), "tax_documents", ["clinic_id"], unique=False)
    op.create_index(op.f("ix_tax_documents_emitter_id"), "tax_documents", ["emitter_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_tax_documents_emitter_id"), table_name="tax_documents")
    op.drop_index(op.f("ix_tax_documents_clinic_id"), table_name="tax_documents")
    op.drop_table("tax_documents")
    op.drop_index(op.f("ix_tax_folio_ranges_emitter_id"), table_name="tax_folio_ranges")
    op.drop_index(op.f("ix_tax_folio_ranges_clinic_id"), table_name="tax_folio_ranges")
    op.drop_table("tax_folio_ranges")
    op.drop_index(op.f("ix_tax_emitters_clinic_id"), table_name="tax_emitters")
    op.drop_table("tax_emitters")
