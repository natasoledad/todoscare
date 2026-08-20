"""Evoluciones clínicas con doble firma + anulación auditada (70.6)

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-08-20
"""

import sqlalchemy as sa
from alembic import op

revision = "b4c5d6e7f8a9"
down_revision = "a3b4c5d6e7f8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "clinical_evolutions",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("patient_id", sa.UUID(), nullable=False),
        sa.Column("autor_id", sa.UUID(), nullable=False),
        sa.Column("record_id", sa.UUID(), nullable=True),
        sa.Column("texto", sa.Text(), nullable=False),
        sa.Column("firmado_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("firma_tratante", sa.Text(), nullable=True),
        sa.Column("cofirmado_por", sa.UUID(), nullable=True),
        sa.Column("cofirmado_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("firma_cofirmante", sa.Text(), nullable=True),
        sa.Column("estado", sa.String(length=20), server_default="vigente", nullable=False),
        sa.Column("anulado_por", sa.UUID(), nullable=True),
        sa.Column("anulado_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("motivo_anulacion", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["autor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["record_id"], ["medical_records.id"]),
        sa.ForeignKeyConstraint(["cofirmado_por"], ["users.id"]),
        sa.ForeignKeyConstraint(["anulado_por"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_clinical_evolutions_clinic_id"), "clinical_evolutions", ["clinic_id"], unique=False)
    op.create_index(op.f("ix_clinical_evolutions_patient_id"), "clinical_evolutions", ["patient_id"], unique=False)
    op.create_index(op.f("ix_clinical_evolutions_autor_id"), "clinical_evolutions", ["autor_id"], unique=False)
    op.create_index(op.f("ix_clinical_evolutions_record_id"), "clinical_evolutions", ["record_id"], unique=False)


def downgrade() -> None:
    op.drop_table("clinical_evolutions")
