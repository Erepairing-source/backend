"""Add password_set_tokens table

Revision ID: b2c3d4e5f6a7
Revises: c5d6e7f8a9b0
Create Date: 2026-02-07

"""
from alembic import op
import sqlalchemy as sa


revision = "b2c3d4e5f6a7"
down_revision = "c5d6e7f8a9b0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "password_set_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_password_set_tokens_id"), "password_set_tokens", ["id"], unique=False)
    op.create_index(op.f("ix_password_set_tokens_user_id"), "password_set_tokens", ["user_id"], unique=False)
    op.create_index(op.f("ix_password_set_tokens_token"), "password_set_tokens", ["token"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_password_set_tokens_token"), table_name="password_set_tokens")
    op.drop_index(op.f("ix_password_set_tokens_user_id"), table_name="password_set_tokens")
    op.drop_index(op.f("ix_password_set_tokens_id"), table_name="password_set_tokens")
    op.drop_table("password_set_tokens")
