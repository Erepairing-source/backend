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


def _column_exists(bind, table_name, column_name):
    result = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = :table AND column_name = :column"
        ),
        {"table": table_name, "column": column_name},
    )
    return result.scalar() > 0


def _index_exists(bind, table_name, index_name):
    result = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM information_schema.statistics "
            "WHERE table_schema = DATABASE() AND table_name = :table AND index_name = :idx"
        ),
        {"table": table_name, "idx": index_name},
    )
    return result.scalar() > 0


def _fk_exists(bind, constraint_name, table_name):
    result = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM information_schema.table_constraints "
            "WHERE table_schema = DATABASE() AND table_name = :table "
            "AND constraint_name = :cname AND constraint_type = 'FOREIGN KEY'"
        ),
        {"table": table_name, "cname": constraint_name},
    )
    return result.scalar() > 0


def upgrade() -> None:
    bind = op.get_bind()
    if not _column_exists(bind, "tickets", "parent_ticket_id"):
        op.add_column("tickets", sa.Column("parent_ticket_id", sa.Integer(), nullable=True))
    if not _column_exists(bind, "tickets", "follow_up_preferred_date"):
        op.add_column("tickets", sa.Column("follow_up_preferred_date", sa.DateTime(timezone=True), nullable=True))
    idx = op.f("ix_tickets_parent_ticket_id")
    if not _index_exists(bind, "tickets", idx):
        op.create_index(idx, "tickets", ["parent_ticket_id"], unique=False)
    if not _fk_exists(bind, "fk_tickets_parent_ticket_id", "tickets"):
        op.create_foreign_key("fk_tickets_parent_ticket_id", "tickets", "tickets", ["parent_ticket_id"], ["id"])


def downgrade() -> None:
    bind = op.get_bind()
    if _fk_exists(bind, "fk_tickets_parent_ticket_id", "tickets"):
        op.drop_constraint("fk_tickets_parent_ticket_id", "tickets", type_="foreignkey")
    idx = op.f("ix_tickets_parent_ticket_id")
    if _index_exists(bind, "tickets", idx):
        op.drop_index(idx, table_name="tickets")
    if _column_exists(bind, "tickets", "follow_up_preferred_date"):
        op.drop_column("tickets", "follow_up_preferred_date")
    if _column_exists(bind, "tickets", "parent_ticket_id"):
        op.drop_column("tickets", "parent_ticket_id")
