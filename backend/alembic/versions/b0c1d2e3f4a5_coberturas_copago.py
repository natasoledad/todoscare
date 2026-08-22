"""Copago chileno: coberturas complementarias (seguros + CCAF) + traza en caja

Revision ID: b0c1d2e3f4a5
Revises: a9b0c1d2e3f4
Create Date: 2026-08-22
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "b0c1d2e3f4a5"
down_revision = "a9b0c1d2e3f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "coberturas_complementarias",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("tipo", sa.String(length=30), nullable=False),
        sa.Column("nombre", sa.String(length=120), nullable=False),
        sa.Column("modalidad", sa.String(length=20), server_default="porcentaje", nullable=False),
        sa.Column("valor", sa.Numeric(precision=12, scale=4), server_default="0", nullable=False),
        sa.Column("tope", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("deducible", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("permite_cuotas", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("activo", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_coberturas_complementarias_clinic_id"), "coberturas_complementarias", ["clinic_id"], unique=False)

    # Traza de cómo se llegó al copago de un pago: qué capas (previsión, seguro
    # complementario, CCAF) aportaron y cuánto. El monto del pago sigue siendo
    # el copago final; esto es el desglose para auditoría/conciliación.
    op.add_column("cash_payments", sa.Column("coberturas_aplicadas", postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column("cash_payments", "coberturas_aplicadas")
    op.drop_table("coberturas_complementarias")
