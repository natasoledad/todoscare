"""Recintos (salas/boxes) como recurso finito con exclusión a nivel de BD

Crea `rooms` y ata la agenda y las citas a un recinto (`room_id`). Dos EXCLUDE
USING gist impiden que dos profesionales/citas ocupen el mismo recinto a la vez
—igual que el anti doble-reserva por profesional—. Requiere btree_gist (ya
habilitado en el esquema inicial).

Revision ID: a3c4d5e6f7b8
Revises: f2b3c4d5e6a7
Create Date: 2026-08-11
"""

import sqlalchemy as sa
from alembic import op

revision = "a3c4d5e6f7b8"
down_revision = "f2b3c4d5e6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rooms",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("branch_id", sa.UUID(), nullable=True),
        sa.Column("nombre", sa.String(length=120), nullable=False),
        sa.Column("numero", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("activo", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("clinic_id", "tipo", "numero", name="uq_room_clinic_tipo_numero"),
    )
    op.create_index(op.f("ix_rooms_clinic_id"), "rooms", ["clinic_id"], unique=False)
    op.create_index(op.f("ix_rooms_branch_id"), "rooms", ["branch_id"], unique=False)

    op.add_column("availability_blocks", sa.Column("room_id", sa.UUID(), nullable=True))
    op.create_foreign_key("fk_availability_blocks_room_id", "availability_blocks", "rooms", ["room_id"], ["id"])
    op.create_index(op.f("ix_availability_blocks_room_id"), "availability_blocks", ["room_id"], unique=False)

    op.add_column("appointments", sa.Column("room_id", sa.UUID(), nullable=True))
    op.create_foreign_key("fk_appointments_room_id", "appointments", "rooms", ["room_id"], ["id"])
    op.create_index(op.f("ix_appointments_room_id"), "appointments", ["room_id"], unique=False)

    # Exclusión de solape por recinto (partial: solo cuando hay recinto asignado).
    op.execute(
        "ALTER TABLE availability_blocks ADD CONSTRAINT availability_blocks_room_no_overlap "
        "EXCLUDE USING gist (room_id WITH =, rango WITH &&) "
        "WHERE (deleted_at IS NULL AND room_id IS NOT NULL)"
    )
    op.execute(
        "ALTER TABLE appointments ADD CONSTRAINT appointments_room_no_overlap "
        "EXCLUDE USING gist (room_id WITH =, slot WITH &&) "
        "WHERE (deleted_at IS NULL AND estado <> 'cancelada' AND room_id IS NOT NULL)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE appointments DROP CONSTRAINT IF EXISTS appointments_room_no_overlap")
    op.execute("ALTER TABLE availability_blocks DROP CONSTRAINT IF EXISTS availability_blocks_room_no_overlap")
    op.drop_index(op.f("ix_appointments_room_id"), table_name="appointments")
    op.drop_column("appointments", "room_id")
    op.drop_index(op.f("ix_availability_blocks_room_id"), table_name="availability_blocks")
    op.drop_column("availability_blocks", "room_id")
    op.drop_index(op.f("ix_rooms_branch_id"), table_name="rooms")
    op.drop_index(op.f("ix_rooms_clinic_id"), table_name="rooms")
    op.drop_table("rooms")
