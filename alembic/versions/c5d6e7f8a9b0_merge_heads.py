"""Merge heads (device product columns + service policy / ticket branches)

Revision ID: c5d6e7f8a9b0
Revises: 4a47d2e532ee, ecf451d13f5b
Create Date: 2026-02-07

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c5d6e7f8a9b0'
down_revision = ('4a47d2e532ee', 'ecf451d13f5b')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
