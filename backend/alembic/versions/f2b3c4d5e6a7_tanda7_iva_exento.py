"""Tanda 7 (IVA exento): catalog_items.afecto_iva

Marca si una prestación está afecta a IVA. En Chile las prestaciones médicas/
odontológicas son exentas (D.L. 825 Art. 12 E) y solo algunos exámenes
diagnósticos particulares son afectos — este flag lo decide por servicio.

Revision ID: f2b3c4d5e6a7
Revises: e1a2b3c4d5f6
Create Date: 2026-08-11
"""

import sqlalchemy as sa
from alembic import op

revision = "f2b3c4d5e6a7"
down_revision = "e1a2b3c4d5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "catalog_items",
        sa.Column("afecto_iva", sa.Boolean(), server_default="true", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("catalog_items", "afecto_iva")
