"""Prepago al agendar (61.7): campos de prepago en la solicitud online

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-08-19
"""

import sqlalchemy as sa
from alembic import op

revision = "f7a8b9c0d1e2"
down_revision = "e6f7a8b9c0d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("online_booking_requests", sa.Column("prepago_requerido", sa.Boolean(), server_default="false", nullable=False))
    op.add_column("online_booking_requests", sa.Column("prepago_monto", sa.Numeric(precision=12, scale=2), server_default="0", nullable=False))
    op.add_column("online_booking_requests", sa.Column("prepagado", sa.Boolean(), server_default="false", nullable=False))
    op.add_column("online_booking_requests", sa.Column("prepago_ref", sa.String(length=80), nullable=True))


def downgrade() -> None:
    op.drop_column("online_booking_requests", "prepago_ref")
    op.drop_column("online_booking_requests", "prepagado")
    op.drop_column("online_booking_requests", "prepago_monto")
    op.drop_column("online_booking_requests", "prepago_requerido")
