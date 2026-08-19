"""Firma manuscrita del profesional (48): firma en el perfil + instantánea en documentos

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-08-19
"""

import sqlalchemy as sa
from alembic import op

revision = "e1f2a3b4c5d6"
down_revision = "d0e1f2a3b4c5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("professional_profiles", sa.Column("firma", sa.Text(), nullable=True))
    op.add_column("clinical_documents", sa.Column("firma_profesional", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("clinical_documents", "firma_profesional")
    op.drop_column("professional_profiles", "firma")
