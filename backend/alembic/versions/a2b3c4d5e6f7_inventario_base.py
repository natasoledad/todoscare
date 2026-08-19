"""Inventario base (56): proveedores, centros de costo, bodegas e ítems de insumo

Revision ID: a2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-08-19
"""

import sqlalchemy as sa
from alembic import op

revision = "a2b3c4d5e6f7"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None

def _audit() -> list:
    """Columnas comunes (AuditMixin + TenantMixin), frescas por tabla —
    un Column no puede compartirse entre tablas en SQLAlchemy 2.0."""
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
        "suppliers",
        *_audit(),
        sa.Column("nombre", sa.String(length=255), nullable=False),
        sa.Column("rut", sa.String(length=50), nullable=True),
        sa.Column("contacto", sa.String(length=255), nullable=True),
        sa.Column("activo", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_suppliers_clinic_id"), "suppliers", ["clinic_id"], unique=False)

    op.create_table(
        "cost_centers",
        *_audit(),
        sa.Column("nombre", sa.String(length=120), nullable=False),
        sa.Column("activo", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_cost_centers_clinic_id"), "cost_centers", ["clinic_id"], unique=False)

    op.create_table(
        "warehouses",
        *_audit(),
        sa.Column("branch_id", sa.UUID(), nullable=True),
        sa.Column("nombre", sa.String(length=120), nullable=False),
        sa.Column("activo", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_warehouses_clinic_id"), "warehouses", ["clinic_id"], unique=False)
    op.create_index(op.f("ix_warehouses_branch_id"), "warehouses", ["branch_id"], unique=False)

    op.create_table(
        "inventory_items",
        *_audit(),
        sa.Column("nombre", sa.String(length=255), nullable=False),
        sa.Column("sku", sa.String(length=60), nullable=True),
        sa.Column("unidad", sa.String(length=20), server_default="unidad", nullable=False),
        sa.Column("stock_minimo", sa.Numeric(precision=14, scale=2), server_default="0", nullable=False),
        sa.Column("supplier_id", sa.UUID(), nullable=True),
        sa.Column("cost_center_id", sa.UUID(), nullable=True),
        sa.Column("activo", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"]),
        sa.ForeignKeyConstraint(["cost_center_id"], ["cost_centers.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("clinic_id", "sku", name="uq_inventory_item_clinic_sku"),
    )
    op.create_index(op.f("ix_inventory_items_clinic_id"), "inventory_items", ["clinic_id"], unique=False)
    op.create_index(op.f("ix_inventory_items_supplier_id"), "inventory_items", ["supplier_id"], unique=False)
    op.create_index(op.f("ix_inventory_items_cost_center_id"), "inventory_items", ["cost_center_id"], unique=False)


def downgrade() -> None:
    op.drop_table("inventory_items")
    op.drop_table("warehouses")
    op.drop_table("cost_centers")
    op.drop_table("suppliers")
