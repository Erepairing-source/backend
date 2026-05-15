"""Add Razorpay autopay fields on subscriptions

Revision ID: m0n1o2p3q4r5
Revises: l9m0n1o2p3q4
Create Date: 2026-05-15

"""
from alembic import op
import sqlalchemy as sa


revision = "m0n1o2p3q4r5"
down_revision = "l9m0n1o2p3q4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("subscriptions", sa.Column("razorpay_customer_id", sa.String(64), nullable=True))
    op.add_column("subscriptions", sa.Column("razorpay_token_id", sa.String(64), nullable=True))
    op.add_column("subscriptions", sa.Column("razorpay_last_order_id", sa.String(64), nullable=True))
    op.add_column("subscriptions", sa.Column("razorpay_last_payment_id", sa.String(64), nullable=True))
    op.add_column(
        "subscriptions",
        sa.Column("autopay_setup_complete", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "subscriptions",
        sa.Column("billing_interval_months", sa.Integer(), nullable=False, server_default="6"),
    )
    op.add_column("subscriptions", sa.Column("autopay_method", sa.String(32), nullable=True))

    op.create_table(
        "payment_transactions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("subscription_id", sa.Integer(), sa.ForeignKey("subscriptions.id"), nullable=True, index=True),
        sa.Column("razorpay_order_id", sa.String(64), nullable=True, index=True),
        sa.Column("razorpay_payment_id", sa.String(64), nullable=True, index=True),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("status", sa.String(32), nullable=False, server_default="created"),
        sa.Column("purpose", sa.String(64), nullable=False, server_default="subscription"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("payment_transactions")
    op.drop_column("subscriptions", "autopay_method")
    op.drop_column("subscriptions", "billing_interval_months")
    op.drop_column("subscriptions", "autopay_setup_complete")
    op.drop_column("subscriptions", "razorpay_last_payment_id")
    op.drop_column("subscriptions", "razorpay_last_order_id")
    op.drop_column("subscriptions", "razorpay_token_id")
    op.drop_column("subscriptions", "razorpay_customer_id")
