"""Diferenciadores IA (72): sugerencias de ficha generadas por la IA clínica

Revision ID: e0f1a2b3c4d5
Revises: d9e0f1a2b3c4
Create Date: 2026-08-18
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e0f1a2b3c4d5"
down_revision = "d9e0f1a2b3c4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_ficha_suggestions",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("patient_id", sa.UUID(), nullable=False),
        sa.Column("exam_order_id", sa.UUID(), nullable=True),
        sa.Column("resumen", sa.String(length=500), nullable=False),
        sa.Column("hallazgos", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("proximo_control", sa.Date(), nullable=True),
        sa.Column("estado", sa.String(length=20), server_default="pendiente", nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["exam_order_id"], ["exam_orders.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ai_ficha_suggestions_clinic_id"), "ai_ficha_suggestions", ["clinic_id"], unique=False)
    op.create_index(op.f("ix_ai_ficha_suggestions_patient_id"), "ai_ficha_suggestions", ["patient_id"], unique=False)
    op.create_index(op.f("ix_ai_ficha_suggestions_exam_order_id"), "ai_ficha_suggestions", ["exam_order_id"], unique=False)


def downgrade() -> None:
    op.drop_table("ai_ficha_suggestions")
