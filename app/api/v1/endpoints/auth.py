"""
Authentication endpoints
"""
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status, Body, Query
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

from app.core.database import get_db
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    get_current_user_token,
    is_pending_password,
    get_pending_password_hash,
)
from app.core.config import settings
from app.core.email import send_email_verification_otp, send_password_reset_otp
from app.core.password_set_email import create_and_send_set_password_token
from app.core.email_verification import (
    OTP_PURPOSE_PASSWORD_RESET,
    consume_password_reset_otp,
    create_email_verification_otp,
    verify_email_otp,
    consume_verification_otp_for_user,
    get_user_by_email_ci,
)
from app.models.user import User
from app.models.password_set_token import PasswordSetToken
from app.schemas.auth import Token, LoginRequest

router = APIRouter()
logger = logging.getLogger(__name__)


class SetPasswordRequest(BaseModel):
    token: str
    new_password: str
    # 6-digit code from the same email as the link (required if email not verified yet)
    verification_code: str = ""


class ResendSetPasswordRequest(BaseModel):
    email: EmailStr


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    code: str


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordWithOtpRequest(BaseModel):
    email: EmailStr
    code: str
    new_password: str


@router.post("/login", response_model=Token)
async def login(
    login_data: LoginRequest,
    db: Session = Depends(get_db)
):
    """Login endpoint"""
    try:
        # Find user (case-insensitive email — same as verify / resend OTP)
        user = get_user_by_email_ci(db, str(login_data.email))
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        if not user.password_hash:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="User password hash is missing"
            )

        if is_pending_password(user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Please set your password using the link sent to your email"
            )
        
        # Verify password with error handling
        try:
            password_valid = verify_password(login_data.password, user.password_hash)
        except Exception as e:
            import traceback
            print(f"Password verification error: {str(e)}")
            print(traceback.format_exc())
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Password verification failed: {str(e)}"
            )
        
        if not password_valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Check if user is active
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive"
            )
        
        # Create access token
        try:
            access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
            access_token = create_access_token(
                data={
                    "sub": str(user.id),
                    "email": user.email,
                    "role": user.role.value if user.role else None,
                    "organization_id": user.organization_id
                },
                expires_delta=access_token_expires
            )
        except Exception as e:
            import traceback
            print(f"Token creation error: {str(e)}")
            print(traceback.format_exc())
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Token creation failed: {str(e)}"
            )
        
        # Update last login
        try:
            from datetime import datetime
            user.last_login = datetime.utcnow()
            db.commit()
        except Exception as e:
            import traceback
            print(f"Database update error: {str(e)}")
            print(traceback.format_exc())
            db.rollback()
            # Don't fail login if last_login update fails
        
        # Return token
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user_id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value if user.role else None,
            "organization_id": user.organization_id,
            "is_verified": bool(user.is_verified),
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"Login error: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {str(e)}"
        )


@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """OAuth2 compatible token endpoint"""
    user = db.query(User).filter(User.email == form_data.username).first()
    
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "email": user.email,
            "role": user.role.value,
            "organization_id": user.organization_id
        },
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value,
        "organization_id": user.organization_id,
        "is_verified": bool(user.is_verified),
    }


@router.get("/me")
async def get_current_user(
    token_data: dict = Depends(get_current_user_token),
    db: Session = Depends(get_db)
):
    """Get current user info"""
    user_id = token_data.get("sub")
    user = db.query(User).filter(User.id == int(user_id)).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value,
        "organization_id": user.organization_id,
        "is_verified": bool(user.is_verified),
    }


@router.get("/set-password-preview")
async def set_password_preview(
    token: str = Query(..., description="Token from the set-password email link"),
    db: Session = Depends(get_db),
):
    """
    Check if the link is valid and whether the user must still enter an email verification code.
    """
    if not token or not str(token).strip():
        raise HTTPException(status_code=400, detail="Missing token")
    pt = (
        db.query(PasswordSetToken)
        .filter(
            PasswordSetToken.token == token.strip(),
            PasswordSetToken.used_at.is_(None),
        )
        .first()
    )
    if not pt:
        return {"valid": False, "requires_verification_code": True, "reason": "invalid_or_used"}
    if pt.expires_at < datetime.now(timezone.utc):
        return {"valid": False, "requires_verification_code": True, "reason": "expired"}
    user = db.query(User).filter(User.id == pt.user_id).first()
    if not user:
        return {"valid": False, "requires_verification_code": True, "reason": "invalid"}
    return {
        "valid": True,
        "requires_verification_code": not bool(user.is_verified),
    }


@router.post("/set-password")
async def set_password(
    body: SetPasswordRequest,
    db: Session = Depends(get_db)
):
    """
    Complete new-account setup: magic link token + email verification code + new password.
    Verifies OTP, sets password, marks email verified, invalidates the link (one use).
    """
    if not body.new_password or len(body.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters"
        )
    pt = (
        db.query(PasswordSetToken)
        .filter(
            PasswordSetToken.token == body.token,
            PasswordSetToken.used_at.is_(None)
        )
        .first()
    )
    if not pt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired link. Please request a new set-password email."
        )
    if pt.expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This link has expired. Please request a new set-password email."
        )
    user = db.query(User).filter(User.id == pt.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    code = (body.verification_code or "").strip()
    if not user.is_verified:
        if len(code) < 4:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Enter the verification code from your email"
            )
        ok, msg = consume_verification_otp_for_user(db, user.id, code)
        if not ok:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)

    user.password_hash = get_password_hash(body.new_password)
    pt.used_at = datetime.now(timezone.utc)
    db.commit()
    return {
        "message": "Account activated. Your email is verified and you can log in with your new password."
    }


@router.post("/resend-set-password")
async def resend_set_password(
    body: ResendSetPasswordRequest,
    db: Session = Depends(get_db)
):
    """
    Resend the set-password email for a user who has not set password yet.
    Only works for users with pending password (placeholder hash).
    """
    user = db.query(User).filter(User.email == body.email).first()
    if not user:
        # Do not reveal whether email exists
        return {"message": "If an account exists for this email, a set-password link has been sent."}
    if not is_pending_password(user.password_hash):
        return {"message": "If an account exists for this email, a set-password link has been sent."}
    sent = create_and_send_set_password_token(db, user)
    db.commit()
    if not sent:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email could not be sent. Please try again later or contact support."
        )
    return {"message": "If an account exists for this email, a set-password link has been sent."}


@router.post("/verify-email")
async def verify_email_endpoint(
    body: VerifyEmailRequest,
    db: Session = Depends(get_db),
):
    """Confirm email ownership using the 6-digit code sent after signup or user creation."""
    ok, msg = verify_email_otp(db, body.email, body.code, None)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
    return {"message": msg, "verified": True}


@router.post("/resend-verification-otp")
async def resend_verification_otp(
    body: ResendVerificationRequest,
    db: Session = Depends(get_db),
):
    """Resend email verification code (only if account exists and email is not yet verified)."""
    user = get_user_by_email_ci(db, str(body.email))
    if not user:
        logger.info(
            "resend-verification-otp: no user for normalized email (same generic response as success)"
        )
        return {
            "message": "If an account exists and needs verification, a new code has been sent to your email."
        }
    if user.is_verified:
        logger.info("resend-verification-otp: user already verified id=%s", user.id)
        return {
            "message": "If an account exists and needs verification, a new code has been sent to your email."
        }
    otp_code = create_email_verification_otp(db, user.id, ttl_minutes=15)
    db.commit()
    sent = send_email_verification_otp(
        user.email,
        otp_code,
        user.full_name,
        context="account",
    )
    if not sent:
        logger.error(
            "resend-verification-otp: SMTP send failed for user id=%s (check SMTP_* env)",
            user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email could not be sent. Please try again later or contact support.",
        )
    logger.info("resend-verification-otp: sent OK for user id=%s", user.id)
    return {
        "message": "If an account exists and needs verification, a new code has been sent to your email."
    }


@router.post("/forgot-password")
async def forgot_password(
    body: ForgotPasswordRequest,
    db: Session = Depends(get_db),
):
    """
    Send a password-reset OTP to the registered email (active accounts with a real password only).
    Same response whether or not the email exists, to avoid account enumeration.
    """
    generic = {"message": "If an account exists for that email, a reset code has been sent."}
    user = get_user_by_email_ci(db, str(body.email))
    if not user or not user.is_active:
        return generic
    if not user.password_hash or is_pending_password(user.password_hash):
        return generic

    otp_code = create_email_verification_otp(
        db, user.id, ttl_minutes=15, purpose=OTP_PURPOSE_PASSWORD_RESET
    )
    sent = send_password_reset_otp(user.email, otp_code, user.full_name)
    if not sent:
        db.rollback()
        logger.error("forgot-password: SMTP failed for user id=%s", user.id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email could not be sent. Please try again later or contact support.",
        )
    db.commit()
    logger.info("forgot-password: reset OTP sent for user id=%s", user.id)
    return generic


@router.post("/reset-password")
async def reset_password_with_otp(
    body: ResetPasswordWithOtpRequest,
    db: Session = Depends(get_db),
):
    """Set a new password using the code from forgot-password email."""
    if not body.new_password or len(body.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters",
        )
    user = get_user_by_email_ci(db, str(body.email))
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired code",
        )
    if not user.password_hash or is_pending_password(user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use the set-password link from your invite email to activate your account.",
        )

    ok, msg = consume_password_reset_otp(db, user.id, body.code)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)

    user.password_hash = get_password_hash(body.new_password)
    db.commit()
    return {
        "message": "Your password has been updated. You can sign in with your new password.",
    }


