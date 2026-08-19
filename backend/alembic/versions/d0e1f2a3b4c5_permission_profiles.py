"""Perfiles de acceso reutilizables (48): perfil nombrado de permisos + asignación a usuarios

Revision ID: d0e1f2a3b4c5
Revises: c0d1e2f3a4b5
Create Date: 2026-08-19
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "d0e1f2a3b4c5"
down_revision = "c0d1e2f3a4b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "permission_profiles",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("nombre", sa.String(length=80), nullable=False),
        sa.Column("base_role", sa.String(length=50), nullable=False),
        sa.Column("permisos", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False),
        sa.Column("sin_restriccion", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("activo", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("clinic_id", "nombre", name="uq_permission_profile_nombre"),
    )
    op.create_index(op.f("ix_permission_profiles_clinic_id"), "permission_profiles", ["clinic_id"], unique=False)

    op.create_table(
        "user_permission_profiles",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("profile_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["profile_id"], ["permission_profiles.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "clinic_id", name="uq_user_permission_profile"),
    )
    op.create_index(op.f("ix_user_permission_profiles_user_id"), "user_permission_profiles", ["user_id"], unique=False)
    op.create_index(op.f("ix_user_permission_profiles_clinic_id"), "user_permission_profiles", ["clinic_id"], unique=False)
    op.create_index(op.f("ix_user_permission_profiles_profile_id"), "user_permission_profiles", ["profile_id"], unique=False)


def downgrade() -> None:
    op.drop_table("user_permission_profiles")
    op.drop_table("permission_profiles")
