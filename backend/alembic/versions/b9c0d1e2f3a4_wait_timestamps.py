"""Reportería/BI (68.12): marcas de sala de espera / atención para el KPI de espera

Revision ID: b9c0d1e2f3a4
Revises: a8b9c0d1e2f3
Create Date: 2026-08-19
"""

import sqlalchemy as sa
from alembic import op

revision = "b9c0d1e2f3a4"
down_revision = "a8b9c0d1e2f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("appointments", sa.Column("sala_espera_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("appointments", sa.Column("atencion_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("appointments", "atencion_at")
    op.drop_column("appointments", "sala_espera_at")
