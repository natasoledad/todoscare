"""MKT: atribución de conversiones — patients.origen_campana_id

FK opcional del paciente a la campaña que lo trajo (UTM/ref al registrarse).

Revision ID: e5a1b2c3d4f8
Revises: d4f0a1b2c3e7
Create Date: 2026-07-24
"""

import sqlalchemy as sa
from alembic import op

revision = "e5a1b2c3d4f8"
down_revision = "d4f0a1b2c3e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("patients", sa.Column("origen_campana_id", sa.UUID(), nullable=True))
    op.create_foreign_key("patients_origen_campana_id_fkey", "patients", "marketing_campaigns", ["origen_campana_id"], ["id"])
    op.create_index(op.f("ix_patients_origen_campana_id"), "patients", ["origen_campana_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_patients_origen_campana_id"), table_name="patients")
    op.drop_constraint("patients_origen_campana_id_fkey", "patients", type_="foreignkey")
    op.drop_column("patients", "origen_campana_id")
