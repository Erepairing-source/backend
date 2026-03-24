"""
Ticket OTP for service start and completion verification.
Customer receives OTP (email/SMS); engineer or customer enters OTP to verify.
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.core.database import Base


class TicketOTPPurpose(str, enum.Enum):
    START = "start"
    COMPLETION = "completion"


class TicketOTP(Base):
    """OTP sent to customer for start or completion verification."""
    __tablename__ = "ticket_otps"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True)
    purpose = Column(String(20), nullable=False, index=True)  # start | completion
    otp_code = Column(String(10), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    verified_at = Column(DateTime(timezone=True), nullable=True)

    ticket = relationship("Ticket", backref="otps")
