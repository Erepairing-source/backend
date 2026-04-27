"""Add ticket customer contact fields

Revision ID: j4d5e6f7a8b9
Revises: h3c4d5e6f7a8
Create Date: 2026-04-27 21:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "j4d5e6f7a8b9"
down_revision = "h3c4d5e6f7a8"
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


def upgrade() -> None:
    bind = op.get_bind()
    if not _column_exists(bind, "tickets", "customer_name"):
        op.add_column("tickets", sa.Column("customer_name", sa.String(length=255), nullable=True))
    if not _column_exists(bind, "tickets", "customer_company"):
        op.add_column("tickets", sa.Column("customer_company", sa.String(length=255), nullable=True))
    if not _column_exists(bind, "tickets", "customer_phone"):
        op.add_column("tickets", sa.Column("customer_phone", sa.String(length=20), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    if _column_exists(bind, "tickets", "customer_phone"):
        op.drop_column("tickets", "customer_phone")
    if _column_exists(bind, "tickets", "customer_company"):
        op.drop_column("tickets", "customer_company")
    if _column_exists(bind, "tickets", "customer_name"):
        op.drop_column("tickets", "customer_name")
