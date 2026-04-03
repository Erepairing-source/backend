"""Add ticket_otps and ticket_start_approvals tables

Revision ID: a1b2c3d4e5f6
Revises: b2c3d4e5f6a7
Create Date: 2026-02-07

"""
from alembic import op
import sqlalchemy as sa


revision = "a1b2c3d4e5f6"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ticket_otps",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ticket_id", sa.Integer(), nullable=False),
        sa.Column("purpose", sa.String(20), nullable=False),
        sa.Column("otp_code", sa.String(10), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ticket_otps_id"), "ticket_otps", ["id"], unique=False)
    op.create_index(op.f("ix_ticket_otps_ticket_id"), "ticket_otps", ["ticket_id"], unique=False)
    op.create_index(op.f("ix_ticket_otps_purpose"), "ticket_otps", ["purpose"], unique=False)

    op.create_table(
        "ticket_start_approvals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ticket_id", sa.Integer(), nullable=False),
        sa.Column("requested_by_id", sa.Integer(), nullable=False),
        sa.Column("approval_level", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("approved_by_id", sa.Integer(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["approved_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ticket_start_approvals_id"), "ticket_start_approvals", ["id"], unique=False)
    op.create_index(op.f("ix_ticket_start_approvals_ticket_id"), "ticket_start_approvals", ["ticket_id"], unique=False)
    op.create_index(op.f("ix_ticket_start_approvals_status"), "ticket_start_approvals", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ticket_start_approvals_status"), table_name="ticket_start_approvals")
    op.drop_index(op.f("ix_ticket_start_approvals_ticket_id"), table_name="ticket_start_approvals")
    op.drop_index(op.f("ix_ticket_start_approvals_id"), table_name="ticket_start_approvals")
    op.drop_table("ticket_start_approvals")
    op.drop_index(op.f("ix_ticket_otps_purpose"), table_name="ticket_otps")
    op.drop_index(op.f("ix_ticket_otps_ticket_id"), table_name="ticket_otps")
    op.drop_index(op.f("ix_ticket_otps_id"), table_name="ticket_otps")
    op.drop_table("ticket_otps")
