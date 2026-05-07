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


def _table_exists(bind, table_name):
    result = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema = DATABASE() AND table_name = :table"
        ),
        {"table": table_name},
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


def upgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, "password_set_tokens"):
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
    for idx_expr, tbl, cols, kw in (
        (op.f("ix_password_set_tokens_id"), "password_set_tokens", ["id"], {"unique": False}),
        (op.f("ix_password_set_tokens_user_id"), "password_set_tokens", ["user_id"], {"unique": False}),
        (op.f("ix_password_set_tokens_token"), "password_set_tokens", ["token"], {"unique": True}),
    ):
        if not _index_exists(bind, tbl, idx_expr):
            op.create_index(idx_expr, tbl, cols, **kw)


def downgrade() -> None:
    bind = op.get_bind()
    for idx_expr in (
        op.f("ix_password_set_tokens_token"),
        op.f("ix_password_set_tokens_user_id"),
        op.f("ix_password_set_tokens_id"),
    ):
        if _index_exists(bind, "password_set_tokens", idx_expr):
            op.drop_index(idx_expr, table_name="password_set_tokens")
    if _table_exists(bind, "password_set_tokens"):
        op.drop_table("password_set_tokens")
