"""Laboratorios dentales · catálogo (57.1 · 57.3b): labs y sus prestaciones

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-08-19
"""

import sqlalchemy as sa
from alembic import op

revision = "c4d5e6f7a8b9"
down_revision = "b3c4d5e6f7a8"
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
        "dental_labs",
        *_audit(),
        sa.Column("nombre", sa.String(length=255), nullable=False),
        sa.Column("rut", sa.String(length=50), nullable=True),
        sa.Column("contacto", sa.String(length=255), nullable=True),
        sa.Column("activo", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_dental_labs_clinic_id"), "dental_labs", ["clinic_id"], unique=False)

    op.create_table(
        "lab_services",
        *_audit(),
        sa.Column("lab_id", sa.UUID(), nullable=False),
        sa.Column("nombre", sa.String(length=255), nullable=False),
        sa.Column("costo", sa.Numeric(precision=12, scale=2), server_default="0", nullable=False),
        sa.Column("precio", sa.Numeric(precision=12, scale=2), server_default="0", nullable=False),
        sa.Column("activo", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["lab_id"], ["dental_labs.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_lab_services_clinic_id"), "lab_services", ["clinic_id"], unique=False)
    op.create_index(op.f("ix_lab_services_lab_id"), "lab_services", ["lab_id"], unique=False)


def downgrade() -> None:
    op.drop_table("lab_services")
    op.drop_table("dental_labs")
