"""
City Admin endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_, text
from typing import List, Optional
from datetime import datetime, timedelta, timezone
import json

from app.core.database import get_db
from app.core.permissions import require_role
from app.models.user import User, UserRole
from app.models.ticket import Ticket, TicketStatus, TicketComment
from app.models.ticket_start_approval import TicketStartApproval
from app.models.inventory import Inventory, InventoryTransaction, Part, ReorderRequest
from app.services.ai.insights import build_sla_risk_explanation, compute_sla_risk
from app.models.device import Device
from app.models.location import City
from app.models.notification import Notification, NotificationType, NotificationChannel, NotificationStatus
from app.models.escalation import Escalation, EscalationStatus
from app.services.ai.anomaly_detection import AnomalyDetectionService
from app.core.email import send_ticket_resolved_email
from app.core.config import frontend_base_url

router = APIRouter()
anomaly_service = AnomalyDetectionService()


def _enum_or_str_lower(value) -> str:
    if value is None:
        return ""
    if hasattr(value, "value"):
        return str(value.value).strip().lower()
    return str(value).strip().lower()


def _is_completion_otp_escalation(esc: Escalation) -> bool:
    extra = esc.extra_data if isinstance(esc.extra_data, dict) else {}
    subtype = str(extra.get("subtype") or "").strip().lower()
    esc_type = _enum_or_str_lower(getattr(esc, "escalation_type", None))
    reason = str(getattr(esc, "reason", "") or "").strip().lower()
    return (
        subtype == "completion_otp_not_provided"
        or esc_type == "completion_otp_not_provided"
        or ("completion otp" in reason and "not provide" in reason)
    )


def _as_extra_dict(value) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def _days_from_time_range_city(time_range: str) -> int:
    key = (time_range or "30d").strip().lower()
    return {"7d": 7, "30d": 30, "90d": 90, "1y": 365}.get(key, 30)


@router.get("/analytics")
def get_city_admin_analytics(
    time_range: str = "30d",
    current_user: User = Depends(require_role([UserRole.CITY_ADMIN])),
    db: Session = Depends(get_db),
):
    """Time-series and distributions for city-scoped tickets."""
    if not current_user.city_id:
        raise HTTPException(status_code=400, detail="User must be assigned to a city")

    days = _days_from_time_range_city(time_range)
    since = datetime.now(timezone.utc) - timedelta(days=days)

    base = db.query(Ticket).filter(Ticket.city_id == current_user.city_id, Ticket.created_at >= since)
    if current_user.organization_id:
        base = base.filter(Ticket.organization_id == current_user.organization_id)

    daily_rows = (
        db.query(func.date(Ticket.created_at), func.count(Ticket.id))
        .filter(Ticket.city_id == current_user.city_id, Ticket.created_at >= since)
    )
    if current_user.organization_id:
        daily_rows = daily_rows.filter(Ticket.organization_id == current_user.organization_id)
    daily_rows = daily_rows.group_by(func.date(Ticket.created_at)).order_by(func.date(Ticket.created_at)).all()
    daily_trend = [{"date": str(r[0]), "tickets": int(r[1])} for r in daily_rows]

    status_rows = base.with_entities(Ticket.status, func.count(Ticket.id)).group_by(Ticket.status).all()
    status_distribution = {s.value if hasattr(s, "value") else str(s): int(c) for s, c in status_rows}

    prio_rows = base.with_entities(Ticket.priority, func.count(Ticket.id)).group_by(Ticket.priority).all()
    priority_distribution = {p.value if hasattr(p, "value") else str(p): int(c) for p, c in prio_rows}

    return {
        "period": time_range,
        "daily_trend": daily_trend,
        "status_distribution": status_distribution,
        "priority_distribution": priority_distribution,
    }


@router.get("/escalations")
def list_city_escalations(
    status_filter: Optional[str] = None,
    current_user: User = Depends(require_role([UserRole.CITY_ADMIN])),
    db: Session = Depends(get_db),
):
    """Escalations for tickets in this city (engineer OTP issues, safety, etc.)."""
    if not current_user.city_id:
        raise HTTPException(status_code=400, detail="User must be assigned to a city")

    q = (
        db.query(Escalation)
        .join(Ticket, Escalation.ticket_id == Ticket.id)
        .filter(Ticket.city_id == current_user.city_id)
    )
    if current_user.organization_id:
        q = q.filter(Ticket.organization_id == current_user.organization_id)
    if status_filter:
        try:
            st = EscalationStatus(status_filter)
            q = q.filter(Escalation.status == st)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid status filter")
    else:
        q = q.filter(Escalation.status.in_([EscalationStatus.PENDING, EscalationStatus.ACKNOWLEDGED]))

    def _enum_or_str(value):
        if value is None:
            return None
        return value.value if hasattr(value, "value") else str(value)

    try:
        rows = q.order_by(Escalation.created_at.desc()).limit(200).all()
        out = []
        for e in rows:
            t = db.query(Ticket).filter(Ticket.id == e.ticket_id).first()
            extra = _as_extra_dict(e.extra_data)
            is_otp = _is_completion_otp_escalation(e)
            status_s = _enum_or_str(e.status)
            can_force_close = bool(is_otp and str(status_s or "").strip().lower() == "acknowledged")
            out.append(
                {
                    "id": e.id,
                    "ticket_id": e.ticket_id,
                    "ticket_number": t.ticket_number if t else None,
                    "status": status_s,
                    "escalation_type": _enum_or_str(e.escalation_type),
                    "escalation_level": _enum_or_str(e.escalation_level),
                    "reason": e.reason,
                    "extra_data": extra,
                    "is_completion_otp": is_otp,
                    "can_force_close": can_force_close,
                    "created_at": e.created_at.isoformat() if e.created_at else None,
                }
            )
        return out
    except Exception:
        # Fallback for legacy enum values in production DB that don't map to current Python enums.
        sql = """
            SELECT e.id, e.ticket_id, t.ticket_number, e.status, e.escalation_type, e.escalation_level,
                   e.reason, e.extra_data, e.created_at
            FROM escalations e
            LEFT JOIN tickets t ON t.id = e.ticket_id
            WHERE t.city_id = :city_id
              AND (:org_id IS NULL OR t.organization_id = :org_id)
              AND (:status_filter IS NULL OR e.status = :status_filter)
              AND (:status_filter IS NOT NULL OR e.status IN ('pending', 'acknowledged'))
            ORDER BY e.created_at DESC
            LIMIT 200
        """
        rows = db.execute(
            text(sql),
            {
                "city_id": current_user.city_id,
                "org_id": current_user.organization_id,
                "status_filter": status_filter,
            },
        ).mappings().all()
        out = []
        for r in rows:
            extra = _as_extra_dict(r.get("extra_data"))
            created = r.get("created_at")
            status_s = r.get("status")
            esc_type_s = str(r.get("escalation_type") or "").strip().lower()
            reason_s = str(r.get("reason") or "").strip().lower()
            subtype_s = str(extra.get("subtype") or "").strip().lower()
            is_otp = (
                subtype_s == "completion_otp_not_provided"
                or esc_type_s == "completion_otp_not_provided"
                or ("completion otp" in reason_s and "not provide" in reason_s)
            )
            can_force_close = bool(is_otp and str(status_s or "").strip().lower() == "acknowledged")
            out.append(
                {
                    "id": r.get("id"),
                    "ticket_id": r.get("ticket_id"),
                    "ticket_number": r.get("ticket_number"),
                    "status": r.get("status"),
                    "escalation_type": r.get("escalation_type"),
                    "escalation_level": r.get("escalation_level"),
                    "reason": r.get("reason"),
                    "extra_data": extra,
                    "is_completion_otp": is_otp,
                    "can_force_close": can_force_close,
                    "created_at": created.isoformat() if hasattr(created, "isoformat") else None,
                }
            )
        return out


@router.post("/escalations/{escalation_id}/approve")
def approve_city_escalation(
    escalation_id: int,
    body: dict = Body(default={}),
    current_user: User = Depends(require_role([UserRole.CITY_ADMIN])),
    db: Session = Depends(get_db),
):
    """Acknowledge an escalation before force-close/resolution actions."""
    row = db.execute(
        text(
            """
            SELECT e.id, e.ticket_id, e.status, t.city_id, t.organization_id
            FROM escalations e
            JOIN tickets t ON t.id = e.ticket_id
            WHERE e.id = :escalation_id
            LIMIT 1
            """
        ),
        {"escalation_id": escalation_id},
    ).mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail="Escalation not found")

    ticket = db.query(Ticket).filter(Ticket.id == row.get("ticket_id")).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if row.get("city_id") != current_user.city_id:
        raise HTTPException(status_code=403, detail="Escalation is not in your city")
    if current_user.organization_id and row.get("organization_id") != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Escalation is outside your organization scope")

    current_status = str(row.get("status") or "").strip().lower()
    if current_status in ("resolved", "closed"):
        raise HTTPException(status_code=400, detail="Escalation is already closed")

    db.execute(
        text("UPDATE escalations SET status = :status WHERE id = :escalation_id"),
        {"status": "acknowledged", "escalation_id": escalation_id},
    )
    note = (body.get("approval_notes") or "").strip()
    db.add(
        TicketComment(
            ticket_id=ticket.id,
            user_id=current_user.id,
            comment_text=note or "City admin acknowledged escalation and started review.",
            comment_type="escalation_approval",
            extra_data={"escalation_id": escalation_id, "approved": True},
        )
    )
    db.commit()
    return {"message": "Escalation approved", "escalation_id": escalation_id, "status": "acknowledged"}


@router.post("/tickets/{ticket_id}/force-close")
def city_admin_force_close_ticket(
    ticket_id: int,
    body: dict = Body(...),
    current_user: User = Depends(require_role([UserRole.CITY_ADMIN])),
    db: Session = Depends(get_db),
):
    """Resolve or close a ticket without customer completion OTP (after engineer escalation)."""
    resolution_notes = (body.get("resolution_notes") or "").strip()
    if not resolution_notes:
        raise HTTPException(status_code=400, detail="resolution_notes is required")

    escalation_id = body.get("escalation_id")
    close_as = (body.get("close_as") or "resolved").strip().lower()

    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.city_id != current_user.city_id:
        raise HTTPException(status_code=403, detail="Ticket is not in your city")
    if current_user.organization_id and ticket.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Ticket is outside your organization scope")

    # Force-close is allowed only for OTP-unavailable escalations after city admin approval.
    esc = None
    if escalation_id:
        esc = (
            db.query(Escalation)
            .filter(Escalation.id == int(escalation_id), Escalation.ticket_id == ticket.id)
            .first()
        )
    else:
        esc = (
            db.query(Escalation)
            .filter(
                Escalation.ticket_id == ticket.id,
                Escalation.status.in_([EscalationStatus.PENDING, EscalationStatus.ACKNOWLEDGED]),
            )
            .order_by(Escalation.created_at.desc())
            .first()
        )
    if not esc:
        raise HTTPException(status_code=400, detail="No active escalation found for this ticket")

    if not _is_completion_otp_escalation(esc):
        raise HTTPException(status_code=400, detail="Force close is only allowed for completion OTP escalations")
    if _enum_or_str_lower(esc.status) != "acknowledged":
        raise HTTPException(status_code=400, detail="Escalation must be approved by city admin before force close")

    suffix = "\n\n[Closed by City Admin — completion OTP not required]"
    ticket.resolution_notes = resolution_notes + suffix
    ticket.resolved_at = datetime.now(timezone.utc)
    ticket.customer_otp_verified = False
    if close_as == "closed":
        ticket.status = TicketStatus.CLOSED
    else:
        ticket.status = TicketStatus.RESOLVED

    comment = TicketComment(
        ticket_id=ticket.id,
        user_id=current_user.id,
        comment_text="City admin force-closed ticket (OTP waived).",
        comment_type="resolution",
        extra_data={"force_close": True, "escalation_id": escalation_id},
    )
    db.add(comment)

    esc.status = EscalationStatus.RESOLVED
    esc.resolution_notes = "Resolved via city admin force-close"
    esc.resolved_by_id = current_user.id
    esc.resolved_at = datetime.now(timezone.utc)

    if ticket.customer_id:
        db.add(
            Notification(
                organization_id=ticket.organization_id,
                user_id=ticket.customer_id,
                notification_type=NotificationType.TICKET_RESOLVED,
                channel=NotificationChannel.IN_APP,
                title="Ticket closed",
                message=f"Your ticket {ticket.ticket_number} was closed by the service center.",
                ticket_id=ticket.id,
                status=NotificationStatus.PENDING,
                action_url=f"/customer/ticket/{ticket.id}",
            )
        )

    db.commit()
    db.refresh(ticket)

    cust_email, cust_name = None, None
    if ticket.customer_id:
        u = db.query(User).filter(User.id == ticket.customer_id).first()
        if u and u.email:
            cust_email, cust_name = u.email, u.full_name
    if cust_email:
        try:
            send_ticket_resolved_email(
                cust_email,
                ticket.ticket_number,
                ticket.resolution_notes or resolution_notes,
                f"{frontend_base_url()}/customer/ticket/{ticket.id}",
                cust_name,
            )
        except Exception:
            pass

    return {"message": "Ticket closed by city admin", "ticket_id": ticket.id, "status": ticket.status.value}


def _is_assignment_frozen(db: Session, ticket_id: int) -> bool:
    freeze_comment = db.query(TicketComment).filter(
        TicketComment.ticket_id == ticket_id,
        TicketComment.comment_type == "assignment_freeze"
    ).order_by(TicketComment.created_at.desc()).first()
    if not freeze_comment:
        return False
    return bool((freeze_comment.extra_data or {}).get("frozen", True))


def pick_available_engineer(db: Session, city_id: int, organization_id: Optional[int]):
    engineers = db.query(User).filter(
        User.city_id == city_id,
        User.role == UserRole.SUPPORT_ENGINEER,
        User.is_available == True
    )
    if organization_id:
        engineers = engineers.filter(User.organization_id == organization_id)
    engineers = engineers.all()
    if not engineers:
        return None

    engineer_ids = [e.id for e in engineers]
    counts = dict(
        db.query(Ticket.assigned_engineer_id, func.count(Ticket.id))
        .filter(
            Ticket.assigned_engineer_id.in_(engineer_ids),
            Ticket.status.in_([TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS])
        )
        .group_by(Ticket.assigned_engineer_id)
        .all()
    )
    return min(engineers, key=lambda e: counts.get(e.id, 0))


@router.get("/dashboard")
def get_city_dashboard(
    current_user: User = Depends(require_role([UserRole.CITY_ADMIN])),
    db: Session = Depends(get_db)
):
    """Get city-level dashboard with all data from database"""
    if not current_user.city_id:
        raise HTTPException(status_code=400, detail="User must be assigned to a city")
    
    # Get all tickets for this city from database
    tickets = db.query(Ticket).filter(Ticket.city_id == current_user.city_id).all()
    
    # Calculate statistics from database
    total_tickets = len(tickets)
    open_tickets = len([t for t in tickets if t.status in [TicketStatus.CREATED, TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS]])
    resolved_today = len([t for t in tickets if t.status == TicketStatus.RESOLVED and t.resolved_at and t.resolved_at.date() == datetime.now(timezone.utc).date()])
    at_risk = len([t for t in tickets if t.sla_breach_risk and t.sla_breach_risk > 0.7])
    
    # Get engineers in this city from database
    engineers = db.query(User).filter(
        User.city_id == current_user.city_id,
        User.role == UserRole.SUPPORT_ENGINEER,
        User.is_active == True
    ).all()
    
    # Calculate engineer workload from database
    engineer_stats = []
    for engineer in engineers:
        assigned_count = len([t for t in tickets if t.assigned_engineer_id == engineer.id and t.status != TicketStatus.RESOLVED])
        engineer_stats.append({
            "id": engineer.id,
            "name": engineer.full_name,
            "assigned_tickets": assigned_count,
            "is_available": engineer.is_available
        })
    
    # Get inventory for this city from database
    inventory_items = db.query(Inventory).filter(
        Inventory.city_id == current_user.city_id,
        Inventory.organization_id == current_user.organization_id
    ).all()
    
    low_stock_count = len([inv for inv in inventory_items if inv.is_low_stock])
    
    # Get tickets pending parts approval from database
    pending_parts_approval = [
        t for t in tickets 
        if (
            (t.status == TicketStatus.RESOLVED and t.parts_used and len(t.parts_used) > 0)
            or db.query(TicketComment).filter(
                TicketComment.ticket_id == t.id,
                TicketComment.comment_type == "parts_request"
            ).first() is not None
        )
        and not getattr(t, 'parts_approved', False)
    ]
    
    # City name from DB (cities table) for this admin's assigned city
    city_record = db.query(City).filter(City.id == current_user.city_id).first() if current_user.city_id else None
    return {
        "city": {
            "id": current_user.city_id,
            "name": city_record.name if city_record else "Unknown",
            "latitude": city_record.latitude if city_record else None,
            "longitude": city_record.longitude if city_record else None,
            "hq_latitude": city_record.hq_latitude if city_record else None,
            "hq_longitude": city_record.hq_longitude if city_record else None
        },
        "statistics": {
            "total_tickets": total_tickets,
            "open_tickets": open_tickets,
            "resolved_today": resolved_today,
            "at_risk_tickets": at_risk,
            "total_engineers": len(engineers),
            "available_engineers": len([e for e in engineers if e.is_available]),
            "low_stock_items": low_stock_count,
            "pending_parts_approval": len(pending_parts_approval)
        },
        "engineers": engineer_stats,
        "recent_tickets": [
            {
                "id": t.id,
                "ticket_number": t.ticket_number,
                "status": t.status.value,
                "priority": t.priority.value,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "assigned_engineer_id": t.assigned_engineer_id
            }
            for t in sorted(tickets, key=lambda x: x.created_at or datetime.min, reverse=True)[:10]
        ]
    }


@router.get("/tickets")
def list_city_tickets(
    status_filter: Optional[str] = None,
    priority_filter: Optional[str] = None,
    partner_id: Optional[int] = None,
    product_category: Optional[str] = None,
    oem_brand: Optional[str] = None,
    current_user: User = Depends(require_role([UserRole.CITY_ADMIN])),
    db: Session = Depends(get_db)
):
    """List all tickets in the city from database"""
    if not current_user.city_id:
        raise HTTPException(status_code=400, detail="User must be assigned to a city")
    
    query = db.query(Ticket).filter(Ticket.city_id == current_user.city_id)
    
    if status_filter:
        try:
            status_enum = TicketStatus(status_filter)
            query = query.filter(Ticket.status == status_enum)
        except ValueError:
            pass
    
    if priority_filter:
        try:
            from app.models.ticket import TicketPriority
            priority_enum = TicketPriority(priority_filter)
            query = query.filter(Ticket.priority == priority_enum)
        except ValueError:
            pass
    
    if partner_id:
        query = query.filter(Ticket.organization_id == partner_id)

    if product_category or oem_brand:
        query = query.join(Device, isouter=True)
        if product_category:
            query = query.filter(Device.product_category == product_category)
        if oem_brand:
            query = query.filter(Device.brand == oem_brand)
    
    tickets = query.options(joinedload(Ticket.device)).order_by(Ticket.created_at.desc()).all()
    
    return [
        {
            "id": t.id,
            "ticket_number": t.ticket_number,
            "status": t.status.value,
            "priority": t.priority.value,
            "issue_category": t.issue_category,
            "issue_description": t.issue_description[:100] + "..." if len(t.issue_description) > 100 else t.issue_description,
            "customer_id": t.customer_id,
            "assigned_engineer_id": t.assigned_engineer_id,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "sla_deadline": t.sla_deadline.isoformat() if t.sla_deadline else None,
            "sla_breach_risk": t.sla_breach_risk if t.sla_breach_risk is not None else compute_sla_risk(t),
            "sla_risk_reasons": build_sla_risk_explanation(t).get("reasons", []),
            "service_latitude": t.service_latitude,
            "service_longitude": t.service_longitude,
            "service_address": t.service_address,
            "product_category": t.device.product_category if t.device else None,
            "oem_brand": t.device.brand if t.device else None,
            "partner_id": t.organization_id,
            "assignment_frozen": _is_assignment_frozen(db, t.id)
        }
        for t in tickets
    ]


@router.get("/engineers")
def list_city_engineers(
    available_only: bool = False,
    current_user: User = Depends(require_role([UserRole.CITY_ADMIN])),
    db: Session = Depends(get_db)
):
    """List all engineers in the city from database"""
    if not current_user.city_id:
        raise HTTPException(status_code=400, detail="User must be assigned to a city")
    
    query = db.query(User).filter(
        User.city_id == current_user.city_id,
        User.role == UserRole.SUPPORT_ENGINEER,
        User.organization_id == current_user.organization_id
    )
    
    if available_only:
        query = query.filter(User.is_available == True)
    
    engineers = query.all()
    
    # Get ticket counts for each engineer from database
    result = []
    for engineer in engineers:
        assigned_tickets = db.query(Ticket).filter(
            Ticket.assigned_engineer_id == engineer.id,
            Ticket.status.in_([TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS])
        ).count()
        
        result.append({
            "id": engineer.id,
            "name": engineer.full_name,
            "email": engineer.email,
            "phone": engineer.phone,
            "is_available": engineer.is_available,
            "skill_level": engineer.engineer_skill_level,
            "assigned_tickets": assigned_tickets
        })
    
    return result


@router.get("/complaints")
def list_negative_complaints(
    current_user: User = Depends(require_role([UserRole.CITY_ADMIN])),
    db: Session = Depends(get_db)
):
    """List negative feedback and dispute flags for the city"""
    if not current_user.city_id:
        raise HTTPException(status_code=400, detail="User must be assigned to a city")

    tickets = db.query(Ticket).filter(
        Ticket.city_id == current_user.city_id,
        or_(
            Ticket.customer_rating <= 2,
            Ticket.sentiment_score < -0.2,
            Ticket.customer_dispute_tags != None  # noqa: E711
        )
    ).order_by(Ticket.updated_at.desc()).all()

    return [
        {
            "id": t.id,
            "ticket_number": t.ticket_number,
            "status": t.status.value,
            "customer_rating": t.customer_rating,
            "customer_feedback": t.customer_feedback,
            "customer_dispute_tags": t.customer_dispute_tags or [],
            "sentiment_score": t.sentiment_score,
            "resolved_at": t.resolved_at.isoformat() if t.resolved_at else None
        }
        for t in tickets
    ]


@router.post("/city-hq")
def update_city_hq(
    payload: dict = Body(...),
    current_user: User = Depends(require_role([UserRole.CITY_ADMIN])),
    db: Session = Depends(get_db)
):
    """Update city HQ coordinates"""
    if not current_user.city_id:
        raise HTTPException(status_code=400, detail="User must be assigned to a city")
    city = db.query(City).filter(City.id == current_user.city_id).first()
    if not city:
        raise HTTPException(status_code=404, detail="City not found")

    city.hq_latitude = payload.get("hq_latitude")
    city.hq_longitude = payload.get("hq_longitude")
    db.commit()
    return {"message": "City HQ updated"}


@router.post("/complaints/{ticket_id}/follow-up")
def create_complaint_follow_up(
    ticket_id: int,
    follow_up_data: dict = Body(...),
    current_user: User = Depends(require_role([UserRole.CITY_ADMIN])),
    db: Session = Depends(get_db)
):
    """Log follow-up action for a complaint ticket"""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.city_id != current_user.city_id:
        raise HTTPException(status_code=403, detail="Ticket not in your city")

    action_type = follow_up_data.get("action_type") or "follow_up"
    notes = follow_up_data.get("notes") or ""
    preferred_date = follow_up_data.get("preferred_date")
    goodwill = follow_up_data.get("goodwill")
    create_follow_up_ticket = bool(follow_up_data.get("create_follow_up_ticket"))
    engineer_id = follow_up_data.get("engineer_id")
    if engineer_id is not None:
        try:
            engineer_id = int(engineer_id)
        except (TypeError, ValueError):
            engineer_id = None
    follow_up_preferred_dt = None
    if preferred_date:
        try:
            follow_up_preferred_dt = datetime.fromisoformat(preferred_date.replace('Z', '+00:00'))
        except Exception:
            follow_up_preferred_dt = None

    assigned_engineer = None
    if engineer_id:
        assigned_engineer = db.query(User).filter(
            User.id == engineer_id,
            User.city_id == current_user.city_id,
            User.role == UserRole.SUPPORT_ENGINEER
        ).first()
        if not assigned_engineer:
            raise HTTPException(status_code=404, detail="Engineer not found in your city")
    elif create_follow_up_ticket:
        assigned_engineer = pick_available_engineer(db, ticket.city_id, ticket.organization_id)

    comment = TicketComment(
        ticket_id=ticket.id,
        user_id=current_user.id,
        comment_text=f"Follow-up action: {action_type}. Notes: {notes}",
        comment_type="follow_up",
        extra_data={
            "action_type": action_type,
            "preferred_date": preferred_date,
            "goodwill": goodwill,
            "create_follow_up_ticket": create_follow_up_ticket
        }
    )
    db.add(comment)

    follow_up_ticket_id = None
    if create_follow_up_ticket:
        from app.models.ticket import TicketPriority
        follow_up_priority = ticket.priority
        if ticket.sla_breach_risk and ticket.sla_breach_risk > 0.7:
            follow_up_priority = TicketPriority.URGENT
        new_ticket_number = f"TKT-{datetime.utcnow().strftime('%Y%m%d')}-{db.query(Ticket).count() + 1:06d}"
        follow_up_ticket = Ticket(
            ticket_number=new_ticket_number,
            organization_id=ticket.organization_id,
            customer_id=ticket.customer_id,
            device_id=ticket.device_id,
            created_by_id=current_user.id,
            parent_ticket_id=ticket.id,
            issue_description=f"Follow-up visit for ticket {ticket.ticket_number}. {notes}".strip(),
            issue_photos=ticket.issue_photos or [],
            service_address=ticket.service_address,
            service_latitude=ticket.service_latitude,
            service_longitude=ticket.service_longitude,
            priority=follow_up_priority,
            issue_category=ticket.issue_category,
            status=TicketStatus.ASSIGNED if assigned_engineer else TicketStatus.CREATED,
            assigned_engineer_id=assigned_engineer.id if assigned_engineer else None,
            assigned_by_id=current_user.id if assigned_engineer else None,
            assigned_at=datetime.now(timezone.utc) if assigned_engineer else None,
            city_id=ticket.city_id,
            state_id=ticket.state_id,
            country_id=ticket.country_id,
            follow_up_preferred_date=follow_up_preferred_dt
        )
        db.add(follow_up_ticket)
        db.flush()
        follow_up_ticket_id = follow_up_ticket.id

        if ticket.customer_id:
            channels = [NotificationChannel.IN_APP]
            if ticket.contact_preferences:
                if "sms" in ticket.contact_preferences:
                    channels.append(NotificationChannel.SMS)
                if "whatsapp" in ticket.contact_preferences:
                    channels.append(NotificationChannel.WHATSAPP)
            for channel in channels:
                notification = Notification(
                    organization_id=ticket.organization_id,
                    user_id=ticket.customer_id,
                    notification_type=NotificationType.TICKET_UPDATED,
                    channel=channel,
                    title="Follow-up visit scheduled",
                    message=f"A follow-up visit was scheduled for ticket {ticket.ticket_number}.",
                    ticket_id=follow_up_ticket_id,
                    status=NotificationStatus.PENDING,
                    action_url=f"/customer/ticket/{follow_up_ticket_id}"
                )
                db.add(notification)
        if assigned_engineer:
            notification = Notification(
                organization_id=ticket.organization_id,
                user_id=assigned_engineer.id,
                notification_type=NotificationType.TICKET_ASSIGNED,
                channel=NotificationChannel.IN_APP,
                title="New follow-up ticket assigned",
                message=f"Follow-up ticket {new_ticket_number} has been assigned to you.",
                ticket_id=follow_up_ticket_id,
                status=NotificationStatus.PENDING,
                action_url=f"/engineer/ticket/{follow_up_ticket_id}"
            )
            db.add(notification)

    db.commit()

    return {"message": "Follow-up action logged", "follow_up_ticket_id": follow_up_ticket_id}


@router.get("/tickets/pending-start-approvals")
def get_pending_start_approvals(
    current_user: User = Depends(require_role([UserRole.CITY_ADMIN])),
    db: Session = Depends(get_db)
):
    """Get tickets in this city with pending start approval (engineer accepted, waiting for city admin to approve start)."""
    if not current_user.city_id:
        raise HTTPException(status_code=400, detail="User must be assigned to a city")
    pending = (
        db.query(TicketStartApproval)
        .options(joinedload(TicketStartApproval.ticket), joinedload(TicketStartApproval.requested_by))
        .join(Ticket, Ticket.id == TicketStartApproval.ticket_id)
        .filter(
            Ticket.city_id == current_user.city_id,
            TicketStartApproval.status == "pending",
        )
        .order_by(TicketStartApproval.created_at.desc())
        .all()
    )
    out = []
    for appr in pending:
        t = appr.ticket
        out.append({
            "approval_id": appr.id,
            "ticket_id": t.id,
            "ticket_number": t.ticket_number,
            "requested_by_id": appr.requested_by_id,
            "requested_at": appr.created_at.isoformat() if appr.created_at else None,
            "engineer_name": appr.requested_by.full_name if appr.requested_by else None,
        })
    return out


@router.get("/tickets/pending-parts-approval")
def get_pending_parts_approval(
    current_user: User = Depends(require_role([UserRole.CITY_ADMIN])),
    db: Session = Depends(get_db)
):
    """Get tickets with parts usage pending approval from database"""
    if not current_user.city_id:
        raise HTTPException(status_code=400, detail="User must be assigned to a city")
    
    # Get tickets with parts usage or parts requests that need approval
    tickets = db.query(Ticket).filter(
        Ticket.city_id == current_user.city_id
    ).all()
    
    pending_tickets = []
    for ticket in tickets:
        approval_comment = (
            db.query(TicketComment)
            .filter(
                TicketComment.ticket_id == ticket.id,
                TicketComment.comment_type == "parts_approval",
            )
            .first()
        )
        if approval_comment:
            continue

        parts_request_comment = (
            db.query(TicketComment)
            .filter(
                TicketComment.ticket_id == ticket.id,
                TicketComment.comment_type == "parts_request",
            )
            .order_by(TicketComment.created_at.desc())
            .first()
        )

        request_authorized = False
        if parts_request_comment:
            request_authorized = bool(
                db.query(TicketComment)
                .filter(
                    TicketComment.ticket_id == ticket.id,
                    TicketComment.comment_type == "parts_request_approved",
                    TicketComment.created_at > parts_request_comment.created_at,
                )
                .first()
            )

        post_resolution = bool(ticket.parts_used and len(ticket.parts_used) > 0)
        pre_request = bool(parts_request_comment and not request_authorized)

        if post_resolution:
            request_type = "post_resolution"
            requested_parts = list(ticket.parts_used)
        elif pre_request:
            request_type = "pre_approval"
            requested_parts = (parts_request_comment.extra_data or {}).get("parts", []) or []
        else:
            continue

        if not requested_parts:
            continue

        parts_details = []
        for part_usage in requested_parts:
            part_id = part_usage.get("part_id")
            quantity = part_usage.get("quantity", 1)
            if part_id:
                part = db.query(Part).filter(Part.id == part_id).first()
                if part:
                    inventory = db.query(Inventory).filter(
                        Inventory.part_id == part_id,
                        Inventory.city_id == current_user.city_id,
                        Inventory.organization_id == current_user.organization_id,
                    ).first()

                    parts_details.append(
                        {
                            "part_id": part_id,
                            "part_name": part.name,
                            "sku": part.sku,
                            "quantity": quantity,
                            "available_stock": inventory.current_stock if inventory else 0,
                        }
                    )

        pending_tickets.append(
            {
                "ticket_id": ticket.id,
                "ticket_number": ticket.ticket_number,
                "ticket_status": ticket.status.value if ticket.status else None,
                "engineer_id": ticket.assigned_engineer_id,
                "engineer_name": ticket.assigned_engineer.full_name if ticket.assigned_engineer else "Unknown",
                "resolved_at": ticket.resolved_at.isoformat() if ticket.resolved_at else None,
                "request_type": request_type,
                "parts": parts_details,
            }
        )

    return pending_tickets


@router.post("/tickets/{ticket_id}/approve-parts")
def approve_parts_usage(
    ticket_id: int,
    approval_data: dict = Body(...),
    current_user: User = Depends(require_role([UserRole.CITY_ADMIN])),
    db: Session = Depends(get_db)
):
    """Approve parts usage and deduct inventory from database"""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    if ticket.city_id != current_user.city_id:
        raise HTTPException(status_code=403, detail="Ticket not in your city")
    
    if ticket.status != TicketStatus.RESOLVED:
        raise HTTPException(status_code=400, detail="Ticket must be resolved to approve parts")
    
    if not ticket.parts_used or len(ticket.parts_used) == 0:
        raise HTTPException(status_code=400, detail="No parts used in this ticket")
    
    # Check if already approved
    existing_approval = db.query(TicketComment).filter(
        TicketComment.ticket_id == ticket.id,
        TicketComment.comment_type == "parts_approval"
    ).first()
    
    if existing_approval:
        raise HTTPException(status_code=400, detail="Parts already approved for this ticket")
    
    # Approve and deduct inventory from database
    approved_parts = []
    rejected_parts = []
    
    for part_usage in ticket.parts_used:
        part_id = part_usage.get('part_id')
        quantity = part_usage.get('quantity', 1)
        
        if not part_id:
            continue
        
        # Get inventory from database
        inventory = db.query(Inventory).filter(
            Inventory.part_id == part_id,
            Inventory.city_id == current_user.city_id,
            Inventory.organization_id == current_user.organization_id
        ).first()
        
        if not inventory:
            rejected_parts.append({
                "part_id": part_id,
                "reason": "Inventory not found for this part in city"
            })
            continue
        
        # Check if sufficient stock
        if inventory.current_stock < quantity:
            rejected_parts.append({
                "part_id": part_id,
                "reason": f"Insufficient stock. Available: {inventory.current_stock}, Required: {quantity}"
            })
            continue
        
        # Deduct inventory
        previous_stock = inventory.current_stock
        inventory.current_stock -= quantity
        
        # Update low stock status
        inventory.is_low_stock = inventory.current_stock <= inventory.min_threshold
        
        # Create transaction log
        transaction = InventoryTransaction(
            part_id=part_id,
            inventory_id=inventory.id,
            ticket_id=ticket.id,
            transaction_type="out",
            quantity=quantity,
            previous_stock=previous_stock,
            new_stock=inventory.current_stock,
            performed_by_id=current_user.id,
            notes=f"Parts approved and deducted for ticket {ticket.ticket_number}"
        )
        db.add(transaction)
        
        approved_parts.append({
            "part_id": part_id,
            "quantity": quantity,
            "previous_stock": previous_stock,
            "new_stock": inventory.current_stock
        })
    
    # Create approval comment
    approval_comment = TicketComment(
        ticket_id=ticket.id,
        user_id=current_user.id,
        comment_text=f"Parts usage approved by City Admin. Approved: {len(approved_parts)}, Rejected: {len(rejected_parts)}",
        comment_type="parts_approval",
        extra_data={
            "approved_parts": approved_parts,
            "rejected_parts": rejected_parts,
            "approved_by": current_user.id
        }
    )
    db.add(approval_comment)
    
    db.commit()
    
    return {
        "message": "Parts approval processed",
        "approved": approved_parts,
        "rejected": rejected_parts
    }


@router.post("/tickets/{ticket_id}/approve-parts-request")
def approve_parts_request(
    ticket_id: int,
    current_user: User = Depends(require_role([UserRole.CITY_ADMIN])),
    db: Session = Depends(get_db),
):
    """
    Authorize an engineer's **pre-job** parts request (POST /tickets/.../parts/request).
    Does not deduct inventory — that happens on POST .../approve-parts after the ticket is
    resolved with parts_used.
    """
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.city_id != current_user.city_id:
        raise HTTPException(status_code=403, detail="Ticket not in your city")

    req = (
        db.query(TicketComment)
        .filter(
            TicketComment.ticket_id == ticket.id,
            TicketComment.comment_type == "parts_request",
        )
        .order_by(TicketComment.created_at.desc())
        .first()
    )
    if not req:
        raise HTTPException(
            status_code=400,
            detail="No engineer parts request on this ticket. Use “Review & approve stock” after the ticket is resolved.",
        )

    already = (
        db.query(TicketComment)
        .filter(
            TicketComment.ticket_id == ticket.id,
            TicketComment.comment_type == "parts_request_approved",
            TicketComment.created_at > req.created_at,
        )
        .first()
    )
    if already:
        raise HTTPException(status_code=400, detail="This parts request was already authorized")

    db.add(
        TicketComment(
            ticket_id=ticket.id,
            user_id=current_user.id,
            comment_text=(
                "City admin authorized the engineer's parts request. "
                "Stock is deducted after the job is completed and final parts usage is approved."
            ),
            comment_type="parts_request_approved",
            extra_data={"approved_by": current_user.id},
        )
    )
    if ticket.status == TicketStatus.WAITING_PARTS:
        ticket.status = TicketStatus.IN_PROGRESS

    db.commit()
    return {
        "message": (
            "Parts request authorized. The engineer can continue; "
            "city inventory is reduced only after resolution and “Approve parts usage”."
        )
    }


@router.post("/tickets/{ticket_id}/reject-parts")
def reject_parts_usage(
    ticket_id: int,
    rejection_data: dict = Body(...),
    current_user: User = Depends(require_role([UserRole.CITY_ADMIN])),
    db: Session = Depends(get_db)
):
    """Reject parts usage with reason"""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    if ticket.city_id != current_user.city_id:
        raise HTTPException(status_code=403, detail="Ticket not in your city")
    
    rejection_reason = rejection_data.get("reason", "Parts usage rejected by City Admin")
    
    # Create rejection comment
    rejection_comment = TicketComment(
        ticket_id=ticket.id,
        user_id=current_user.id,
        comment_text=f"Parts usage rejected. Reason: {rejection_reason}",
        comment_type="parts_rejection",
        extra_data={
            "rejection_reason": rejection_reason,
            "rejected_by": current_user.id
        }
    )
    db.add(rejection_comment)
    
    db.commit()
    
    return {"message": "Parts usage rejected", "reason": rejection_reason}


@router.get("/inventory")
def get_city_inventory(
    low_stock_only: bool = False,
    slow_moving_days: int = 30,
    ageing_only: bool = False,
    current_user: User = Depends(require_role([UserRole.CITY_ADMIN])),
    db: Session = Depends(get_db)
):
    """Get inventory for the city from database"""
    if not current_user.city_id:
        raise HTTPException(status_code=400, detail="User must be assigned to a city")
    
    query = db.query(Inventory).filter(
        Inventory.city_id == current_user.city_id,
        Inventory.organization_id == current_user.organization_id
    )
    
    if low_stock_only:
        query = query.filter(Inventory.is_low_stock == True)
    
    inventory_items = query.options(joinedload(Inventory.part)).all()
    inventory_ids = [inv.id for inv in inventory_items]
    last_moves = {}
    if inventory_ids:
        last_moves = dict(
            db.query(InventoryTransaction.inventory_id, func.max(InventoryTransaction.created_at))
            .filter(InventoryTransaction.inventory_id.in_(inventory_ids))
            .group_by(InventoryTransaction.inventory_id)
            .all()
        )
    now = datetime.now(timezone.utc)
    
    # Helper function to ensure timezone-aware datetime
    def ensure_timezone_aware(dt):
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    
    result = [
        {
            "id": inv.id,
            "part_id": inv.part_id,
            "part_name": inv.part.name,
            "sku": inv.part.sku,
            "current_stock": inv.current_stock,
            "min_threshold": inv.min_threshold,
            "max_threshold": inv.max_threshold,
            "is_low_stock": inv.is_low_stock,
            "reserved_stock": inv.reserved_stock,
            "last_restocked_at": inv.last_restocked_at.isoformat() if inv.last_restocked_at else None,
            "last_moved_at": last_moves.get(inv.id).isoformat() if last_moves.get(inv.id) else None,
            "age_days": (now - ensure_timezone_aware(last_moves.get(inv.id))).days if last_moves.get(inv.id) else None,
            "slow_moving": (
                (now - ensure_timezone_aware(last_moves.get(inv.id))).days >= slow_moving_days
                if last_moves.get(inv.id) and inv.current_stock > 0
                else False
            )
        }
        for inv in inventory_items
    ]
    if ageing_only:
        result = [item for item in result if item.get("slow_moving")]
    return result


@router.post("/inventory/{inventory_id}/thresholds")
def update_inventory_thresholds(
    inventory_id: int,
    payload: dict = Body(...),
    current_user: User = Depends(require_role([UserRole.CITY_ADMIN])),
    db: Session = Depends(get_db)
):
    """Update min/max safety stock thresholds for a city inventory item"""
    inventory = db.query(Inventory).filter(
        Inventory.id == inventory_id,
        Inventory.city_id == current_user.city_id,
        Inventory.organization_id == current_user.organization_id
    ).first()
    if not inventory:
        raise HTTPException(status_code=404, detail="Inventory item not found")

    min_threshold = payload.get("min_threshold")
    max_threshold = payload.get("max_threshold")
    if min_threshold is None:
        raise HTTPException(status_code=400, detail="min_threshold is required")
    try:
        min_threshold = int(min_threshold)
        if max_threshold in ("", None):
            max_threshold = None
        else:
            max_threshold = int(max_threshold)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid threshold values")
    if max_threshold is not None and max_threshold < min_threshold:
        raise HTTPException(status_code=400, detail="max_threshold must be >= min_threshold")

    inventory.min_threshold = min_threshold
    inventory.max_threshold = max_threshold
    inventory.is_low_stock = inventory.current_stock <= inventory.min_threshold

    transaction = InventoryTransaction(
        part_id=inventory.part_id,
        inventory_id=inventory.id,
        transaction_type="threshold_update",
        quantity=0,
        previous_stock=inventory.current_stock,
        new_stock=inventory.current_stock,
        performed_by_id=current_user.id,
        notes=f"Thresholds updated to min={min_threshold}, max={max_threshold}"
    )
    db.add(transaction)
    db.commit()
    return {"message": "Thresholds updated"}


@router.get("/inventory/reorder-requests")
def list_reorder_requests(
    status_filter: Optional[str] = None,
    current_user: User = Depends(require_role([UserRole.CITY_ADMIN])),
    db: Session = Depends(get_db)
):
    """List reorder requests for the city inventory"""
    query = db.query(ReorderRequest).join(Inventory, Inventory.id == ReorderRequest.inventory_id).filter(
        Inventory.city_id == current_user.city_id,
        ReorderRequest.organization_id == current_user.organization_id
    )
    if status_filter:
        query = query.filter(ReorderRequest.status == status_filter)
    requests = query.order_by(ReorderRequest.created_at.desc()).all()
    return [
        {
            "id": r.id,
            "part_id": r.part_id,
            "part_name": r.part.name if r.part else None,
            "inventory_id": r.inventory_id,
            "requested_quantity": r.requested_quantity,
            "current_stock": r.current_stock,
            "min_threshold": r.min_threshold,
            "status": r.status,
            "requested_by_id": r.requested_by_id,
            "approved_by_id": r.approved_by_id,
            "approved_at": r.approved_at.isoformat() if r.approved_at else None,
            "created_at": r.created_at.isoformat() if r.created_at else None
        }
        for r in requests
    ]


@router.post("/inventory/reorder-requests")
def create_reorder_request(
    payload: dict = Body(...),
    current_user: User = Depends(require_role([UserRole.CITY_ADMIN])),
    db: Session = Depends(get_db)
):
    """Create a reorder request for a city inventory item"""
    inventory_id = payload.get("inventory_id")
    requested_quantity = payload.get("requested_quantity")
    if not inventory_id or not requested_quantity:
        raise HTTPException(status_code=400, detail="inventory_id and requested_quantity are required")
    try:
        inventory_id = int(inventory_id)
        requested_quantity = int(requested_quantity)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid requested_quantity")

    inventory = db.query(Inventory).filter(
        Inventory.id == inventory_id,
        Inventory.city_id == current_user.city_id,
        Inventory.organization_id == current_user.organization_id
    ).first()
    if not inventory:
        raise HTTPException(status_code=404, detail="Inventory item not found")

    existing = db.query(ReorderRequest).filter(
        ReorderRequest.inventory_id == inventory_id,
        ReorderRequest.status == "pending"
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Pending reorder request already exists")

    request = ReorderRequest(
        part_id=inventory.part_id,
        inventory_id=inventory.id,
        organization_id=inventory.organization_id,
        requested_quantity=requested_quantity,
        current_stock=inventory.current_stock,
        min_threshold=inventory.min_threshold,
        requested_by_id=current_user.id,
        status="pending"
    )
    db.add(request)

    for admin in db.query(User).filter(
        User.role == UserRole.STATE_ADMIN,
        User.state_id == inventory.state_id,
        User.organization_id == inventory.organization_id
    ).all():
        db.add(Notification(
            organization_id=inventory.organization_id,
            user_id=admin.id,
            notification_type=NotificationType.INVENTORY_LOW,
            channel=NotificationChannel.IN_APP,
            title="Restock request submitted",
            message=f"Restock requested for {inventory.part.name} (qty {requested_quantity}).",
            status=NotificationStatus.PENDING
        ))

    db.commit()
    return {"message": "Reorder request created"}


@router.post("/inventory/reorder-requests/{request_id}/approve")
def approve_reorder_request(
    request_id: int,
    current_user: User = Depends(require_role([UserRole.CITY_ADMIN])),
    db: Session = Depends(get_db)
):
    """Approve a reorder request"""
    request = db.query(ReorderRequest).filter(ReorderRequest.id == request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Reorder request not found")
    if request.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    if request.status != "pending":
        raise HTTPException(status_code=400, detail="Request already processed")

    request.status = "approved"
    request.approved_by_id = current_user.id
    request.approved_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": "Reorder request approved"}


@router.post("/inventory/reorder-requests/{request_id}/reject")
def reject_reorder_request(
    request_id: int,
    payload: dict = Body(default={}),
    current_user: User = Depends(require_role([UserRole.CITY_ADMIN])),
    db: Session = Depends(get_db)
):
    """Reject a reorder request"""
    request = db.query(ReorderRequest).filter(ReorderRequest.id == request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Reorder request not found")
    if request.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    if request.status != "pending":
        raise HTTPException(status_code=400, detail="Request already processed")

    request.status = "rejected"
    request.approved_by_id = current_user.id
    request.approved_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": "Reorder request rejected"}


@router.post("/inventory/restock/auto")
def auto_create_restock_requests(
    current_user: User = Depends(require_role([UserRole.CITY_ADMIN])),
    db: Session = Depends(get_db)
):
    """Auto-create restock requests for low stock items"""
    items = db.query(Inventory).filter(
        Inventory.city_id == current_user.city_id,
        Inventory.organization_id == current_user.organization_id,
        Inventory.current_stock <= Inventory.min_threshold
    ).all()
    created = 0
    for inv in items:
        existing = db.query(ReorderRequest).filter(
            ReorderRequest.inventory_id == inv.id,
            ReorderRequest.status == "pending"
        ).first()
        if existing:
            continue
        requested_qty = (inv.max_threshold - inv.current_stock) if inv.max_threshold else max(inv.min_threshold - inv.current_stock, 1)
        request = ReorderRequest(
            part_id=inv.part_id,
            inventory_id=inv.id,
            organization_id=inv.organization_id,
            requested_quantity=requested_qty,
            current_stock=inv.current_stock,
            min_threshold=inv.min_threshold,
            requested_by_id=current_user.id,
            status="pending"
        )
        db.add(request)
        created += 1
    db.commit()
    return {"message": "Auto restock requests created", "created": created}


@router.post("/inventory/returns")
def record_inventory_return(
    payload: dict = Body(...),
    current_user: User = Depends(require_role([UserRole.CITY_ADMIN])),
    db: Session = Depends(get_db)
):
    """Record return of used/rejected parts into city inventory"""
    inventory_id = payload.get("inventory_id")
    quantity = payload.get("quantity")
    ticket_id = payload.get("ticket_id")
    notes = payload.get("notes") or "Returned parts"
    if not inventory_id or not quantity:
        raise HTTPException(status_code=400, detail="inventory_id and quantity are required")
    try:
        inventory_id = int(inventory_id)
        quantity = int(quantity)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid quantity")

    # ticket_id is optional; treat empty string as None, validate if provided
    ticket_id_int = None
    if ticket_id not in ("", None):
        try:
            ticket_id_int = int(ticket_id)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Invalid ticket_id")

    inventory = db.query(Inventory).filter(
        Inventory.id == inventory_id,
        Inventory.city_id == current_user.city_id,
        Inventory.organization_id == current_user.organization_id
    ).first()
    if not inventory:
        raise HTTPException(status_code=404, detail="Inventory item not found")

    previous_stock = inventory.current_stock
    inventory.current_stock += quantity
    inventory.is_low_stock = inventory.current_stock <= inventory.min_threshold

    transaction = InventoryTransaction(
        part_id=inventory.part_id,
        inventory_id=inventory.id,
        ticket_id=ticket_id_int,
        transaction_type="return",
        quantity=quantity,
        previous_stock=previous_stock,
        new_stock=inventory.current_stock,
        performed_by_id=current_user.id,
        notes=notes
    )
    db.add(transaction)
    db.commit()
    return {"message": "Return recorded", "new_stock": inventory.current_stock}


@router.post("/tickets/{ticket_id}/reassign")
def reassign_ticket(
    ticket_id: int,
    reassign_data: dict = Body(...),
    current_user: User = Depends(require_role([UserRole.CITY_ADMIN])),
    db: Session = Depends(get_db)
):
    """Reassign ticket to another engineer from database"""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    if ticket.city_id != current_user.city_id:
        raise HTTPException(status_code=403, detail="Ticket not in your city")
    
    engineer_id = reassign_data.get("engineer_id")
    if not engineer_id:
        raise HTTPException(status_code=400, detail="engineer_id is required")
    
    # Verify engineer is in the same city from database
    engineer = db.query(User).filter(
        User.id == engineer_id,
        User.city_id == current_user.city_id,
        User.role == UserRole.SUPPORT_ENGINEER
    ).first()
    
    if not engineer:
        raise HTTPException(status_code=404, detail="Engineer not found in your city")
    
    # Create comment
    comment = TicketComment(
        ticket_id=ticket.id,
        user_id=current_user.id,
        comment_text=f"Ticket reassigned from engineer {ticket.assigned_engineer_id} to {engineer_id}",
        comment_type="reassignment"
    )
    db.add(comment)
    
    # Reassign
    ticket.assigned_engineer_id = engineer_id
    ticket.assigned_by_id = current_user.id
    ticket.assigned_at = datetime.now(timezone.utc)
    ticket.status = TicketStatus.ASSIGNED
    
    db.commit()
    
    return {"message": "Ticket reassigned successfully"}


@router.post("/tickets/bulk-reassign")
def bulk_reassign_tickets(
    reassign_data: dict = Body(...),
    current_user: User = Depends(require_role([UserRole.CITY_ADMIN])),
    db: Session = Depends(get_db)
):
    """Bulk reassign multiple tickets to an engineer"""
    ticket_ids = reassign_data.get("ticket_ids") or []
    engineer_id = reassign_data.get("engineer_id")
    if not ticket_ids or not engineer_id:
        raise HTTPException(status_code=400, detail="ticket_ids and engineer_id are required")

    engineer = db.query(User).filter(
        User.id == engineer_id,
        User.city_id == current_user.city_id,
        User.role == UserRole.SUPPORT_ENGINEER
    ).first()
    if not engineer:
        raise HTTPException(status_code=404, detail="Engineer not found in your city")

    tickets = db.query(Ticket).filter(
        Ticket.id.in_(ticket_ids),
        Ticket.city_id == current_user.city_id
    ).all()
    if not tickets:
        raise HTTPException(status_code=404, detail="No matching tickets found")

    for ticket in tickets:
        comment = TicketComment(
            ticket_id=ticket.id,
            user_id=current_user.id,
            comment_text=f"Ticket reassigned from engineer {ticket.assigned_engineer_id} to {engineer_id}",
            comment_type="reassignment"
        )
        db.add(comment)
        ticket.assigned_engineer_id = engineer_id
        ticket.assigned_by_id = current_user.id
        ticket.assigned_at = datetime.now(timezone.utc)
        ticket.status = TicketStatus.ASSIGNED

    db.commit()
    return {"message": f"Reassigned {len(tickets)} tickets"}


@router.post("/tickets/auto-redispatch")
def auto_redispatch_tickets(
    payload: dict = Body(default={}),
    current_user: User = Depends(require_role([UserRole.CITY_ADMIN])),
    db: Session = Depends(get_db)
):
    """Auto-redispatch at-risk tickets to available engineers"""
    risk_threshold = float(payload.get("risk_threshold", 0.7))
    max_tickets = int(payload.get("max_tickets", 10))

    tickets = db.query(Ticket).filter(
        Ticket.city_id == current_user.city_id,
        Ticket.status.in_([TicketStatus.CREATED, TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS]),
        Ticket.sla_breach_risk.isnot(None),
        Ticket.sla_breach_risk >= risk_threshold
    ).order_by(Ticket.sla_breach_risk.desc()).limit(max_tickets).all()

    engineers = db.query(User).filter(
        User.city_id == current_user.city_id,
        User.role == UserRole.SUPPORT_ENGINEER,
        User.is_available == True
    ).all()

    if not engineers or not tickets:
        return {"message": "No redispatch needed", "redispatched": 0}

    engineer_ids = [e.id for e in engineers]
    workload = dict(
        db.query(Ticket.assigned_engineer_id, func.count(Ticket.id))
        .filter(
            Ticket.assigned_engineer_id.in_(engineer_ids),
            Ticket.status.in_([TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS])
        )
        .group_by(Ticket.assigned_engineer_id)
        .all()
    )

    redispatched = 0
    for ticket in tickets:
        if _is_assignment_frozen(db, ticket.id):
            continue
        selected = min(engineers, key=lambda e: workload.get(e.id, 0))
        ticket.assigned_engineer_id = selected.id
        ticket.assigned_by_id = current_user.id
        ticket.assigned_at = datetime.now(timezone.utc)
        ticket.status = TicketStatus.ASSIGNED
        workload[selected.id] = workload.get(selected.id, 0) + 1
        redispatched += 1

        comment = TicketComment(
            ticket_id=ticket.id,
            user_id=current_user.id,
            comment_text=f"Auto-redispatched to engineer {selected.id} due to SLA risk",
            comment_type="auto_redispatch"
        )
        db.add(comment)

    db.commit()
    return {"message": "Auto-redispatch complete", "redispatched": redispatched}


@router.post("/tickets/{ticket_id}/priority")
def update_ticket_priority(
    ticket_id: int,
    payload: dict = Body(...),
    current_user: User = Depends(require_role([UserRole.CITY_ADMIN])),
    db: Session = Depends(get_db)
):
    """Update ticket priority with reason"""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.city_id != current_user.city_id:
        raise HTTPException(status_code=403, detail="Ticket not in your city")

    from app.models.ticket import TicketPriority
    priority_value = payload.get("priority")
    reason = payload.get("reason") or "Priority updated by City Admin"
    try:
        priority_enum = TicketPriority(priority_value)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid priority")

    ticket.priority = priority_enum
    comment = TicketComment(
        ticket_id=ticket.id,
        user_id=current_user.id,
        comment_text=reason,
        comment_type="priority_update",
        extra_data={"priority": priority_enum.value}
    )
    db.add(comment)
    db.commit()
    return {"message": "Priority updated"}


@router.post("/tickets/{ticket_id}/freeze-assignment")
def freeze_ticket_assignment(
    ticket_id: int,
    payload: dict = Body(default={}),
    current_user: User = Depends(require_role([UserRole.CITY_ADMIN])),
    db: Session = Depends(get_db)
):
    """Freeze or unfreeze auto-redispatch for a ticket"""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.city_id != current_user.city_id:
        raise HTTPException(status_code=403, detail="Ticket not in your city")

    frozen = bool(payload.get("frozen", True))
    reason = payload.get("reason") or ("Assignment frozen" if frozen else "Assignment unfrozen")
    comment = TicketComment(
        ticket_id=ticket.id,
        user_id=current_user.id,
        comment_text=reason,
        comment_type="assignment_freeze",
        extra_data={"frozen": frozen}
    )
    db.add(comment)
    db.commit()
    return {"message": "Assignment freeze updated", "frozen": frozen}


@router.get("/tickets/redispatch-suggestions")
def get_redispatch_suggestions(
    current_user: User = Depends(require_role([UserRole.CITY_ADMIN])),
    db: Session = Depends(get_db)
):
    """Suggest engineer assignments for at-risk tickets"""
    if not current_user.city_id:
        raise HTTPException(status_code=400, detail="User must be assigned to a city")

    tickets = db.query(Ticket).filter(
        Ticket.city_id == current_user.city_id,
        Ticket.status.in_([TicketStatus.CREATED, TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS]),
        Ticket.sla_breach_risk.isnot(None),
        Ticket.sla_breach_risk >= 0.6
    ).order_by(Ticket.sla_breach_risk.desc()).limit(10).all()

    engineers = db.query(User).filter(
        User.city_id == current_user.city_id,
        User.role == UserRole.SUPPORT_ENGINEER,
        User.is_available == True
    ).all()

    if not engineers or not tickets:
        return []

    engineer_ids = [e.id for e in engineers]
    workload = dict(
        db.query(Ticket.assigned_engineer_id, func.count(Ticket.id))
        .filter(
            Ticket.assigned_engineer_id.in_(engineer_ids),
            Ticket.status.in_([TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS])
        )
        .group_by(Ticket.assigned_engineer_id)
        .all()
    )

    suggestions = []
    for ticket in tickets:
        if _is_assignment_frozen(db, ticket.id):
            continue
        selected = min(engineers, key=lambda e: workload.get(e.id, 0))
        suggestions.append({
            "ticket_id": ticket.id,
            "ticket_number": ticket.ticket_number,
            "risk": ticket.sla_breach_risk,
            "suggested_engineer_id": selected.id,
            "suggested_engineer_name": selected.full_name,
            "reason": "Lowest current workload and available",
        })
        workload[selected.id] = workload.get(selected.id, 0) + 1

    return suggestions


@router.get("/fraud-anomalies")
async def get_city_fraud_anomalies(
    current_user: User = Depends(require_role([UserRole.CITY_ADMIN])),
    db: Session = Depends(get_db)
):
    """Detect fraud or suspicious patterns for the city"""
    if not current_user.city_id:
        raise HTTPException(status_code=400, detail="User must be assigned to a city")

    # Run heuristic anomaly detection
    anomalies = await anomaly_service.detect_anomalies(current_user.organization_id or 0)

    # Add city-specific checks
    suspicious = []
    recent_tickets = db.query(Ticket).filter(
        Ticket.city_id == current_user.city_id,
        Ticket.created_at >= datetime.now(timezone.utc) - timedelta(days=30)
    ).all()
    for t in recent_tickets:
        if t.parts_used and not t.resolution_photos:
            suspicious.append({
                "type": "parts_without_photos",
                "severity": "medium",
                "ticket_id": t.id,
                "description": "Parts used without resolution photos"
            })
        if t.parent_ticket_id:
            suspicious.append({
                "type": "repeat_visit",
                "severity": "low",
                "ticket_id": t.id,
                "description": "Follow-up ticket indicates repeat visit"
            })

    return {
        "risk_score": anomalies.get("risk_score", 0),
        "detected_anomalies": anomalies.get("detected_anomalies", []) + suspicious,
        "recommendations": anomalies.get("recommendations", [])
    }


@router.get("/tickets/{ticket_id}/quality-check")
def get_ticket_for_quality_check(
    ticket_id: int,
    current_user: User = Depends(require_role([UserRole.CITY_ADMIN])),
    db: Session = Depends(get_db)
):
    """Get ticket details for quality check from database"""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    if ticket.city_id != current_user.city_id:
        raise HTTPException(status_code=403, detail="Ticket not in your city")
    
    # Get all comments from database
    comments = db.query(TicketComment).filter(
        TicketComment.ticket_id == ticket.id
    ).order_by(TicketComment.created_at.desc()).all()
    
    return {
        "ticket": {
            "id": ticket.id,
            "ticket_number": ticket.ticket_number,
            "status": ticket.status.value,
            "resolution_notes": ticket.resolution_notes,
            "resolution_photos": ticket.resolution_photos,
            "parts_used": ticket.parts_used,
            "customer_rating": ticket.customer_rating,
            "customer_feedback": ticket.customer_feedback,
            "resolved_at": ticket.resolved_at.isoformat() if ticket.resolved_at else None
        },
        "engineer": {
            "id": ticket.assigned_engineer_id,
            "name": ticket.assigned_engineer.full_name if ticket.assigned_engineer else None
        },
        "comments": [
            {
                "id": c.id,
                "comment_text": c.comment_text,
                "comment_type": c.comment_type,
                "user_id": c.user_id,
                "created_at": c.created_at.isoformat() if c.created_at else None
            }
            for c in comments
        ]
    }


@router.post("/tickets/{ticket_id}/quality-check")
def submit_quality_check(
    ticket_id: int,
    quality_data: dict = Body(...),
    current_user: User = Depends(require_role([UserRole.CITY_ADMIN])),
    db: Session = Depends(get_db)
):
    """Submit quality check for a ticket"""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    if ticket.city_id != current_user.city_id:
        raise HTTPException(status_code=403, detail="Ticket not in your city")
    
    quality_status = quality_data.get("status")  # pass, fail, needs_improvement
    quality_notes = quality_data.get("notes", "")
    
    # Create quality check comment
    comment = TicketComment(
        ticket_id=ticket.id,
        user_id=current_user.id,
        comment_text=f"Quality check: {quality_status}. Notes: {quality_notes}",
        comment_type="quality_check",
        extra_data={
            "quality_status": quality_status,
            "quality_notes": quality_notes
        }
    )
    db.add(comment)
    
    # If quality check fails, reopen ticket or escalate
    if quality_status == "fail":
        ticket.status = TicketStatus.ESCALATED
        # Could also create escalation record here
    
    db.commit()
    
    return {"message": "Quality check submitted", "status": quality_status}
