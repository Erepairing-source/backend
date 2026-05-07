"""add ai knowledge base and chat memory tables

Revision ID: 9b3c4d5e6f70
Revises: 385c62615b2d
Create Date: 2026-02-02 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9b3c4d5e6f70"
down_revision = "385c62615b2d"
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


def upgrade():
    bind = op.get_bind()
    if not _table_exists(bind, "ai_knowledge_base"):
        op.create_table(
            "ai_knowledge_base",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("tags", sa.JSON(), nullable=True),
            sa.Column("role", sa.String(length=50), nullable=True),
            sa.Column("source", sa.String(length=255), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.text("1")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )
    if not _index_exists(bind, "ai_knowledge_base", "ix_ai_knowledge_base_role"):
        op.create_index("ix_ai_knowledge_base_role", "ai_knowledge_base", ["role"])

    if not _table_exists(bind, "chat_sessions"):
        op.create_table(
            "chat_sessions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("session_id", sa.String(length=64), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("role", sa.String(length=50), nullable=True),
            sa.Column("context_type", sa.String(length=50), nullable=True),
            sa.Column("title", sa.String(length=255), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )
    if not _index_exists(bind, "chat_sessions", "ix_chat_sessions_session_id"):
        op.create_index("ix_chat_sessions_session_id", "chat_sessions", ["session_id"], unique=True)

    if not _table_exists(bind, "chat_messages"):
        op.create_table(
            "chat_messages",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("session_id", sa.Integer(), sa.ForeignKey("chat_sessions.id"), nullable=False),
            sa.Column("sender", sa.String(length=20), nullable=False),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("extra_data", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        )
    if not _index_exists(bind, "chat_messages", "ix_chat_messages_session_id"):
        op.create_index("ix_chat_messages_session_id", "chat_messages", ["session_id"])
    if not _index_exists(bind, "chat_messages", "ix_chat_messages_created_at"):
        op.create_index("ix_chat_messages_created_at", "chat_messages", ["created_at"])


def downgrade():
    bind = op.get_bind()
    if _index_exists(bind, "chat_messages", "ix_chat_messages_created_at"):
        op.drop_index("ix_chat_messages_created_at", table_name="chat_messages")
    if _index_exists(bind, "chat_messages", "ix_chat_messages_session_id"):
        op.drop_index("ix_chat_messages_session_id", table_name="chat_messages")
    if _table_exists(bind, "chat_messages"):
        op.drop_table("chat_messages")
    if _index_exists(bind, "chat_sessions", "ix_chat_sessions_session_id"):
        op.drop_index("ix_chat_sessions_session_id", table_name="chat_sessions")
    if _table_exists(bind, "chat_sessions"):
        op.drop_table("chat_sessions")
    if _index_exists(bind, "ai_knowledge_base", "ix_ai_knowledge_base_role"):
        op.drop_index("ix_ai_knowledge_base_role", table_name="ai_knowledge_base")
    if _table_exists(bind, "ai_knowledge_base"):
        op.drop_table("ai_knowledge_base")
