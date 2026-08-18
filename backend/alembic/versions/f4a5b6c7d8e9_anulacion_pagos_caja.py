"""Anulación auditada de pagos de caja (67.1/67.2)

Añade a cash_payments los campos de anulación: anulado + auditoría (quién,
cuándo, motivo). El pago no se borra; se marca anulado y se asienta un reverso
en el ledger.

Revision ID: f4a5b6c7d8e9
Revises: e3f4a5b6c7d8
Create Date: 2026-08-18
"""

import sqlalchemy as sa
from alembic import op

revision = "f4a5b6c7d8e9"
down_revision = "e3f4a5b6c7d8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cash_payments", sa.Column("anulado", sa.Boolean(), server_default="false", nullable=False))
    op.add_column("cash_payments", sa.Column("anulado_por", sa.UUID(), nullable=True))
    op.add_column("cash_payments", sa.Column("anulado_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("cash_payments", sa.Column("motivo_anulacion", sa.String(length=255), nullable=True))
    op.create_foreign_key("fk_cash_payments_anulado_por", "cash_payments", "users", ["anulado_por"], ["id"])


def downgrade() -> None:
    op.drop_constraint("fk_cash_payments_anulado_por", "cash_payments", type_="foreignkey")
    op.drop_column("cash_payments", "motivo_anulacion")
    op.drop_column("cash_payments", "anulado_at")
    op.drop_column("cash_payments", "anulado_por")
    op.drop_column("cash_payments", "anulado")
