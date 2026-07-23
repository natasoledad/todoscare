"""Fase 7 (Aseguradora/Prestador): scope de aseguradora + pago de liquidación

- role_assignments.insurer_id: vincula el rol aseguradora a su entidad
  (el tercero pagador opera sobre su cartera, no sobre un tenant clínico).
  Se rehace la restricción única para incluirlo.
- settlements.pagado_at: marca temporal del pago de una liquidación.

Revision ID: b2d8e1f3a4c5
Revises: a1c7f0e2b3d4
Create Date: 2026-07-23
"""

import sqlalchemy as sa
from alembic import op

revision = "b2d8e1f3a4c5"
down_revision = "a1c7f0e2b3d4"
branch_labels = None
depends_on = None

_OLD_UQ = "role_assignments_user_id_role_id_clinic_id_branch_id_key"
_NEW_UQ = "role_assignments_user_role_clinic_branch_insurer_key"


def upgrade() -> None:
    op.add_column("role_assignments", sa.Column("insurer_id", sa.UUID(), nullable=True))
    op.create_foreign_key("role_assignments_insurer_id_fkey", "role_assignments", "insurers", ["insurer_id"], ["id"])
    op.create_index(op.f("ix_role_assignments_insurer_id"), "role_assignments", ["insurer_id"], unique=False)
    op.drop_constraint(_OLD_UQ, "role_assignments", type_="unique")
    op.create_unique_constraint(_NEW_UQ, "role_assignments", ["user_id", "role_id", "clinic_id", "branch_id", "insurer_id"])

    op.add_column("settlements", sa.Column("pagado_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("settlements", "pagado_at")
    op.drop_constraint(_NEW_UQ, "role_assignments", type_="unique")
    op.create_unique_constraint(_OLD_UQ, "role_assignments", ["user_id", "role_id", "clinic_id", "branch_id"])
    op.drop_index(op.f("ix_role_assignments_insurer_id"), table_name="role_assignments")
    op.drop_constraint("role_assignments_insurer_id_fkey", "role_assignments", type_="foreignkey")
    op.drop_column("role_assignments", "insurer_id")
