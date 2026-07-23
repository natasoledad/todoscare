"""Fase 6 (CRM): conciliación de liquidaciones — payment_splits.estado

Un split de pago nace "pendiente"; el CRM lo concilia ("conciliado") al
liquidar al prestador, lo que asienta un egreso inmutable en el ledger
(Spec CRM §5.2). Se añade el estado y la marca temporal de conciliación.

Revision ID: a1c7f0e2b3d4
Revises: cbeb6e3d9d3c
Create Date: 2026-07-23
"""

import sqlalchemy as sa
from alembic import op

revision = "a1c7f0e2b3d4"
down_revision = "cbeb6e3d9d3c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "payment_splits",
        sa.Column("estado", sa.String(length=20), nullable=False, server_default="pendiente"),
    )
    op.add_column(
        "payment_splits",
        sa.Column("conciliado_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("payment_splits", "conciliado_at")
    op.drop_column("payment_splits", "estado")
