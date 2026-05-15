"""Razorpay payment endpoints (autopay setup, webhooks)."""
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status, Body
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.permissions import require_role
from app.models.user import User, UserRole
from app.services import razorpay_service
from app.services.subscription_payment_service import (
    autopay_status_payload,
    complete_autopay_setup,
    initiate_autopay_setup,
    _subscription_for_org,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/razorpay/config")
def razorpay_public_config():
    """Public Razorpay key for Checkout.js (no secret)."""
    return {
        "enabled": razorpay_service.is_razorpay_configured(),
        "key_id": settings.RAZORPAY_KEY_ID if razorpay_service.is_razorpay_configured() else None,
    }


@router.get("/razorpay/autopay-status")
def get_autopay_status(
    current_user: User = Depends(require_role([UserRole.ORGANIZATION_ADMIN])),
    db: Session = Depends(get_db),
):
    sub = _subscription_for_org(db, current_user.organization_id)
    return autopay_status_payload(sub)


@router.post("/razorpay/setup-order")
def create_setup_order(
    current_user: User = Depends(require_role([UserRole.ORGANIZATION_ADMIN])),
    db: Session = Depends(get_db),
):
    """Create ₹1 mandate order — open Razorpay Checkout (card / UPI)."""
    try:
        return initiate_autopay_setup(db, current_user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except razorpay_service.RazorpayNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.exception("setup-order failed")
        raise HTTPException(status_code=500, detail=f"Could not create payment order: {exc}")


@router.post("/razorpay/verify-setup")
def verify_setup_payment(
    payload: dict = Body(...),
    current_user: User = Depends(require_role([UserRole.ORGANIZATION_ADMIN])),
    db: Session = Depends(get_db),
):
    """Verify Razorpay Checkout success and save autopay token."""
    order_id = payload.get("razorpay_order_id")
    payment_id = payload.get("razorpay_payment_id")
    signature = payload.get("razorpay_signature")
    if not all([order_id, payment_id, signature]):
        raise HTTPException(
            status_code=400,
            detail="razorpay_order_id, razorpay_payment_id, and razorpay_signature are required",
        )
    try:
        status_data = complete_autopay_setup(
            db,
            current_user,
            razorpay_order_id=order_id,
            razorpay_payment_id=payment_id,
            razorpay_signature=signature,
        )
        return {"message": "Autopay saved successfully", "autopay": status_data}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("verify-setup failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/razorpay/webhook")
async def razorpay_webhook(request: Request, db: Session = Depends(get_db)):
    """Optional Razorpay webhook (payment.captured). Configure in Razorpay Dashboard."""
    body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")
    if not razorpay_service.verify_webhook_signature(body, signature):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")
    try:
        event = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    event_type = event.get("event", "")
    logger.info("Razorpay webhook: %s", event_type)
    return {"received": True}
