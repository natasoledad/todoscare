"""Diagnóstico CIE-10 (71.20): catálogo global + diagnósticos por paciente

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-08-20
"""

import sqlalchemy as sa
from alembic import op

revision = "f2a3b4c5d6e7"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cie10_codes",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("codigo", sa.String(length=10), nullable=False),
        sa.Column("descripcion", sa.String(length=300), nullable=False),
        sa.Column("categoria", sa.String(length=120), nullable=True),
        sa.Column("activo", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("codigo", name="uq_cie10_codigo"),
    )
    op.create_index(op.f("ix_cie10_codes_codigo"), "cie10_codes", ["codigo"], unique=False)

    op.create_table(
        "clinical_diagnoses",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("patient_id", sa.UUID(), nullable=False),
        sa.Column("professional_id", sa.UUID(), nullable=False),
        sa.Column("record_id", sa.UUID(), nullable=True),
        sa.Column("cie10_id", sa.UUID(), nullable=False),
        sa.Column("tipo", sa.String(length=20), server_default="principal", nullable=False),
        sa.Column("observacion", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["professional_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["record_id"], ["medical_records.id"]),
        sa.ForeignKeyConstraint(["cie10_id"], ["cie10_codes.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_clinical_diagnoses_clinic_id"), "clinical_diagnoses", ["clinic_id"], unique=False)
    op.create_index(op.f("ix_clinical_diagnoses_patient_id"), "clinical_diagnoses", ["patient_id"], unique=False)
    op.create_index(op.f("ix_clinical_diagnoses_professional_id"), "clinical_diagnoses", ["professional_id"], unique=False)
    op.create_index(op.f("ix_clinical_diagnoses_record_id"), "clinical_diagnoses", ["record_id"], unique=False)
    op.create_index(op.f("ix_clinical_diagnoses_cie10_id"), "clinical_diagnoses", ["cie10_id"], unique=False)


def downgrade() -> None:
    op.drop_table("clinical_diagnoses")
    op.drop_table("cie10_codes")
