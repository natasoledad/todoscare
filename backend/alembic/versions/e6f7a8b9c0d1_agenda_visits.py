"""Dashboard de conversión (60.12): registro de visitas a la agenda online pública

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-08-19
"""

import sqlalchemy as sa
from alembic import op

revision = "e6f7a8b9c0d1"
down_revision = "d5e6f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "public_agenda_visits",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_public_agenda_visits_clinic_id"), "public_agenda_visits", ["clinic_id"], unique=False)
    op.create_index("ix_public_agenda_visits_clinic_created", "public_agenda_visits", ["clinic_id", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_public_agenda_visits_clinic_created", table_name="public_agenda_visits")
    op.drop_index(op.f("ix_public_agenda_visits_clinic_id"), table_name="public_agenda_visits")
    op.drop_table("public_agenda_visits")
