"""Documentos + consentimientos (64): plantillas por bloques + firma del paciente

Revision ID: a8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2026-08-19
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a8b9c0d1e2f3"
down_revision = "f7a8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_templates",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("nombre", sa.String(length=255), nullable=False),
        sa.Column("tipo", sa.String(length=30), nullable=False),
        sa.Column("bloques", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False),
        sa.Column("requiere_firma", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("activo", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_document_templates_clinic_id"), "document_templates", ["clinic_id"], unique=False)

    op.add_column("clinical_documents", sa.Column("template_id", sa.UUID(), nullable=True))
    op.add_column("clinical_documents", sa.Column("requiere_firma", sa.Boolean(), server_default="false", nullable=False))
    op.add_column("clinical_documents", sa.Column("firmado_paciente", sa.Boolean(), server_default="false", nullable=False))
    op.add_column("clinical_documents", sa.Column("firmado_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key("fk_clinical_documents_template_id", "clinical_documents", "document_templates", ["template_id"], ["id"])
    op.create_index(op.f("ix_clinical_documents_template_id"), "clinical_documents", ["template_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_clinical_documents_template_id"), table_name="clinical_documents")
    op.drop_constraint("fk_clinical_documents_template_id", "clinical_documents", type_="foreignkey")
    op.drop_column("clinical_documents", "firmado_at")
    op.drop_column("clinical_documents", "firmado_paciente")
    op.drop_column("clinical_documents", "requiere_firma")
    op.drop_column("clinical_documents", "template_id")
    op.drop_table("document_templates")
