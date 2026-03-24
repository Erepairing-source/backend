"""
Tracks sent reminder emails to avoid duplicates (contract renewal windows, service visit days).
"""
from sqlalchemy import Column, Integer, String, DateTime, UniqueConstraint
from sqlalchemy.sql import func

from app.core.database import Base


class ReminderLog(Base):
    __tablename__ = "reminder_logs"
    __table_args__ = (
        UniqueConstraint(
            "reminder_kind",
            "ref_type",
            "ref_id",
            "bucket",
            name="uq_reminder_kind_ref_bucket",
        ),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    # contract_renewal | service_visit
    reminder_kind = Column(String(32), nullable=False, index=True)
    # subscription | ticket
    ref_type = Column(String(32), nullable=False, index=True)
    ref_id = Column(Integer, nullable=False, index=True)
    # e.g. 30d, 14d, followup_2026-02-10, eta_2026-02-10
    bucket = Column(String(64), nullable=False)
    sent_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
