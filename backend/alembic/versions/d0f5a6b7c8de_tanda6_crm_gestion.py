"""Tanda 6: crm_tasks + satisfaction_surveys + message_templates

Revision ID: d0f5a6b7c8de
Revises: c9e4f5a6b7cd
Create Date: 2026-08-07
"""

import sqlalchemy as sa
from alembic import op

revision = "d0f5a6b7c8de"
down_revision = "c9e4f5a6b7cd"
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
        "crm_tasks",
        *_audit(),
        sa.Column("titulo", sa.String(length=255), nullable=False),
        sa.Column("descripcion", sa.String(length=1000), nullable=True),
        sa.Column("patient_id", sa.UUID(), nullable=True),
        sa.Column("estado", sa.String(length=20), server_default="pendiente", nullable=False),
        sa.Column("vencimiento", sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_crm_tasks_clinic_id"), "crm_tasks", ["clinic_id"], unique=False)

    op.create_table(
        "satisfaction_surveys",
        *_audit(),
        sa.Column("patient_id", sa.UUID(), nullable=True),
        sa.Column("paciente_nombre", sa.String(length=255), nullable=True),
        sa.Column("appointment_id", sa.UUID(), nullable=True),
        sa.Column("estado", sa.String(length=20), server_default="enviada", nullable=False),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("comentario", sa.String(length=1000), nullable=True),
        sa.Column("respondida_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_satisfaction_surveys_clinic_id"), "satisfaction_surveys", ["clinic_id"], unique=False)

    op.create_table(
        "message_templates",
        *_audit(),
        sa.Column("nombre", sa.String(length=255), nullable=False),
        sa.Column("canal", sa.String(length=20), server_default="email", nullable=False),
        sa.Column("asunto", sa.String(length=255), nullable=True),
        sa.Column("cuerpo", sa.String(length=4000), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_message_templates_clinic_id"), "message_templates", ["clinic_id"], unique=False)


def downgrade() -> None:
    op.drop_table("message_templates")
    op.drop_table("satisfaction_surveys")
    op.drop_table("crm_tasks")
