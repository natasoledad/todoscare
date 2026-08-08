"""Tanda 5: clinical_documents + periodontograms

Revision ID: c9e4f5a6b7cd
Revises: b8d3e4f5c6ab
Create Date: 2026-08-07
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "c9e4f5a6b7cd"
down_revision = "b8d3e4f5c6ab"
branch_labels = None
depends_on = None


def _audit() -> list:
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
        "clinical_documents",
        *_audit(),
        sa.Column("patient_id", sa.UUID(), nullable=False),
        sa.Column("professional_id", sa.UUID(), nullable=False),
        sa.Column("tipo", sa.String(length=30), nullable=False),
        sa.Column("titulo", sa.String(length=255), nullable=False),
        sa.Column("contenido", sa.String(length=4000), nullable=True),
        sa.Column("estado", sa.String(length=20), server_default="emitido", nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["professional_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_clinical_documents_clinic_id"), "clinical_documents", ["clinic_id"], unique=False)
    op.create_index(op.f("ix_clinical_documents_patient_id"), "clinical_documents", ["patient_id"], unique=False)

    op.create_table(
        "periodontograms",
        *_audit(),
        sa.Column("patient_id", sa.UUID(), nullable=False),
        sa.Column("professional_id", sa.UUID(), nullable=False),
        sa.Column("datos", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("notas", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["professional_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_periodontograms_clinic_id"), "periodontograms", ["clinic_id"], unique=False)
    op.create_index(op.f("ix_periodontograms_patient_id"), "periodontograms", ["patient_id"], unique=False)


def downgrade() -> None:
    op.drop_table("periodontograms")
    op.drop_table("clinical_documents")
