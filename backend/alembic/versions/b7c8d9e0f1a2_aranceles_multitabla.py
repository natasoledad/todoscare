"""Aranceles multi-tabla: Arancel -> Categoria -> Item (62)

Revision ID: b7c8d9e0f1a2
Revises: a6b7c8d9e0f1
Create Date: 2026-08-18
"""

import sqlalchemy as sa
from alembic import op

revision = "b7c8d9e0f1a2"
down_revision = "a6b7c8d9e0f1"
branch_labels = None
depends_on = None


def _audit_cols() -> list:
    return [
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "price_tariffs",
        *_audit_cols(),
        sa.Column("nombre", sa.String(length=120), nullable=False),
        sa.Column("tipo", sa.String(length=20), server_default="particular", nullable=False),
        sa.Column("es_base", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("activo", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_price_tariffs_clinic_id"), "price_tariffs", ["clinic_id"], unique=False)

    op.create_table(
        "price_tariff_categories",
        *_audit_cols(),
        sa.Column("arancel_id", sa.UUID(), nullable=False),
        sa.Column("nombre", sa.String(length=120), nullable=False),
        sa.Column("orden", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["arancel_id"], ["price_tariffs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_price_tariff_categories_clinic_id"), "price_tariff_categories", ["clinic_id"], unique=False)
    op.create_index(op.f("ix_price_tariff_categories_arancel_id"), "price_tariff_categories", ["arancel_id"], unique=False)

    op.create_table(
        "price_tariff_items",
        *_audit_cols(),
        sa.Column("arancel_id", sa.UUID(), nullable=False),
        sa.Column("categoria_id", sa.UUID(), nullable=True),
        sa.Column("codigo", sa.String(length=40), nullable=True),
        sa.Column("nombre", sa.String(length=255), nullable=False),
        sa.Column("precio", sa.Numeric(precision=12, scale=2), server_default="0", nullable=False),
        sa.Column("precio_referencia", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("permite_descuento", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("comisiona", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("activo", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["arancel_id"], ["price_tariffs.id"]),
        sa.ForeignKeyConstraint(["categoria_id"], ["price_tariff_categories.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_price_tariff_items_clinic_id"), "price_tariff_items", ["clinic_id"], unique=False)
    op.create_index(op.f("ix_price_tariff_items_arancel_id"), "price_tariff_items", ["arancel_id"], unique=False)
    op.create_index(op.f("ix_price_tariff_items_categoria_id"), "price_tariff_items", ["categoria_id"], unique=False)


def downgrade() -> None:
    op.drop_table("price_tariff_items")
    op.drop_table("price_tariff_categories")
    op.drop_table("price_tariffs")
