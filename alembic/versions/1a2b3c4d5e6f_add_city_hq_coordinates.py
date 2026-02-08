"""Add city HQ coordinates

Revision ID: 1a2b3c4d5e6f
Revises: ecf451d13f5b
Create Date: 2026-02-01 14:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1a2b3c4d5e6f'
down_revision = 'ecf451d13f5b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('cities', sa.Column('hq_latitude', sa.String(length=20), nullable=True))
    op.add_column('cities', sa.Column('hq_longitude', sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column('cities', 'hq_longitude')
    op.drop_column('cities', 'hq_latitude')
