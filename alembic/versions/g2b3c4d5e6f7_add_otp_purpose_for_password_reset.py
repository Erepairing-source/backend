"""Add purpose column to email_verification_otps (password reset vs email verification)

Revision ID: g2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-04-03

"""
from alembic import op
import sqlalchemy as sa


revision = "g2b3c4d5e6f7"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = [c["name"] for c in insp.get_columns("email_verification_otps")]
    if "purpose" not in cols:
        op.add_column(
            "email_verification_otps",
            sa.Column("purpose", sa.String(length=32), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = [c["name"] for c in insp.get_columns("email_verification_otps")]
    if "purpose" in cols:
        op.drop_column("email_verification_otps", "purpose")
