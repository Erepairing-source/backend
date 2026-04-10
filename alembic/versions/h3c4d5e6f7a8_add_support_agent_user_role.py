"""Add support_agent to users.role enum (MySQL)

Revision ID: h3c4d5e6f7a8
Revises: g2b3c4d5e6f7
Create Date: 2026-04-11

"""
from alembic import op
import sqlalchemy as sa


revision = "h3c4d5e6f7a8"
down_revision = "g2b3c4d5e6f7"
branch_labels = None
depends_on = None

# Values must match app.models.user.UserRole (SQLAlchemy persists .value strings).
_USERROLE_VALUES = (
    "customer",
    "support_engineer",
    "support_agent",
    "city_admin",
    "state_admin",
    "country_admin",
    "organization_admin",
    "platform_admin",
    "vendor",
)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "mysql":
        return
    enum_sql = ",".join(f"'{v}'" for v in _USERROLE_VALUES)
    op.execute(
        sa.text(
            f"ALTER TABLE users MODIFY COLUMN role ENUM({enum_sql}) NOT NULL"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "mysql":
        return
    without_support = [v for v in _USERROLE_VALUES if v != "support_agent"]
    enum_sql = ",".join(f"'{v}'" for v in without_support)
    op.execute(
        sa.text(
            f"ALTER TABLE users MODIFY COLUMN role ENUM({enum_sql}) NOT NULL"
        )
    )
