"""GES + campos demográficos chilenos (69.17 · 69.14)

Revision ID: f8a9b0c1d2e3
Revises: e7f8a9b0c1d2
Create Date: 2026-08-20
"""

import sqlalchemy as sa
from alembic import op

revision = "f8a9b0c1d2e3"
down_revision = "e7f8a9b0c1d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("patients", sa.Column("prevision", sa.String(length=20), nullable=True))
    op.add_column("patients", sa.Column("prevision_nombre", sa.String(length=120), nullable=True))
    op.add_column("patients", sa.Column("tramo_fonasa", sa.String(length=2), nullable=True))
    op.add_column("patients", sa.Column("nacionalidad", sa.String(length=60), nullable=True))
    op.add_column("patients", sa.Column("comuna", sa.String(length=120), nullable=True))
    op.add_column("patients", sa.Column("ges", sa.Boolean(), server_default="false", nullable=False))
    op.add_column("patients", sa.Column("ges_detalle", sa.String(length=255), nullable=True))


def downgrade() -> None:
    for col in ("ges_detalle", "ges", "comuna", "nacionalidad", "tramo_fonasa", "prevision_nombre", "prevision"):
        op.drop_column("patients", col)
