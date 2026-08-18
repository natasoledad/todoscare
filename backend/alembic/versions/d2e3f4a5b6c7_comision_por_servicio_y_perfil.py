"""Comisión: flag por servicio + % en el perfil del profesional (57.10 / 58)

- catalog_items.comisiona: ¿la prestación comisiona al profesional? (57.10).
- professional_profiles.comision_pct: % del profesional (NULL = % por defecto).

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-08-18
"""

import sqlalchemy as sa
from alembic import op

revision = "d2e3f4a5b6c7"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("catalog_items", sa.Column("comisiona", sa.Boolean(), server_default="true", nullable=False))
    op.add_column("professional_profiles", sa.Column("comision_pct", sa.Numeric(precision=5, scale=4), nullable=True))


def downgrade() -> None:
    op.drop_column("professional_profiles", "comision_pct")
    op.drop_column("catalog_items", "comisiona")
