"""fase 2: cancelled appointments must free the slot

Revision ID: cbeb6e3d9d3c
Revises: 4119623e9546
Create Date: 2026-07-22 15:22:08.678735

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cbeb6e3d9d3c'
down_revision: Union[str, Sequence[str], None] = '4119623e9546'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # A cancelled appointment (estado='cancelada') must free the professional's
    # slot, or nobody could ever rebook it — cancelling only flips `estado`,
    # it doesn't soft-delete the row (history stays in "mis citas"). Widen
    # the exclusion predicate to match.
    op.execute("ALTER TABLE appointments DROP CONSTRAINT appointments_no_overlap")
    op.execute(
        "ALTER TABLE appointments ADD CONSTRAINT appointments_no_overlap "
        "EXCLUDE USING gist (professional_id WITH =, slot WITH &&) "
        "WHERE (deleted_at IS NULL AND estado <> 'cancelada')"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("ALTER TABLE appointments DROP CONSTRAINT appointments_no_overlap")
    op.execute(
        "ALTER TABLE appointments ADD CONSTRAINT appointments_no_overlap "
        "EXCLUDE USING gist (professional_id WITH =, slot WITH &&) "
        "WHERE (deleted_at IS NULL)"
    )
