"""
Internal / scheduled jobs (cron). Protect with REMINDER_JOB_SECRET or platform admin JWT.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.permissions import require_role
from app.models.user import User, UserRole
from app.services.reminders import run_all_reminders

router = APIRouter()


@router.post("/reminders/run")
def run_reminders_job(
    request: Request,
    db: Session = Depends(get_db),
    x_reminder_secret: Optional[str] = Header(default=None, alias="X-Reminder-Secret"),
):
    """
    Run contract renewal + service visit reminder emails (idempotent per bucket).

    **Auth (either):**
    - Header `X-Reminder-Secret` equal to `REMINDER_JOB_SECRET` from `.env` (for cron / curl)
    - `Authorization: Bearer <platform_admin_jwt>`
    """
    if settings.REMINDER_JOB_SECRET and x_reminder_secret == settings.REMINDER_JOB_SECRET:
        pass
    else:
        auth = request.headers.get("Authorization") or ""
        if not auth.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Provide X-Reminder-Secret or Bearer token (platform admin).",
            )
        token = auth[7:].strip()
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM],
            )
            user = db.query(User).filter(User.id == int(payload.get("sub"))).first()
            if not user or user.role != UserRole.PLATFORM_ADMIN:
                raise HTTPException(status_code=403, detail="Platform admin only")
        except HTTPException:
            raise
        except (JWTError, TypeError, ValueError):
            raise HTTPException(status_code=403, detail="Invalid token")

    try:
        result = run_all_reminders(db)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Reminders job failed: {e}",
        )
    return result


@router.post("/reminders/run-as-admin")
def run_reminders_as_platform_admin(
    db: Session = Depends(get_db),
    _: User = Depends(require_role([UserRole.PLATFORM_ADMIN])),
):
    """Same as /reminders/run but uses normal platform-admin session (no secret header)."""
    try:
        return run_all_reminders(db)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Reminders job failed: {e}",
        )
