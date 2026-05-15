"""Add laptop and computer to products.category enum

Revision ID: l9m0n1o2p3q4
Revises: k8l9m0n1o2p3
Create Date: 2026-05-15

"""
from alembic import op
import sqlalchemy as sa


revision = "l9m0n1o2p3q4"
down_revision = "k8l9m0n1o2p3"
branch_labels = None
depends_on = None

_NEW_ENUM = (
    "ac",
    "refrigerator",
    "washing_machine",
    "tv",
    "microwave",
    "air_purifier",
    "water_purifier",
    "laptop",
    "computer",
    "other",
)

_OLD_ENUM = (
    "ac",
    "refrigerator",
    "washing_machine",
    "tv",
    "microwave",
    "air_purifier",
    "water_purifier",
    "other",
)


def _alter_mysql_enum(values: tuple[str, ...]) -> None:
    enum_sql = ",".join(f"'{v}'" for v in values)
    op.execute(
        sa.text(
            f"ALTER TABLE products MODIFY COLUMN category "
            f"ENUM({enum_sql}) NOT NULL"
        )
    )


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "mysql":
        _alter_mysql_enum(_NEW_ENUM)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "mysql":
        op.execute(
            sa.text(
                "UPDATE products SET category = 'other' "
                "WHERE category IN ('laptop', 'computer')"
            )
        )
        _alter_mysql_enum(_OLD_ENUM)
