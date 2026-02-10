"""Add location scope to service policies

Revision ID: 8b6f3d2e4a1c
Revises: f7e8d9c0b1a2
Create Date: 2026-02-01 10:30:00.000000

Location columns (country_id, state_id, city_id) are now created in
f7e8d9c0b1a2_create_service_policies_table. This revision is a no-op
to preserve migration history.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8b6f3d2e4a1c'
down_revision = 'f7e8d9c0b1a2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Columns and FKs are created in f7e8d9c0b1a2_create_service_policies_table
    pass


def downgrade() -> None:
    # Dropping is handled in f7e8d9c0b1a2 downgrade
    pass
