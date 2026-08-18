"""Horario semanal recurrente (plantilla) — punto 52

Crea `weekly_schedule_templates`: el patrón semanal por profesional/sucursal/día
desde el que se materializan los availability_blocks (con descanso, modalidad,
capacidad y recinto).

Revision ID: b1c2d3e4f5a6
Revises: a5b6c7d8e9f0
Create Date: 2026-08-18
"""

import sqlalchemy as sa
from alembic import op

revision = "b1c2d3e4f5a6"
down_revision = "a5b6c7d8e9f0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "weekly_schedule_templates",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("professional_id", sa.UUID(), nullable=False),
        sa.Column("branch_id", sa.UUID(), nullable=False),
        sa.Column("room_id", sa.UUID(), nullable=True),
        sa.Column("dia_semana", sa.Integer(), nullable=False),
        sa.Column("hora_inicio", sa.Time(), nullable=False),
        sa.Column("hora_fin", sa.Time(), nullable=False),
        sa.Column("descanso_inicio", sa.Time(), nullable=True),
        sa.Column("descanso_fin", sa.Time(), nullable=True),
        sa.Column("modalidad", sa.String(length=20), server_default="presencial", nullable=False),
        sa.Column("capacidad", sa.Integer(), server_default="1", nullable=False),
        sa.Column("activo", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["professional_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_weekly_schedule_templates_clinic_id"), "weekly_schedule_templates", ["clinic_id"], unique=False)
    op.create_index(op.f("ix_weekly_schedule_templates_professional_id"), "weekly_schedule_templates", ["professional_id"], unique=False)
    op.create_index(op.f("ix_weekly_schedule_templates_branch_id"), "weekly_schedule_templates", ["branch_id"], unique=False)
    op.create_index(op.f("ix_weekly_schedule_templates_room_id"), "weekly_schedule_templates", ["room_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_weekly_schedule_templates_room_id"), table_name="weekly_schedule_templates")
    op.drop_index(op.f("ix_weekly_schedule_templates_branch_id"), table_name="weekly_schedule_templates")
    op.drop_index(op.f("ix_weekly_schedule_templates_professional_id"), table_name="weekly_schedule_templates")
    op.drop_index(op.f("ix_weekly_schedule_templates_clinic_id"), table_name="weekly_schedule_templates")
    op.drop_table("weekly_schedule_templates")
