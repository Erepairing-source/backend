"""Add ticket customer/engineer workflow fields

Revision ID: d3c8a2f5d0aa
Revises: 4d7c06c1754a
Create Date: 2026-02-01 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd3c8a2f5d0aa'
down_revision = '4d7c06c1754a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    def column_exists(table_name, column_name):
        result = bind.execute(sa.text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = :table AND column_name = :column"
        ), {"table": table_name, "column": column_name})
        return result.scalar() > 0

    if not column_exists("tickets", "issue_language"):
        op.add_column('tickets', sa.Column('issue_language', sa.String(length=50), nullable=True))
    if not column_exists("tickets", "contact_preferences"):
        op.add_column('tickets', sa.Column('contact_preferences', sa.JSON(), nullable=True))
    if not column_exists("tickets", "preferred_time_slots"):
        op.add_column('tickets', sa.Column('preferred_time_slots', sa.JSON(), nullable=True))
    if not column_exists("tickets", "engineer_eta_start"):
        op.add_column('tickets', sa.Column('engineer_eta_start', sa.DateTime(timezone=True), nullable=True))
    if not column_exists("tickets", "engineer_eta_end"):
        op.add_column('tickets', sa.Column('engineer_eta_end', sa.DateTime(timezone=True), nullable=True))
    if not column_exists("tickets", "arrival_latitude"):
        op.add_column('tickets', sa.Column('arrival_latitude', sa.String(length=20), nullable=True))
    if not column_exists("tickets", "arrival_longitude"):
        op.add_column('tickets', sa.Column('arrival_longitude', sa.String(length=20), nullable=True))
    if not column_exists("tickets", "arrival_confirmed_at"):
        op.add_column('tickets', sa.Column('arrival_confirmed_at', sa.DateTime(timezone=True), nullable=True))
    if not column_exists("tickets", "customer_dispute_tags"):
        op.add_column('tickets', sa.Column('customer_dispute_tags', sa.JSON(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()

    def column_exists(table_name, column_name):
        result = bind.execute(sa.text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = :table AND column_name = :column"
        ), {"table": table_name, "column": column_name})
        return result.scalar() > 0

    if column_exists("tickets", "customer_dispute_tags"):
        op.drop_column('tickets', 'customer_dispute_tags')
    if column_exists("tickets", "arrival_confirmed_at"):
        op.drop_column('tickets', 'arrival_confirmed_at')
    if column_exists("tickets", "arrival_longitude"):
        op.drop_column('tickets', 'arrival_longitude')
    if column_exists("tickets", "arrival_latitude"):
        op.drop_column('tickets', 'arrival_latitude')
    if column_exists("tickets", "engineer_eta_end"):
        op.drop_column('tickets', 'engineer_eta_end')
    if column_exists("tickets", "engineer_eta_start"):
        op.drop_column('tickets', 'engineer_eta_start')
    if column_exists("tickets", "preferred_time_slots"):
        op.drop_column('tickets', 'preferred_time_slots')
    if column_exists("tickets", "contact_preferences"):
        op.drop_column('tickets', 'contact_preferences')
    if column_exists("tickets", "issue_language"):
        op.drop_column('tickets', 'issue_language')
