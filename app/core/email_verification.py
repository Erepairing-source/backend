"""
Create and verify short-lived email OTPs for account / email verification.
"""
import random
import string
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.email_verification_otp import EmailVerificationOTP
from app.models.user import User


def _generate_code(length: int = 6) -> str:
    return "".join(random.choices(string.digits, k=length))


def get_user_by_email_ci(db: Session, email: str) -> Optional[User]:
    """Match user email case-insensitively (signup may store mixed case; clients often send lowercase)."""
    n = str(email or "").strip().lower()
    if not n:
        return None
    return db.query(User).filter(func.lower(User.email) == n).first()


def create_email_verification_otp(db: Session, user_id: int, ttl_minutes: int = 15) -> str:
    """
    Invalidate unused OTPs for this user, create a new one, return plain code.
    """
    now = datetime.now(timezone.utc)
    db.query(EmailVerificationOTP).filter(
        EmailVerificationOTP.user_id == user_id,
        EmailVerificationOTP.consumed_at.is_(None),
    ).update({"consumed_at": now})
    code = _generate_code(6)
    expires = now + timedelta(minutes=ttl_minutes)
    row = EmailVerificationOTP(user_id=user_id, otp_code=code, expires_at=expires)
    db.add(row)
    db.flush()
    return code


def verify_email_otp(db: Session, email: str, code: str, user_query) -> tuple[bool, str]:
    """
    Verify OTP for the user with given email. Marks user is_verified=True on success.
    user_query: db.query(User) or pass User model class — we use email lookup from caller.
    Returns (success, message).
    """
    user = get_user_by_email_ci(db, email)
    if not user:
        return False, "Invalid email or code"
    code = (code or "").strip()
    if len(code) < 4:
        return False, "Invalid code"

    now = datetime.now(timezone.utc)
    row = (
        db.query(EmailVerificationOTP)
        .filter(
            EmailVerificationOTP.user_id == user.id,
            EmailVerificationOTP.otp_code == code,
            EmailVerificationOTP.consumed_at.is_(None),
            EmailVerificationOTP.expires_at > now,
        )
        .order_by(EmailVerificationOTP.created_at.desc())
        .first()
    )
    if not row:
        return False, "Invalid or expired verification code"

    row.consumed_at = now
    user.is_verified = True
    db.commit()
    return True, "Email verified successfully"


def consume_verification_otp_for_user(
    db: Session, user_id: int, code: str
) -> tuple[bool, str]:
    """
    Validate OTP for user_id, mark OTP consumed and user is_verified=True.
    Does not commit — caller commits with password / token updates in one transaction.
    """
    code = (code or "").strip()
    if len(code) < 4:
        return False, "Invalid verification code"

    now = datetime.now(timezone.utc)
    row = (
        db.query(EmailVerificationOTP)
        .filter(
            EmailVerificationOTP.user_id == user_id,
            EmailVerificationOTP.otp_code == code,
            EmailVerificationOTP.consumed_at.is_(None),
            EmailVerificationOTP.expires_at > now,
        )
        .order_by(EmailVerificationOTP.created_at.desc())
        .first()
    )
    if not row:
        return False, "Invalid or expired verification code"

    row.consumed_at = now
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        user.is_verified = True
    return True, "OK"
