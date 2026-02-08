"""Add location scope to service policies

Revision ID: 8b6f3d2e4a1c
Revises: d3c8a2f5d0aa
Create Date: 2026-02-01 10:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8b6f3d2e4a1c'
down_revision = 'd3c8a2f5d0aa'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('service_policies', sa.Column('country_id', sa.Integer(), nullable=True))
    op.add_column('service_policies', sa.Column('state_id', sa.Integer(), nullable=True))
    op.add_column('service_policies', sa.Column('city_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_service_policies_country_id', 'service_policies', 'countries', ['country_id'], ['id'])
    op.create_foreign_key('fk_service_policies_state_id', 'service_policies', 'states', ['state_id'], ['id'])
    op.create_foreign_key('fk_service_policies_city_id', 'service_policies', 'cities', ['city_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint('fk_service_policies_city_id', 'service_policies', type_='foreignkey')
    op.drop_constraint('fk_service_policies_state_id', 'service_policies', type_='foreignkey')
    op.drop_constraint('fk_service_policies_country_id', 'service_policies', type_='foreignkey')
    op.drop_column('service_policies', 'city_id')
    op.drop_column('service_policies', 'state_id')
    op.drop_column('service_policies', 'country_id')
