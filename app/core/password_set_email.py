"""
Shared helper: create one-time set-password token and send email.
Used when creating any user (org admin, customer, engineer, vendor, etc.) without a password.
"""
import secrets
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from app.core.config import settings, frontend_base_url
from app.core.email import send_set_password_email
from app.core.email_verification import create_email_verification_otp
from app.models.user import User
from app.models.password_set_token import PasswordSetToken


def create_and_send_set_password_token(db: Session, user: User) -> bool:
    """
    Create a one-time set-password token for the user and send the email.
    Invalidates any existing unused tokens for this user.
    Returns True if email was sent, False if SMTP is not configured or send failed.
    """
    db.query(PasswordSetToken).filter(
        PasswordSetToken.user_id == user.id,
        PasswordSetToken.used_at.is_(None)
    ).update({"used_at": datetime.now(timezone.utc)})
    token_value = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(
        hours=getattr(settings, "SET_PASSWORD_TOKEN_EXPIRE_HOURS", 24)
    )
    pt = PasswordSetToken(user_id=user.id, token=token_value, expires_at=expires_at)
    db.add(pt)
    db.flush()
    otp_code = create_email_verification_otp(db, user.id, ttl_minutes=15)
    link = f"{frontend_base_url()}/set-password?token={token_value}"
    return send_set_password_email(user.email, link, user.full_name, email_verification_otp=otp_code)
