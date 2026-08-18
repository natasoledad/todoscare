"""Medios de pago configurables (66)

Crea `payment_methods`: catálogo por clínica con retención %, facturable,
permite devolución, acepta cuotas y activo.

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-08-18
"""

import sqlalchemy as sa
from alembic import op

revision = "e3f4a5b6c7d8"
down_revision = "d2e3f4a5b6c7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payment_methods",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("nombre", sa.String(length=80), nullable=False),
        sa.Column("retencion_pct", sa.Numeric(precision=5, scale=4), server_default="0", nullable=False),
        sa.Column("facturable", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("permite_devolucion", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("acepta_cuotas", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("activo", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_payment_methods_clinic_id"), "payment_methods", ["clinic_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_payment_methods_clinic_id"), table_name="payment_methods")
    op.drop_table("payment_methods")
