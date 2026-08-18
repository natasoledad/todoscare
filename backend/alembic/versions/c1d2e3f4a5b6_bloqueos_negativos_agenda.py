"""Bloqueos negativos de agenda (horarios especiales) — puntos 51 y 52.9

Crea `schedule_exceptions`: cierra la disponibilidad de un profesional en un
rango (vacaciones, permisos, feriados). Lo respetan la reserva, la
disponibilidad y la generación de bloques.

Revision ID: c1d2e3f4a5b6
Revises: b1c2d3e4f5a6
Create Date: 2026-08-18
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "c1d2e3f4a5b6"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "schedule_exceptions",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("professional_id", sa.UUID(), nullable=False),
        sa.Column("branch_id", sa.UUID(), nullable=True),
        sa.Column("rango", postgresql.TSTZRANGE(), nullable=False),
        sa.Column("motivo", sa.String(length=160), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["professional_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_schedule_exceptions_clinic_id"), "schedule_exceptions", ["clinic_id"], unique=False)
    op.create_index(op.f("ix_schedule_exceptions_professional_id"), "schedule_exceptions", ["professional_id"], unique=False)
    op.create_index(op.f("ix_schedule_exceptions_branch_id"), "schedule_exceptions", ["branch_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_schedule_exceptions_branch_id"), table_name="schedule_exceptions")
    op.drop_index(op.f("ix_schedule_exceptions_professional_id"), table_name="schedule_exceptions")
    op.drop_index(op.f("ix_schedule_exceptions_clinic_id"), table_name="schedule_exceptions")
    op.drop_table("schedule_exceptions")
