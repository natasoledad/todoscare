"""Laboratorios · órdenes de trabajo (57.11 · 57.12 · 57.6)

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-08-19
"""

import sqlalchemy as sa
from alembic import op

revision = "d5e6f7a8b9c0"
down_revision = "c4d5e6f7a8b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lab_orders",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("lab_id", sa.UUID(), nullable=False),
        sa.Column("lab_service_id", sa.UUID(), nullable=True),
        sa.Column("patient_id", sa.UUID(), nullable=True),
        sa.Column("treatment_plan_id", sa.UUID(), nullable=True),
        sa.Column("professional_id", sa.UUID(), nullable=True),
        sa.Column("descripcion", sa.String(length=255), nullable=False),
        sa.Column("pieza", sa.String(length=10), nullable=True),
        sa.Column("costo", sa.Numeric(precision=12, scale=2), server_default="0", nullable=False),
        sa.Column("precio", sa.Numeric(precision=12, scale=2), server_default="0", nullable=False),
        sa.Column("estado", sa.String(length=20), server_default="solicitado", nullable=False),
        sa.Column("fecha_entrega", sa.Date(), nullable=True),
        sa.Column("pagado", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("pagado_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notas", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["lab_id"], ["dental_labs.id"]),
        sa.ForeignKeyConstraint(["lab_service_id"], ["lab_services.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["treatment_plan_id"], ["treatment_plans.id"]),
        sa.ForeignKeyConstraint(["professional_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for col in ("clinic_id", "lab_id", "lab_service_id", "patient_id", "treatment_plan_id", "professional_id"):
        op.create_index(op.f(f"ix_lab_orders_{col}"), "lab_orders", [col], unique=False)


def downgrade() -> None:
    op.drop_table("lab_orders")
