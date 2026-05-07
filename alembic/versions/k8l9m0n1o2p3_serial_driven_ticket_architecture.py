"""Serial-driven ticket architecture: OTP timestamps, customer pincode

Revision ID: k8l9m0n1o2p3
Revises: j4d5e6f7a8b9
Create Date: 2026-05-07

"""
from alembic import op
import sqlalchemy as sa


revision = "k8l9m0n1o2p3"
down_revision = "j4d5e6f7a8b9"
branch_labels = None
depends_on = None


def _column_exists(bind, table_name, column_name):
    result = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = :table AND column_name = :column"
        ),
        {"table": table_name, "column": column_name},
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
    if not _column_exists(bind, "tickets", "otp_start_verified_at"):
        op.add_column("tickets", sa.Column("otp_start_verified_at", sa.DateTime(timezone=True), nullable=True))
    if not _column_exists(bind, "tickets", "otp_complete_verified_at"):
        op.add_column("tickets", sa.Column("otp_complete_verified_at", sa.DateTime(timezone=True), nullable=True))
    if not _column_exists(bind, "users", "address_pincode"):
        op.add_column("users", sa.Column("address_pincode", sa.String(length=20), nullable=True))
    if not _index_exists(bind, "users", "ix_users_address_pincode"):
        op.create_index("ix_users_address_pincode", "users", ["address_pincode"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    if _index_exists(bind, "users", "ix_users_address_pincode"):
        op.drop_index("ix_users_address_pincode", table_name="users")
    if _column_exists(bind, "users", "address_pincode"):
        op.drop_column("users", "address_pincode")
    if _column_exists(bind, "tickets", "otp_complete_verified_at"):
        op.drop_column("tickets", "otp_complete_verified_at")
    if _column_exists(bind, "tickets", "otp_start_verified_at"):
        op.drop_column("tickets", "otp_start_verified_at")
