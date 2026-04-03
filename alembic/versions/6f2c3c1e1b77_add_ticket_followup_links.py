"""Add ticket follow-up links and preferred date

Revision ID: 6f2c3c1e1b77
Revises: d3c8a2f5d0aa
Create Date: 2026-02-01 12:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6f2c3c1e1b77'
down_revision = 'd3c8a2f5d0aa'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('tickets', sa.Column('parent_ticket_id', sa.Integer(), nullable=True))
    op.add_column('tickets', sa.Column('follow_up_preferred_date', sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f('ix_tickets_parent_ticket_id'), 'tickets', ['parent_ticket_id'], unique=False)
    op.create_foreign_key('fk_tickets_parent_ticket_id', 'tickets', 'tickets', ['parent_ticket_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint('fk_tickets_parent_ticket_id', 'tickets', type_='foreignkey')
    op.drop_index(op.f('ix_tickets_parent_ticket_id'), table_name='tickets')
    op.drop_column('tickets', 'follow_up_preferred_date')
    op.drop_column('tickets', 'parent_ticket_id')
