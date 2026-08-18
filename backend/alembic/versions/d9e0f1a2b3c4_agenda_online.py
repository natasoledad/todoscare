"""Agenda online pública (60): slug + config de clínica, servicio reservable, solicitudes

Revision ID: d9e0f1a2b3c4
Revises: c8d9e0f1a2b3
Create Date: 2026-08-18
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "d9e0f1a2b3c4"
down_revision = "c8d9e0f1a2b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("clinics", sa.Column("slug", sa.String(length=80), nullable=True))
    op.create_unique_constraint("uq_clinics_slug", "clinics", ["slug"])
    op.add_column("clinics", sa.Column("agenda_online", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("catalog_items", sa.Column("reservable_online", sa.Boolean(), server_default="false", nullable=False))

    op.create_table(
        "online_booking_requests",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("branch_id", sa.UUID(), nullable=False),
        sa.Column("professional_id", sa.UUID(), nullable=False),
        sa.Column("service_id", sa.UUID(), nullable=True),
        sa.Column("slot", postgresql.TSTZRANGE(), nullable=False),
        sa.Column("codigo", sa.String(length=12), nullable=False),
        sa.Column("estado", sa.String(length=20), server_default="pendiente", nullable=False),
        sa.Column("paciente_nombre", sa.String(length=255), nullable=False),
        sa.Column("paciente_rut", sa.String(length=50), nullable=True),
        sa.Column("paciente_telefono", sa.String(length=40), nullable=True),
        sa.Column("paciente_email", sa.String(length=255), nullable=True),
        sa.Column("notas", sa.String(length=500), nullable=True),
        sa.Column("appointment_id", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["professional_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["service_id"], ["catalog_items.id"]),
        sa.ForeignKeyConstraint(["appointment_id"], ["appointments.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_online_booking_requests_clinic_id"), "online_booking_requests", ["clinic_id"], unique=False)
    op.create_index(op.f("ix_online_booking_requests_branch_id"), "online_booking_requests", ["branch_id"], unique=False)
    op.create_index(op.f("ix_online_booking_requests_professional_id"), "online_booking_requests", ["professional_id"], unique=False)
    op.create_index(op.f("ix_online_booking_requests_codigo"), "online_booking_requests", ["codigo"], unique=False)
    op.create_index(op.f("ix_online_booking_requests_appointment_id"), "online_booking_requests", ["appointment_id"], unique=False)


def downgrade() -> None:
    op.drop_table("online_booking_requests")
    op.drop_column("catalog_items", "reservable_online")
    op.drop_column("clinics", "agenda_online")
    op.drop_constraint("uq_clinics_slug", "clinics", type_="unique")
    op.drop_column("clinics", "slug")
