"""Especialidades (tipo/activo) + perfil del profesional + motivos de atención

Punto 54 del análisis Higia vs Medilink:
  · specialties gana `tipo` (dental | medica) y `activo` (54.3 / 54.4).
  · nueva `professional_profiles`: el perfil del profesional por clínica, con
    especialidad, duración de cita, modalidad y estado activo (54.1b + base de 52/55).
  · nueva `motivos_atencion`: catálogo de motivos de consulta por clínica (54.9).

Revision ID: a5b6c7d8e9f0
Revises: a3c4d5e6f7b8
Create Date: 2026-08-18
"""

import sqlalchemy as sa
from alembic import op

revision = "a5b6c7d8e9f0"
down_revision = "a3c4d5e6f7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- specialties: tipo + activo ---
    op.add_column("specialties", sa.Column("tipo", sa.String(length=20), server_default="medica", nullable=False))
    op.add_column("specialties", sa.Column("activo", sa.Boolean(), server_default="true", nullable=False))

    # --- professional_profiles ---
    op.create_table(
        "professional_profiles",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("specialty_id", sa.UUID(), nullable=True),
        sa.Column("duracion_min", sa.Integer(), nullable=True),
        sa.Column("modalidad", sa.String(length=20), server_default="presencial", nullable=False),
        sa.Column("color", sa.String(length=9), nullable=True),
        sa.Column("activo", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["specialty_id"], ["specialties.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("clinic_id", "user_id", name="uq_profprofile_clinic_user"),
    )
    op.create_index(op.f("ix_professional_profiles_clinic_id"), "professional_profiles", ["clinic_id"], unique=False)
    op.create_index(op.f("ix_professional_profiles_user_id"), "professional_profiles", ["user_id"], unique=False)
    op.create_index(op.f("ix_professional_profiles_specialty_id"), "professional_profiles", ["specialty_id"], unique=False)

    # --- motivos_atencion ---
    op.create_table(
        "motivos_atencion",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("specialty_id", sa.UUID(), nullable=True),
        sa.Column("nombre", sa.String(length=120), nullable=False),
        sa.Column("activo", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["specialty_id"], ["specialties.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_motivos_atencion_clinic_id"), "motivos_atencion", ["clinic_id"], unique=False)
    op.create_index(op.f("ix_motivos_atencion_specialty_id"), "motivos_atencion", ["specialty_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_motivos_atencion_specialty_id"), table_name="motivos_atencion")
    op.drop_index(op.f("ix_motivos_atencion_clinic_id"), table_name="motivos_atencion")
    op.drop_table("motivos_atencion")
    op.drop_index(op.f("ix_professional_profiles_specialty_id"), table_name="professional_profiles")
    op.drop_index(op.f("ix_professional_profiles_user_id"), table_name="professional_profiles")
    op.drop_index(op.f("ix_professional_profiles_clinic_id"), table_name="professional_profiles")
    op.drop_table("professional_profiles")
    op.drop_column("specialties", "activo")
    op.drop_column("specialties", "tipo")
