"""Inventario movimientos (56.9 · 56.11): lotes y kardex de stock

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-08-19
"""

import sqlalchemy as sa
from alembic import op

revision = "b3c4d5e6f7a8"
down_revision = "a2b3c4d5e6f7"
branch_labels = None
depends_on = None


def _audit() -> list:
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
        "stock_lots",
        *_audit(),
        sa.Column("item_id", sa.UUID(), nullable=False),
        sa.Column("warehouse_id", sa.UUID(), nullable=False),
        sa.Column("lote", sa.String(length=60), nullable=True),
        sa.Column("vencimiento", sa.Date(), nullable=True),
        sa.Column("cantidad", sa.Numeric(precision=14, scale=2), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["item_id"], ["inventory_items.id"]),
        sa.ForeignKeyConstraint(["warehouse_id"], ["warehouses.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_stock_lots_clinic_id"), "stock_lots", ["clinic_id"], unique=False)
    op.create_index(op.f("ix_stock_lots_item_id"), "stock_lots", ["item_id"], unique=False)
    op.create_index(op.f("ix_stock_lots_warehouse_id"), "stock_lots", ["warehouse_id"], unique=False)
    op.create_index(op.f("ix_stock_lots_vencimiento"), "stock_lots", ["vencimiento"], unique=False)

    op.create_table(
        "stock_movements",
        *_audit(),
        sa.Column("item_id", sa.UUID(), nullable=False),
        sa.Column("warehouse_id", sa.UUID(), nullable=False),
        sa.Column("lot_id", sa.UUID(), nullable=True),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("cantidad", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("saldo", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("motivo", sa.String(length=255), nullable=True),
        sa.Column("cost_center_id", sa.UUID(), nullable=True),
        sa.Column("supplier_id", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["item_id"], ["inventory_items.id"]),
        sa.ForeignKeyConstraint(["warehouse_id"], ["warehouses.id"]),
        sa.ForeignKeyConstraint(["lot_id"], ["stock_lots.id"]),
        sa.ForeignKeyConstraint(["cost_center_id"], ["cost_centers.id"]),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_stock_movements_clinic_id"), "stock_movements", ["clinic_id"], unique=False)
    op.create_index(op.f("ix_stock_movements_item_id"), "stock_movements", ["item_id"], unique=False)
    op.create_index(op.f("ix_stock_movements_warehouse_id"), "stock_movements", ["warehouse_id"], unique=False)
    op.create_index(op.f("ix_stock_movements_lot_id"), "stock_movements", ["lot_id"], unique=False)
    op.create_index(op.f("ix_stock_movements_cost_center_id"), "stock_movements", ["cost_center_id"], unique=False)
    op.create_index(op.f("ix_stock_movements_supplier_id"), "stock_movements", ["supplier_id"], unique=False)


def downgrade() -> None:
    op.drop_table("stock_movements")
    op.drop_table("stock_lots")
