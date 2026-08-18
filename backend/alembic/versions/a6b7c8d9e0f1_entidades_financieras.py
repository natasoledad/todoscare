"""Entidades financieras: bancos e Isapres/Fonasa (63)

Crea `financial_entities`: catálogo por clínica (banco | isapre) con activo.

Revision ID: a6b7c8d9e0f1
Revises: f4a5b6c7d8e9
Create Date: 2026-08-18
"""

import sqlalchemy as sa
from alembic import op

revision = "a6b7c8d9e0f1"
down_revision = "f4a5b6c7d8e9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "financial_entities",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("nombre", sa.String(length=120), nullable=False),
        sa.Column("tipo", sa.String(length=20), server_default="banco", nullable=False),
        sa.Column("activo", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_financial_entities_clinic_id"), "financial_entities", ["clinic_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_financial_entities_clinic_id"), table_name="financial_entities")
    op.drop_table("financial_entities")
