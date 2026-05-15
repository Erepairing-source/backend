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


def first_billing_date_after_setup(start: datetime | None = None) -> datetime:
    months = int(settings.RAZORPAY_BILLING_INTERVAL_MONTHS or 6)
    base = start or datetime.now(timezone.utc)
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    return add_months(base, months)


def advance_billing_date(current: datetime, months: int | None = None) -> datetime:
    interval = months if months is not None else int(settings.RAZORPAY_BILLING_INTERVAL_MONTHS or 6)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return add_months(current, interval)
