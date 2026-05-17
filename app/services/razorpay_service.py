"""Razorpay REST client (orders, customers, verify, recurring charge)."""
from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

RAZORPAY_API = "https://api.razorpay.com/v1"


class RazorpayNotConfiguredError(RuntimeError):
    pass


def is_razorpay_configured() -> bool:
    if not settings.PAYMENTS_ENABLED:
        return False
    return bool(settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET)


def _auth() -> tuple[str, str]:
    if not is_razorpay_configured():
        raise RazorpayNotConfiguredError(
            "Razorpay is not configured. Set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET in backend/.env"
        )
    return settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET


def _request(method: str, path: str, json: Optional[dict] = None) -> dict:
    url = f"{RAZORPAY_API}{path}"
    with httpx.Client(timeout=30.0) as client:
        response = client.request(method, url, auth=_auth(), json=json)
    try:
        data = response.json()
    except Exception:
        data = {"raw": response.text}
    if response.status_code >= 400:
        err = data.get("error", data) if isinstance(data, dict) else data
        raise RuntimeError(f"Razorpay API error ({response.status_code}): {err}")
    return data


def create_customer(name: str, email: str, contact: str, notes: Optional[dict] = None) -> dict:
    payload: dict[str, Any] = {
        "name": name[:120] if name else "Customer",
        "email": email,
        "contact": contact,
        "fail_existing": "0",
    }
    if notes:
        payload["notes"] = notes
    return _request("POST", "/customers", payload)


def create_order(
    amount_paise: int,
    receipt: str,
    notes: Optional[dict] = None,
    customer_id: Optional[str] = None,
) -> dict:
    payload: dict[str, Any] = {
        "amount": amount_paise,
        "currency": "INR",
        "receipt": receipt[:40],
        "payment_capture": 1,
    }
    if notes:
        payload["notes"] = notes
    if customer_id:
        payload["customer_id"] = customer_id
    return _request("POST", "/orders", payload)


def fetch_payment(payment_id: str) -> dict:
    return _request("GET", f"/payments/{payment_id}")


def verify_payment_signature(order_id: str, payment_id: str, signature: str) -> bool:
    if not settings.RAZORPAY_KEY_SECRET:
        return False
    body = f"{order_id}|{payment_id}"
    expected = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def verify_webhook_signature(body: bytes, signature: str) -> bool:
    secret = settings.RAZORPAY_WEBHOOK_SECRET or settings.RAZORPAY_KEY_SECRET
    if not secret:
        return False
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def create_recurring_payment(
    *,
    email: str,
    contact: str,
    amount_paise: int,
    order_id: str,
    customer_id: str,
    token: str,
    description: str = "eRepairing subscription",
) -> dict:
    """Charge saved card/UPI token (autopay)."""
    payload = {
        "email": email,
        "contact": contact,
        "amount": amount_paise,
        "currency": "INR",
        "order_id": order_id,
        "customer_id": customer_id,
        "token": token,
        "recurring": "1",
        "description": description[:255],
    }
    return _request("POST", "/payments/create/recurring", payload)
