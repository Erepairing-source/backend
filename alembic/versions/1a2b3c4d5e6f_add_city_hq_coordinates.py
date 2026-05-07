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
    if not _column_exists(bind, "cities", "hq_latitude"):
        op.add_column("cities", sa.Column("hq_latitude", sa.String(length=20), nullable=True))
    if not _column_exists(bind, "cities", "hq_longitude"):
        op.add_column("cities", sa.Column("hq_longitude", sa.String(length=20), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    if _column_exists(bind, "cities", "hq_longitude"):
        op.drop_column("cities", "hq_longitude")
    if _column_exists(bind, "cities", "hq_latitude"):
        op.drop_column("cities", "hq_latitude")
