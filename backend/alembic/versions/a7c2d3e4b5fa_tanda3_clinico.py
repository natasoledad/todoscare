"""Tanda 3 clínico: vital_signs + treatment_plans + treatment_plan_items

Revision ID: a7c2d3e4b5fa
Revises: f6b1c2d3e4a9
Create Date: 2026-08-07
"""

import sqlalchemy as sa
from alembic import op

revision = "a7c2d3e4b5fa"
down_revision = "f6b1c2d3e4a9"
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
        "vital_signs",
        *_audit(),
        sa.Column("patient_id", sa.UUID(), nullable=False),
        sa.Column("professional_id", sa.UUID(), nullable=False),
        sa.Column("appointment_id", sa.UUID(), nullable=True),
        sa.Column("presion_sistolica", sa.Integer(), nullable=True),
        sa.Column("presion_diastolica", sa.Integer(), nullable=True),
        sa.Column("fc_ppm", sa.Integer(), nullable=True),
        sa.Column("fr_rpm", sa.Integer(), nullable=True),
        sa.Column("spo2", sa.Integer(), nullable=True),
        sa.Column("glicemia", sa.Integer(), nullable=True),
        sa.Column("eva", sa.Integer(), nullable=True),
        sa.Column("peso_kg", sa.Numeric(6, 2), nullable=True),
        sa.Column("talla_cm", sa.Numeric(6, 2), nullable=True),
        sa.Column("temperatura", sa.Numeric(4, 1), nullable=True),
        sa.Column("notas", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["professional_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["appointment_id"], ["appointments.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_vital_signs_clinic_id"), "vital_signs", ["clinic_id"], unique=False)
    op.create_index(op.f("ix_vital_signs_patient_id"), "vital_signs", ["patient_id"], unique=False)

    op.create_table(
        "treatment_plans",
        *_audit(),
        sa.Column("patient_id", sa.UUID(), nullable=False),
        sa.Column("professional_id", sa.UUID(), nullable=False),
        sa.Column("titulo", sa.String(length=255), nullable=False),
        sa.Column("estado", sa.String(length=20), server_default="propuesto", nullable=False),
        sa.Column("notas", sa.String(length=1000), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["professional_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_treatment_plans_clinic_id"), "treatment_plans", ["clinic_id"], unique=False)
    op.create_index(op.f("ix_treatment_plans_patient_id"), "treatment_plans", ["patient_id"], unique=False)

    op.create_table(
        "treatment_plan_items",
        *_audit(),
        sa.Column("plan_id", sa.UUID(), nullable=False),
        sa.Column("service_id", sa.UUID(), nullable=True),
        sa.Column("descripcion", sa.String(length=255), nullable=False),
        sa.Column("pieza", sa.String(length=10), nullable=True),
        sa.Column("cantidad", sa.Integer(), server_default="1", nullable=False),
        sa.Column("precio_unit", sa.Numeric(14, 2), server_default="0", nullable=False),
        sa.Column("estado", sa.String(length=20), server_default="pendiente", nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["plan_id"], ["treatment_plans.id"]),
        sa.ForeignKeyConstraint(["service_id"], ["catalog_items.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_treatment_plan_items_clinic_id"), "treatment_plan_items", ["clinic_id"], unique=False)
    op.create_index(op.f("ix_treatment_plan_items_plan_id"), "treatment_plan_items", ["plan_id"], unique=False)


def downgrade() -> None:
    op.drop_table("treatment_plan_items")
    op.drop_table("treatment_plans")
    op.drop_table("vital_signs")
