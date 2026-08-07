"""Cajas: cash_registers + cash_payments

Módulo de caja diaria por colaborador (Tanda 2). El arqueo operativo vive en
estas tablas; cada movimiento asienta además un LedgerEntry inmutable.

Revision ID: f6b1c2d3e4a9
Revises: e5a1b2c3d4f8
Create Date: 2026-08-07
"""

import sqlalchemy as sa
from alembic import op

revision = "f6b1c2d3e4a9"
down_revision = "e5a1b2c3d4f8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cash_registers",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("branch_id", sa.UUID(), nullable=True),
        sa.Column("responsable_id", sa.UUID(), nullable=False),
        sa.Column("estado", sa.String(length=20), server_default="abierta", nullable=False),
        sa.Column("abono_inicial", sa.Numeric(14, 2), server_default="0", nullable=False),
        sa.Column("fondo_fijo", sa.Numeric(14, 2), nullable=True),
        sa.Column("cerrada_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cerrada_por", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["responsable_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["cerrada_por"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_cash_registers_clinic_id"), "cash_registers", ["clinic_id"], unique=False)
    op.create_index(op.f("ix_cash_registers_responsable_id"), "cash_registers", ["responsable_id"], unique=False)

    op.create_table(
        "cash_payments",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("cash_register_id", sa.UUID(), nullable=False),
        sa.Column("patient_id", sa.UUID(), nullable=True),
        sa.Column("appointment_id", sa.UUID(), nullable=True),
        sa.Column("ledger_entry_id", sa.UUID(), nullable=True),
        sa.Column("tipo", sa.String(length=20), server_default="pago", nullable=False),
        sa.Column("medio", sa.String(length=30), nullable=False),
        sa.Column("convenio", sa.String(length=120), nullable=True),
        sa.Column("monto", sa.Numeric(14, 2), nullable=False),
        sa.Column("referencia", sa.String(length=120), nullable=True),
        sa.Column("boleta", sa.String(length=120), nullable=True),
        sa.Column("glosa", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["cash_register_id"], ["cash_registers.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["appointment_id"], ["appointments.id"]),
        sa.ForeignKeyConstraint(["ledger_entry_id"], ["ledger_entries.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_cash_payments_clinic_id"), "cash_payments", ["clinic_id"], unique=False)
    op.create_index(op.f("ix_cash_payments_cash_register_id"), "cash_payments", ["cash_register_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_cash_payments_cash_register_id"), table_name="cash_payments")
    op.drop_index(op.f("ix_cash_payments_clinic_id"), table_name="cash_payments")
    op.drop_table("cash_payments")
    op.drop_index(op.f("ix_cash_registers_responsable_id"), table_name="cash_registers")
    op.drop_index(op.f("ix_cash_registers_clinic_id"), table_name="cash_registers")
    op.drop_table("cash_registers")
