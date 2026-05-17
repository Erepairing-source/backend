"""Subscription amount and billing schedule helpers."""
from __future__ import annotations

from calendar import monthrange
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.core.config import settings

if TYPE_CHECKING:
    from app.models.subscription import Subscription


def add_months(dt: datetime, months: int) -> datetime:
    """Add calendar months in UTC."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    month = dt.month - 1 + months
    year = dt.year + month // 12
    month = month % 12 + 1
    day = min(dt.day, monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


def subscription_gst_multiplier() -> float:
    return 1.0 + float(settings.SUBSCRIPTION_GST_RATE or 0.18)


def subscription_charge_amount_inr(subscription: "Subscription") -> float:
    """Plan price + GST in INR."""
    base = float(subscription.current_price or 0)
    return round(base * subscription_gst_multiplier(), 2)


def subscription_charge_amount_paise(subscription: "Subscription") -> int:
    return int(round(subscription_charge_amount_inr(subscription) * 100))


def payments_enabled() -> bool:
    return bool(settings.PAYMENTS_ENABLED)


def complimentary_access_months() -> int:
    return int(
        settings.COMPLIMENTARY_ACCESS_MONTHS
        or settings.RAZORPAY_BILLING_INTERVAL_MONTHS
        or 6
    )


def first_billing_date_after_setup(start: datetime | None = None) -> datetime:
    months = complimentary_access_months()
    base = start or datetime.now(timezone.utc)
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    return add_months(base, months)


def advance_billing_date(current: datetime, months: int | None = None) -> datetime:
    interval = months if months is not None else complimentary_access_months()
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return add_months(current, interval)


def apply_complimentary_subscription_fields(subscription: "Subscription", start: datetime | None = None) -> None:
    """
    New or upgraded subscriptions: active access now; first billing notice after N months.
    Razorpay/autopay only when PAYMENTS_ENABLED and keys are configured.
    """
    from app.services import razorpay_service

    base = start or subscription.start_date or datetime.now(timezone.utc)
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    months = complimentary_access_months()
    subscription.billing_interval_months = months
    subscription.next_billing_date = first_billing_date_after_setup(base)
    use_payments = payments_enabled() and razorpay_service.is_razorpay_configured()
    if use_payments:
        subscription.status = "pending_autopay"
        subscription.autopay_setup_complete = False
    else:
        if subscription.status in (None, "", "pending_autopay"):
            subscription.status = "active"
        subscription.autopay_setup_complete = False


def ensure_complimentary_period(db, subscription: "Subscription") -> bool:
    """Normalize existing orgs to complimentary access when payments are disabled."""
    if payments_enabled():
        return False
    changed = False
    if subscription.status == "pending_autopay":
        subscription.status = "active"
        changed = True
    months = complimentary_access_months()
    if subscription.billing_interval_months != months:
        subscription.billing_interval_months = months
        changed = True
    if not subscription.next_billing_date:
        subscription.next_billing_date = first_billing_date_after_setup(subscription.start_date)
        changed = True
    if changed:
        db.flush()
    return changed


def complimentary_notice(subscription: "Subscription | None") -> str | None:
    if payments_enabled() or not subscription or not subscription.next_billing_date:
        return None
    dt = subscription.next_billing_date
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    label = dt.strftime("%d %b %Y")
    return (
        f"Complimentary access until {label}. "
        "We will notify your organization before billing starts. Online payment is coming soon."
    )
