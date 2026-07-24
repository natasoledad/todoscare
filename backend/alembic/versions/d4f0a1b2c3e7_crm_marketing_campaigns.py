"""CRM: gestión de marketing digital — tabla marketing_campaigns

Campañas por canal (presupuesto, gasto, leads, conversiones). El gasto se
asienta también en el ledger (tipo='gasto_marketing') para alimentar el CAC.

Revision ID: d4f0a1b2c3e7
Revises: c3e9f0a1b2d6
Create Date: 2026-07-24
"""

import sqlalchemy as sa
from alembic import op

revision = "d4f0a1b2c3e7"
down_revision = "c3e9f0a1b2d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "marketing_campaigns",
        sa.Column("nombre", sa.String(length=255), nullable=False),
        sa.Column("canal", sa.String(length=30), nullable=False),
        sa.Column("estado", sa.String(length=20), server_default="activa", nullable=False),
        sa.Column("presupuesto", sa.Numeric(precision=14, scale=2), server_default="0", nullable=False),
        sa.Column("gasto", sa.Numeric(precision=14, scale=2), server_default="0", nullable=False),
        sa.Column("leads", sa.Integer(), server_default="0", nullable=False),
        sa.Column("conversiones", sa.Integer(), server_default="0", nullable=False),
        sa.Column("fecha_inicio", sa.Date(), nullable=True),
        sa.Column("fecha_fin", sa.Date(), nullable=True),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_marketing_campaigns_clinic_id"), "marketing_campaigns", ["clinic_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_marketing_campaigns_clinic_id"), table_name="marketing_campaigns")
    op.drop_table("marketing_campaigns")
