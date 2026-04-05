"""
Short-lived OTP for email address verification (signup, new user invites).
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class EmailVerificationOTP(Base):
    """One-time code to verify email ownership; expires after use or TTL."""

    __tablename__ = "email_verification_otps"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    otp_code = Column(String(10), nullable=False)
    # NULL = legacy rows (treat as email_verification). "password_reset" for forgot-password flow.
    purpose = Column(String(32), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    consumed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", backref="email_verification_otps")
