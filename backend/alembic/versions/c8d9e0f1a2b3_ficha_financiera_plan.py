"""Ficha financiera del plan (69.7): descuento en el plan + pago atribuido a plan

Revision ID: c8d9e0f1a2b3
Revises: b7c8d9e0f1a2
Create Date: 2026-08-18
"""

import sqlalchemy as sa
from alembic import op

revision = "c8d9e0f1a2b3"
down_revision = "b7c8d9e0f1a2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("treatment_plans", sa.Column("descuento_pct", sa.Numeric(precision=5, scale=4), server_default="0", nullable=False))
    op.add_column("cash_payments", sa.Column("treatment_plan_id", sa.UUID(), nullable=True))
    op.create_foreign_key("fk_cash_payments_treatment_plan_id", "cash_payments", "treatment_plans", ["treatment_plan_id"], ["id"])
    op.create_index(op.f("ix_cash_payments_treatment_plan_id"), "cash_payments", ["treatment_plan_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_cash_payments_treatment_plan_id"), table_name="cash_payments")
    op.drop_constraint("fk_cash_payments_treatment_plan_id", "cash_payments", type_="foreignkey")
    op.drop_column("cash_payments", "treatment_plan_id")
    op.drop_column("treatment_plans", "descuento_pct")
