"""Fase 8 (Integraciones): traza de conectores + suscripciones de web push

- integration_events: bandeja de entrada/salida de cada conector externo
  (whatsapp, lab, farmacia, pago, mapas, push), con payload y resultado.
- push_subscriptions: suscripciones de web push por usuario.

Revision ID: c3e9f0a1b2d6
Revises: b2d8e1f3a4c5
Create Date: 2026-07-23
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "c3e9f0a1b2d6"
down_revision = "b2d8e1f3a4c5"
branch_labels = None
depends_on = None


def _audit_cols() -> list:
    return [
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        "integration_events",
        sa.Column("tipo", sa.String(length=30), nullable=False),
        sa.Column("direccion", sa.String(length=10), nullable=False),
        sa.Column("estado", sa.String(length=20), server_default="recibido", nullable=False),
        sa.Column("ref", sa.String(length=255), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("resultado", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        *_audit_cols(),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_integration_events_clinic_id"), "integration_events", ["clinic_id"], unique=False)

    op.create_table(
        "push_subscriptions",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("endpoint", sa.String(length=500), nullable=False),
        sa.Column("activo", sa.Boolean(), server_default="true", nullable=False),
        *_audit_cols(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_push_subscriptions_user_id"), "push_subscriptions", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_push_subscriptions_user_id"), table_name="push_subscriptions")
    op.drop_table("push_subscriptions")
    op.drop_index(op.f("ix_integration_events_clinic_id"), table_name="integration_events")
    op.drop_table("integration_events")
