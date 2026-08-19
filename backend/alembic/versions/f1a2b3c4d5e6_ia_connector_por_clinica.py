"""Asegura el conector 'ia_clinica' (apagado) para cada clínica existente (72)

Los conectores nacen del seed, que NO corre en producción. Sin este registro,
el panel de Administrador —que solo activa/desactiva conectores existentes— no
podría encender la IA clínica en higia.cl. Esta migración de datos, idempotente,
inserta el conector 'ia_clinica' con activo=false (apagado por defecto: el admin
lo enciende con un clic) para toda clínica que aún no lo tenga. No toca ninguna
fila existente ni ningún otro dato.

Revision ID: f1a2b3c4d5e6
Revises: e0f1a2b3c4d5
Create Date: 2026-08-19
"""

from alembic import op

revision = "f1a2b3c4d5e6"
down_revision = "e0f1a2b3c4d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO integration_configs (id, created_at, updated_at, clinic_id, tipo, activo)
        SELECT gen_random_uuid(), now(), now(), c.id, 'ia_clinica', false
        FROM clinics c
        WHERE c.deleted_at IS NULL
          AND NOT EXISTS (
            SELECT 1 FROM integration_configs ic
            WHERE ic.clinic_id = c.id AND ic.tipo = 'ia_clinica' AND ic.deleted_at IS NULL
          );
        """
    )


def downgrade() -> None:
    # Solo revierte los registros por defecto no tocados (siguen apagados); nunca
    # borra un conector que el administrador haya activado.
    op.execute(
        "DELETE FROM integration_configs WHERE tipo = 'ia_clinica' AND activo = false;"
    )
