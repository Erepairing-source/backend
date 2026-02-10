"""Create service_policies table

Revision ID: f7e8d9c0b1a2
Revises: d3c8a2f5d0aa
Create Date: 2026-02-07

The service_policies table was never created in the initial migration.
This migration creates it with all columns (including location scope)
so that the later "add location scope" migration (8b6f3d2e4a1c) remains a no-op.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f7e8d9c0b1a2'
down_revision = 'd3c8a2f5d0aa'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'service_policies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('policy_type', sa.String(length=100), nullable=False),
        sa.Column('rules', sa.JSON(), nullable=True),
        sa.Column('product_category', sa.String(length=100), nullable=True),
        sa.Column('product_id', sa.Integer(), nullable=True),
        sa.Column('country_id', sa.Integer(), nullable=True),
        sa.Column('state_id', sa.Integer(), nullable=True),
        sa.Column('city_id', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
        sa.ForeignKeyConstraint(['country_id'], ['countries.id'], ),
        sa.ForeignKeyConstraint(['state_id'], ['states.id'], ),
        sa.ForeignKeyConstraint(['city_id'], ['cities.id'], ),
    )
    op.create_index(op.f('ix_service_policies_id'), 'service_policies', ['id'], unique=False)
    op.create_index(op.f('ix_service_policies_organization_id'), 'service_policies', ['organization_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_service_policies_organization_id'), table_name='service_policies')
    op.drop_index(op.f('ix_service_policies_id'), table_name='service_policies')
    op.drop_table('service_policies')
