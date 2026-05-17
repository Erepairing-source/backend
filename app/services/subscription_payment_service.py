"""Business logic: Razorpay autopay setup and recurring subscription charges."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.models.organization import Organization
from app.models.payment import PaymentTransaction
from app.models.subscription import Subscription
from app.models.user import User, UserRole
from app.services import razorpay_service
from app.services.subscription_billing import (
    advance_billing_date,
    complimentary_access_months,
    complimentary_notice,
    first_billing_date_after_setup,
    payments_enabled,
    subscription_charge_amount_inr,
    subscription_charge_amount_paise,
)

logger = logging.getLogger(__name__)


def _subscription_for_org(db: Session, organization_id: int) -> Subscription | None:
    return (
        db.query(Subscription)
        .options(joinedload(Subscription.plan))
        .filter(Subscription.organization_id == organization_id)
        .first()
    )


def autopay_status_payload(subscription: Subscription | None) -> dict:
    pay_on = payments_enabled() and razorpay_service.is_razorpay_configured()
    months = complimentary_access_months()
    if not subscription:
        return {
            "payments_enabled": pay_on,
            "complimentary_access": not pay_on,
            "configured": pay_on,
            "autopay_setup_complete": False,
            "requires_autopay_setup": False,
            "next_billing_date": None,
            "complimentary_until": None,
            "billing_interval_months": months,
            "next_charge_amount_inr": None,
            "payment_notice": None,
        }
    next_amt = subscription_charge_amount_inr(subscription) if pay_on else None
    next_bill = (
        subscription.next_billing_date.isoformat() if subscription.next_billing_date else None
    )
    return {
        "payments_enabled": pay_on,
        "complimentary_access": not pay_on,
        "configured": pay_on,
        "autopay_setup_complete": bool(subscription.autopay_setup_complete),
        "requires_autopay_setup": (
            pay_on and not subscription.autopay_setup_complete
        ),
        "status": subscription.status,
        "next_billing_date": next_bill,
        "complimentary_until": next_bill if not pay_on else None,
        "billing_interval_months": subscription.billing_interval_months or months,
        "next_charge_amount_inr": next_amt,
        "plan_name": subscription.plan.name if subscription.plan else None,
        "payment_method": subscription.payment_method,
        "autopay_method": subscription.autopay_method,
        "payment_notice": complimentary_notice(subscription),
    }


def initiate_autopay_setup(db: Session, user: User) -> dict:
    if user.role != UserRole.ORGANIZATION_ADMIN or not user.organization_id:
        raise ValueError("Only organization admins can set up autopay")
    if not razorpay_service.is_razorpay_configured():
        raise ValueError("Payment gateway is not configured on the server")

    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    if not org:
        raise ValueError("Organization not found")
    sub = _subscription_for_org(db, user.organization_id)
    if not sub:
        raise ValueError("No subscription found for this organization")

    amount_paise = int(settings.RAZORPAY_MANDATE_AMOUNT_PAISE or 100)
    receipt = f"mandate_{org.id}_{uuid.uuid4().hex[:8]}"

    customer_id = sub.razorpay_customer_id
    if not customer_id:
        customer = razorpay_service.create_customer(
            name=org.name,
            email=org.email,
            contact=org.phone,
            notes={"organization_id": str(org.id), "subscription_id": str(sub.id)},
        )
        customer_id = customer["id"]
        sub.razorpay_customer_id = customer_id
        db.flush()

    order = razorpay_service.create_order(
        amount_paise=amount_paise,
        receipt=receipt,
        customer_id=customer_id,
        notes={
            "organization_id": str(org.id),
            "subscription_id": str(sub.id),
            "purpose": "mandate_setup",
        },
    )
    sub.razorpay_last_order_id = order["id"]
    txn = PaymentTransaction(
        organization_id=org.id,
        subscription_id=sub.id,
        razorpay_order_id=order["id"],
        amount_paise=amount_paise,
        status="created",
        purpose="mandate_setup",
        meta={"receipt": receipt},
    )
    db.add(txn)
    db.commit()

    return {
        "key_id": settings.RAZORPAY_KEY_ID,
        "order_id": order["id"],
        "amount": amount_paise,
        "currency": "INR",
        "name": "eRepairing.com",
        "description": "Save card or UPI for plan autopay (₹1 authorization)",
        "prefill": {
            "name": user.full_name or org.name,
            "email": user.email,
            "contact": user.phone or org.phone,
        },
        "customer_id": customer_id,
        "notes": {
            "organization_id": org.id,
            "subscription_id": sub.id,
        },
    }


def complete_autopay_setup(
    db: Session,
    user: User,
    *,
    razorpay_order_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str,
) -> dict:
    if not razorpay_service.verify_payment_signature(
        razorpay_order_id, razorpay_payment_id, razorpay_signature
    ):
        raise ValueError("Invalid payment signature")

    sub = _subscription_for_org(db, user.organization_id)
    if not sub:
        raise ValueError("Subscription not found")

    payment = razorpay_service.fetch_payment(razorpay_payment_id)
    if payment.get("status") not in ("authorized", "captured"):
        raise ValueError(f"Payment not successful: {payment.get('status')}")

    token_id = payment.get("token_id") or payment.get("card_id")
    if not token_id:
        # Some UPI flows return token in acquirer_data
        token_id = (payment.get("acquirer_data") or {}).get("token_id")

    sub.razorpay_last_payment_id = razorpay_payment_id
    sub.razorpay_token_id = token_id
    sub.razorpay_customer_id = payment.get("customer_id") or sub.razorpay_customer_id
    sub.autopay_setup_complete = True
    sub.payment_method = "razorpay"
    sub.autopay_method = payment.get("method")
    sub.billing_interval_months = int(settings.RAZORPAY_BILLING_INTERVAL_MONTHS or 6)
    now = datetime.now(timezone.utc)
    sub.next_billing_date = first_billing_date_after_setup(now)
    if sub.status in ("pending_autopay", "trial"):
        sub.status = "active"

    txn = (
        db.query(PaymentTransaction)
        .filter(PaymentTransaction.razorpay_order_id == razorpay_order_id)
        .order_by(PaymentTransaction.id.desc())
        .first()
    )
    if txn:
        txn.razorpay_payment_id = razorpay_payment_id
        txn.status = "captured"
        txn.meta = {**(txn.meta or {}), "method": payment.get("method")}

    db.commit()
    db.refresh(sub)
    return autopay_status_payload(sub)


def charge_due_subscriptions(db: Session) -> dict:
    """Charge subscriptions where next_billing_date <= now and autopay is configured."""
    if not payments_enabled():
        return {
            "charged": 0,
            "failed": 0,
            "errors": [],
            "message": "Payments are disabled. Organizations are on complimentary access.",
        }
    now = datetime.now(timezone.utc)
    due = (
        db.query(Subscription)
        .options(joinedload(Subscription.plan))
        .filter(
            Subscription.autopay_setup_complete == True,
            Subscription.auto_renew == True,
            Subscription.razorpay_token_id.isnot(None),
            Subscription.next_billing_date.isnot(None),
            Subscription.next_billing_date <= now,
            Subscription.status.in_(["active", "trial"]),
        )
        .all()
    )
    charged = 0
    failed = 0
    errors = []

    for sub in due:
        org = db.query(Organization).filter(Organization.id == sub.organization_id).first()
        if not org:
            failed += 1
            errors.append({"subscription_id": sub.id, "error": "organization missing"})
            continue
        amount_paise = subscription_charge_amount_paise(sub)
        receipt = f"sub_{sub.id}_{uuid.uuid4().hex[:8]}"
        try:
            order = razorpay_service.create_order(
                amount_paise=amount_paise,
                receipt=receipt,
                customer_id=sub.razorpay_customer_id,
                notes={"subscription_id": str(sub.id), "purpose": "subscription_charge"},
            )
            payment = razorpay_service.create_recurring_payment(
                email=org.email,
                contact=org.phone,
                amount_paise=amount_paise,
                order_id=order["id"],
                customer_id=sub.razorpay_customer_id,
                token=sub.razorpay_token_id,
                description=f"eRepairing {sub.plan.name if sub.plan else 'plan'} subscription",
            )
            if payment.get("status") not in ("authorized", "captured"):
                raise RuntimeError(f"Charge status: {payment.get('status')}")

            sub.last_payment_date = now
            sub.razorpay_last_payment_id = payment.get("id")
            sub.razorpay_last_order_id = order["id"]
            sub.next_billing_date = advance_billing_date(
                sub.next_billing_date or now,
                sub.billing_interval_months,
            )
            txn = PaymentTransaction(
                organization_id=org.id,
                subscription_id=sub.id,
                razorpay_order_id=order["id"],
                razorpay_payment_id=payment.get("id"),
                amount_paise=amount_paise,
                status="captured",
                purpose="subscription_charge",
            )
            db.add(txn)
            db.commit()
            charged += 1
        except Exception as exc:
            db.rollback()
            failed += 1
            err_msg = str(exc)
            errors.append({"subscription_id": sub.id, "organization_id": org.id, "error": err_msg})
            logger.exception("Subscription charge failed for org %s: %s", org.id, exc)
            txn = PaymentTransaction(
                organization_id=org.id,
                subscription_id=sub.id,
                amount_paise=amount_paise,
                status="failed",
                purpose="subscription_charge",
                error_message=err_msg,
            )
            db.add(txn)
            db.commit()

    return {"due": len(due), "charged": charged, "failed": failed, "errors": errors[:50]}
