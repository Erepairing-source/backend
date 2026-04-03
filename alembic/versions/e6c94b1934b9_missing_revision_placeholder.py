"""Placeholder migration for missing revision

Revision ID: e6c94b1934b9
Revises: 4d7c06c1754a
Create Date: 2026-02-01 13:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e6c94b1934b9'
down_revision = '4d7c06c1754a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Placeholder for missing migration in DB history.
    pass


def downgrade() -> None:
    pass
