"""add reminder_logs for contract/service email dedupe

Revision ID: f1a2b3c4d5e6
Revises: d6e7f8a9b0c1
Create Date: 2026-02-07

Linearized after email_verification_otps so `alembic upgrade head` is a single chain.
"""
from alembic import op
import sqlalchemy as sa


revision = "f1a2b3c4d5e6"
down_revision = "d6e7f8a9b0c1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "reminder_logs" in insp.get_table_names():
        # Table may already exist from app startup create_all
        return
    op.create_table(
        "reminder_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("reminder_kind", sa.String(length=32), nullable=False),
        sa.Column("ref_type", sa.String(length=32), nullable=False),
        sa.Column("ref_id", sa.Integer(), nullable=False),
        sa.Column("bucket", sa.String(length=64), nullable=False),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "reminder_kind",
            "ref_type",
            "ref_id",
            "bucket",
            name="uq_reminder_kind_ref_bucket",
        ),
    )
    op.create_index(op.f("ix_reminder_logs_reminder_kind"), "reminder_logs", ["reminder_kind"], unique=False)
    op.create_index(op.f("ix_reminder_logs_ref_type"), "reminder_logs", ["ref_type"], unique=False)
    op.create_index(op.f("ix_reminder_logs_ref_id"), "reminder_logs", ["ref_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_reminder_logs_ref_id"), table_name="reminder_logs")
    op.drop_index(op.f("ix_reminder_logs_ref_type"), table_name="reminder_logs")
    op.drop_index(op.f("ix_reminder_logs_reminder_kind"), table_name="reminder_logs")
    op.drop_table("reminder_logs")
