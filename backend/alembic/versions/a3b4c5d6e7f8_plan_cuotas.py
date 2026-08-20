"""Financiamiento en cuotas del plan de tratamiento (69.19)

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-08-20
"""

import sqlalchemy as sa
from alembic import op

revision = "a3b4c5d6e7f8"
down_revision = "f2a3b4c5d6e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "plan_installments",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("plan_id", sa.UUID(), nullable=False),
        sa.Column("numero", sa.Integer(), nullable=False),
        sa.Column("monto", sa.Numeric(14, 2), nullable=False),
        sa.Column("vencimiento", sa.Date(), nullable=False),
        sa.Column("pagado", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("pagado_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["plan_id"], ["treatment_plans.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_plan_installments_clinic_id"), "plan_installments", ["clinic_id"], unique=False)
    op.create_index(op.f("ix_plan_installments_plan_id"), "plan_installments", ["plan_id"], unique=False)


def downgrade() -> None:
    op.drop_table("plan_installments")
