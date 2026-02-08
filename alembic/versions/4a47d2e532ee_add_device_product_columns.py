"""add_device_product_columns

Revision ID: 4a47d2e532ee
Revises: 9b3c4d5e6f70
Create Date: 2026-02-03 16:17:22.935304

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = '4a47d2e532ee'
down_revision = '9b3c4d5e6f70'
branch_labels = None
depends_on = None


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    return column_name in [col["name"] for col in inspector.get_columns(table_name)]


def upgrade() -> None:
    if not _column_exists("devices", "product_id"):
        op.add_column("devices", sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=True))
    if not _column_exists("devices", "product_model_id"):
        op.add_column("devices", sa.Column("product_model_id", sa.Integer(), sa.ForeignKey("product_models.id"), nullable=True))


def downgrade() -> None:
    if _column_exists("devices", "product_model_id"):
        op.drop_column("devices", "product_model_id")
    if _column_exists("devices", "product_id"):
        op.drop_column("devices", "product_id")




