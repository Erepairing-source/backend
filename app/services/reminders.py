"""
Scheduled reminder emails: contract (subscription) renewal and upcoming service visits.
Run daily via cron: python scripts/run_reminders.py
Or POST /api/v1/jobs/reminders/run (see endpoints/jobs.py).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone, time
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.email import send_contract_renewal_reminder_email, send_service_visit_reminder_email
from app.models.reminder_log import ReminderLog
from app.models.subscription import Subscription
from app.models.ticket import Ticket, TicketStatus
from app.models.user import User, UserRole

CONTRACT_REMINDER_DAYS = (30, 14, 7, 1)
REMINDER_KIND_CONTRACT = "contract_renewal"
REMINDER_KIND_SERVICE = "service_visit"
REF_SUBSCRIPTION = "subscription"
REF_TICKET = "ticket"

_OPEN_STATUSES = (
    TicketStatus.CREATED,
    TicketStatus.ASSIGNED,
    TicketStatus.IN_PROGRESS,
    TicketStatus.WAITING_PARTS,
    TicketStatus.ESCALATED,
)


def _utc_today() -> datetime.date:
    return datetime.now(timezone.utc).date()


def _reminder_already_sent(
    db: Session, kind: str, ref_type: str, ref_id: int, bucket: str
) -> bool:
    return (
        db.query(ReminderLog)
        .filter(
            ReminderLog.reminder_kind == kind,
            ReminderLog.ref_type == ref_type,
            ReminderLog.ref_id == ref_id,
            ReminderLog.bucket == bucket,
        )
        .first()
        is not None
    )


def _log_reminder(db: Session, kind: str, ref_type: str, ref_id: int, bucket: str) -> None:
    row = ReminderLog(
        reminder_kind=kind,
        ref_type=ref_type,
        ref_id=ref_id,
        bucket=bucket,
    )
    db.add(row)
    db.flush()


def _org_dashboard_url() -> str:
    return f"{settings.FRONTEND_URL.rstrip('/')}/organization-admin/dashboard"


def _ticket_portal_url(ticket_id: int) -> str:
    return f"{settings.FRONTEND_URL.rstrip('/')}/customer/ticket/{ticket_id}"


def _organization_admin_emails(db: Session, organization_id: int) -> List[User]:
    return (
        db.query(User)
        .filter(
            User.organization_id == organization_id,
            User.role == UserRole.ORGANIZATION_ADMIN,
            User.is_active == True,  # noqa: E712
        )
        .all()
    )


def run_contract_renewal_reminders(db: Session) -> Dict[str, int]:
    """
    Email org admins when subscription end_date is in 30, 14, 7, or 1 days (active only).
    """
    sent = 0
    skipped = 0
    today = _utc_today()

    subs = (
        db.query(Subscription)
        .filter(Subscription.status == "active")
        .all()
    )
    for sub in subs:
        if not sub.end_date:
            continue
        end = sub.end_date
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        end_d = end.date()
        days_left = (end_d - today).days
        if days_left not in CONTRACT_REMINDER_DAYS:
            continue
        bucket = f"{days_left}d"
        if _reminder_already_sent(db, REMINDER_KIND_CONTRACT, REF_SUBSCRIPTION, sub.id, bucket):
            skipped += 1
            continue
        org = sub.organization
        if not org:
            skipped += 1
            continue
        plan_name = sub.plan.name if sub.plan else "Your plan"
        end_display = end.strftime("%Y-%m-%d %H:%M UTC")
        admins = _organization_admin_emails(db, org.id)
        if not admins:
            skipped += 1
            continue
        any_sent = False
        for admin in admins:
            if not admin.email:
                continue
            ok = send_contract_renewal_reminder_email(
                to_email=admin.email,
                organization_name=org.name,
                plan_name=plan_name,
                end_date_display=end_display,
                days_remaining=days_left,
                dashboard_url=_org_dashboard_url(),
                full_name=admin.full_name,
            )
            if ok:
                any_sent = True
        if any_sent:
            _log_reminder(db, REMINDER_KIND_CONTRACT, REF_SUBSCRIPTION, sub.id, bucket)
            sent += 1
        else:
            skipped += 1

    return {"contract_renewal_checked": len(subs), "contract_renewal_sent": sent, "contract_renewal_skipped": skipped}


def _day_bounds_utc(d: datetime.date) -> Tuple[datetime, datetime]:
    start = datetime.combine(d, time.min, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    return start, end


def run_service_visit_reminders(db: Session) -> Dict[str, int]:
    """
    Email customers the day before:
    - follow_up_preferred_date falls on tomorrow (UTC day), or
    - engineer_eta_start falls on tomorrow (UTC day).
    """
    sent = 0
    skipped = 0
    today = _utc_today()
    tomorrow = today + timedelta(days=1)
    t_start, t_end = _day_bounds_utc(tomorrow)

    tickets = (
        db.query(Ticket)
        .filter(Ticket.status.in_(_OPEN_STATUSES))
        .filter(Ticket.customer_id.isnot(None))
        .all()
    )

    for ticket in tickets:
        customer = ticket.customer
        if not customer or not customer.email:
            skipped += 1
            continue

        # Follow-up preferred date → tomorrow
        if ticket.follow_up_preferred_date:
            fu = ticket.follow_up_preferred_date
            if fu.tzinfo is None:
                fu = fu.replace(tzinfo=timezone.utc)
            if t_start <= fu < t_end:
                bucket = f"followup_{tomorrow.isoformat()}"
                if _reminder_already_sent(db, REMINDER_KIND_SERVICE, REF_TICKET, ticket.id, bucket):
                    skipped += 1
                    continue
                detail = (
                    f"Follow-up visit is scheduled for {fu.strftime('%Y-%m-%d %H:%M UTC')}."
                )
                ok = send_service_visit_reminder_email(
                    to_email=customer.email,
                    ticket_number=ticket.ticket_number,
                    when_label="Tomorrow",
                    detail_line=detail,
                    ticket_link=_ticket_portal_url(ticket.id),
                    full_name=customer.full_name,
                )
                if ok:
                    _log_reminder(db, REMINDER_KIND_SERVICE, REF_TICKET, ticket.id, bucket)
                    sent += 1
                else:
                    skipped += 1
                continue

        # Engineer ETA start → tomorrow (assigned / in progress)
        if ticket.engineer_eta_start:
            eta = ticket.engineer_eta_start
            if eta.tzinfo is None:
                eta = eta.replace(tzinfo=timezone.utc)
            if t_start <= eta < t_end:
                bucket = f"eta_{tomorrow.isoformat()}"
                if _reminder_already_sent(db, REMINDER_KIND_SERVICE, REF_TICKET, ticket.id, bucket):
                    skipped += 1
                    continue
                end_s = ""
                if ticket.engineer_eta_end:
                    e2 = ticket.engineer_eta_end
                    if e2.tzinfo is None:
                        e2 = e2.replace(tzinfo=timezone.utc)
                    end_s = f" – {e2.strftime('%H:%M UTC')}"
                detail = f"Engineer estimated arrival window: {eta.strftime('%Y-%m-%d %H:%M UTC')}{end_s}."
                ok = send_service_visit_reminder_email(
                    to_email=customer.email,
                    ticket_number=ticket.ticket_number,
                    when_label="Tomorrow",
                    detail_line=detail,
                    ticket_link=_ticket_portal_url(ticket.id),
                    full_name=customer.full_name,
                )
                if ok:
                    _log_reminder(db, REMINDER_KIND_SERVICE, REF_TICKET, ticket.id, bucket)
                    sent += 1
                else:
                    skipped += 1

    return {
        "service_tickets_scanned": len(tickets),
        "service_reminders_sent": sent,
        "service_reminders_skipped": skipped,
    }


def run_all_reminders(db: Session) -> Dict[str, Any]:
    """
    Run contract + service reminders. Commits should be done by caller after success,
    or call commit inside this function — we commit per sub-reminder batch.
    """
    out: Dict[str, Any] = {}
    try:
        out.update(run_contract_renewal_reminders(db))
        out.update(run_service_visit_reminders(db))
        db.commit()
        out["ok"] = True
    except Exception as e:
        db.rollback()
        out["ok"] = False
        out["error"] = str(e)
        raise
    return out
