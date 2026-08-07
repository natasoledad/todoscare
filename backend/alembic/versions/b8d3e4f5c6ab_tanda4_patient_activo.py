"""Tanda 4: patients.activo (habilitar/deshabilitar paciente)

Revision ID: b8d3e4f5c6ab
Revises: a7c2d3e4b5fa
Create Date: 2026-08-07
"""

import sqlalchemy as sa
from alembic import op

revision = "b8d3e4f5c6ab"
down_revision = "a7c2d3e4b5fa"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("patients", sa.Column("activo", sa.Boolean(), server_default="true", nullable=False))


def downgrade() -> None:
    op.drop_column("patients", "activo")
