"""
Ticket endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, Body, Response, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
import os
import uuid

from app.core.database import get_db
from app.core.permissions import get_current_user, require_role
from app.models.user import User, UserRole
from app.models.ticket import Ticket, TicketStatus, TicketPriority, TicketComment
from app.models.device import Device
from app.models.inventory import Part
from app.models.escalation import Escalation, EscalationLevel, EscalationType
from app.models.notification import Notification, NotificationType, NotificationChannel, NotificationStatus
from app.services.ai.sentiment_analyzer import SentimentAnalyzerService
from app.services.ai.case_triage import CaseTriageService
from app.services.ai.sla_prediction import SLABreachPredictionService
from app.services.policy_matcher import PolicyMatcherService
from app.models.sla_policy import SLAType

router = APIRouter()
triage_service = CaseTriageService()
sla_service = SLABreachPredictionService()
sentiment_service = SentimentAnalyzerService()


def build_status_timeline(ticket: Ticket, follow_up_comments: Optional[List[TicketComment]] = None):
    timeline = [
        ("Ticket created", ticket.created_at),
        ("Assigned to engineer", ticket.assigned_at),
        ("Engineer started", ticket.started_at),
        ("Waiting for parts", ticket.status == TicketStatus.WAITING_PARTS),
        ("Resolved", ticket.resolved_at),
        ("Closed", ticket.closed_at),
    ]
    result = []
    for label, marker in timeline:
        if isinstance(marker, bool):
            completed = marker
        else:
            completed = marker is not None
        result.append({
            "label": label,
            "completed": completed
        })

    comments = follow_up_comments or ticket.comments or []
    for comment in comments:
        if comment.comment_type == "reschedule_request":
            preferred_date = (comment.extra_data or {}).get("preferred_date")
            label = f"Visit rescheduled ({preferred_date})" if preferred_date else "Visit rescheduled"
            result.append({"label": label, "completed": True})
        elif comment.comment_type == "part_ordered":
            result.append({"label": "Part ordered", "completed": True})
        elif comment.comment_type == "part_received":
            result.append({"label": "Part received", "completed": True})
        elif comment.comment_type == "parts_approval":
            result.append({"label": "Parts approved", "completed": True})
        elif comment.comment_type == "parts_rejection":
            result.append({"label": "Parts rejected", "completed": True})
        elif comment.comment_type == "arrival":
            result.append({"label": "Engineer arrived", "completed": True})
        elif comment.comment_type == "resolution":
            result.append({"label": "Resolution updated", "completed": True})

    return result


def _queue_customer_notifications(
    db: Session,
    ticket: Ticket,
    title: str,
    message: str,
    notification_type: NotificationType
):
    if not ticket.customer_id:
        return
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
            notification_type=notification_type,
            channel=channel,
            title=title,
            message=message,
            ticket_id=ticket.id,
            status=NotificationStatus.PENDING,
            action_url=f"/customer/ticket/{ticket.id}"
        )
        db.add(notification)


def _save_upload_file(upload: UploadFile, subdir: str) -> str:
    base_dir = os.path.join(os.path.dirname(__file__), "..", "..", "uploads", subdir)
    os.makedirs(base_dir, exist_ok=True)
    ext = os.path.splitext(upload.filename or "")[1] or ".bin"
    filename = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(base_dir, filename)
    with open(file_path, "wb") as f:
        f.write(upload.file.read())
    return f"/uploads/{subdir}/{filename}"


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_ticket(
    ticket_data: dict = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new ticket"""
    issue_description = ticket_data.get("issue_description")
    device_id = ticket_data.get("device_id")
    device_serial = ticket_data.get("device_serial")
    issue_photos = ticket_data.get("issue_photos") or []
    service_address = ticket_data.get("service_address") or ""
    service_latitude = ticket_data.get("service_latitude")
    service_longitude = ticket_data.get("service_longitude")
    priority = ticket_data.get("priority") or TicketPriority.MEDIUM
    issue_language = ticket_data.get("issue_language")
    contact_preferences = ticket_data.get("contact_preferences") or []
    preferred_time_slots = ticket_data.get("preferred_time_slots") or []

    if not issue_description:
        raise HTTPException(status_code=400, detail="Issue description is required")

    # Get or create device
    device = None
    if device_id:
        device = db.query(Device).filter(Device.id == device_id).first()
    elif device_serial:
        device = db.query(Device).filter(Device.serial_number == device_serial).first()
    
    if not device and device_serial:
        raise HTTPException(status_code=404, detail="Device not found. Please register device first.")
    
    # Generate ticket number
    ticket_number = f"TKT-{datetime.utcnow().strftime('%Y%m%d')}-{db.query(Ticket).count() + 1:06d}"
    
    # AI Triage
    triage_result = await triage_service.triage_ticket(
        issue_description=issue_description,
        issue_photos=issue_photos or [],
        device_category=device.product_category if device else None,
        device_model=device.model_number if device else None
    )
    
    # Create ticket
    try:
        priority_enum = TicketPriority(priority) if isinstance(priority, str) else priority
    except ValueError:
        priority_enum = TicketPriority.MEDIUM

    organization_id = current_user.organization_id or (device.organization_id if device else None)

    ticket = Ticket(
        ticket_number=ticket_number,
        organization_id=organization_id,
        customer_id=current_user.id if current_user.role == UserRole.CUSTOMER else None,
        device_id=device.id if device else None,
        created_by_id=current_user.id,
        country_id=current_user.country_id,
        state_id=current_user.state_id,
        city_id=current_user.city_id,
        issue_description=issue_description,
        issue_photos=issue_photos or [],
        issue_language=issue_language,
        contact_preferences=contact_preferences,
        preferred_time_slots=preferred_time_slots,
        service_address=service_address,
        service_latitude=service_latitude,
        service_longitude=service_longitude,
        priority=priority_enum or TicketPriority(triage_result.get("suggested_priority", "medium")),
        issue_category=triage_result.get("suggested_category"),
        ai_triage_category=triage_result.get("suggested_category"),
        ai_triage_confidence=triage_result.get("confidence_score"),
        ai_suggested_parts=triage_result.get("suggested_parts", []),
        status=TicketStatus.CREATED
    )
    
    db.add(ticket)
    db.flush()  # Flush to get ticket ID without committing
    
    # Apply policies
    policy_matcher = PolicyMatcherService(db)
    policy_results = {}
    
    if ticket.organization_id:
        # Apply Resolution SLA
        resolution_deadline = policy_matcher.apply_sla_to_ticket(ticket, SLAType.RESOLUTION)
        if resolution_deadline:
            ticket.sla_deadline = resolution_deadline
        
        # Apply Service Policies
        service_policy_results = policy_matcher.apply_service_policies_to_ticket(ticket)
        if service_policy_results:
            ticket.warranty_status = service_policy_results.get("warranty_status")
            ticket.is_chargeable = service_policy_results.get("is_chargeable", False)
            policy_results = service_policy_results

    _queue_customer_notifications(
        db,
        ticket,
        title="Ticket created",
        message=f"Your ticket {ticket.ticket_number} has been created.",
        notification_type=NotificationType.TICKET_CREATED
    )
    
    db.commit()
    db.refresh(ticket)
    
    return {
        "id": ticket.id,
        "ticket_number": ticket.ticket_number,
        "status": ticket.status.value,
        "sla_deadline": ticket.sla_deadline.isoformat() if ticket.sla_deadline else None,
        "warranty_status": ticket.warranty_status,
        "is_chargeable": ticket.is_chargeable,
        "ai_triage": triage_result,
        "applied_policies": policy_results.get("applied_policies", [])
    }


@router.get("/", response_model=List[dict])
async def list_tickets(
    status_filter: Optional[TicketStatus] = None,
    priority_filter: Optional[TicketPriority] = None,
    city_id: Optional[int] = None,
    state_id: Optional[int] = None,
    assigned_to_me: bool = False,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List tickets based on user role and permissions"""
    query = db.query(Ticket)
    
    # Role-based filtering
    if current_user.role == UserRole.CUSTOMER:
        query = query.filter(Ticket.customer_id == current_user.id)
    elif current_user.role == UserRole.SUPPORT_ENGINEER:
        if assigned_to_me:
            query = query.filter(Ticket.assigned_engineer_id == current_user.id)
        else:
            query = query.filter(
                (Ticket.city_id == current_user.city_id) |
                (Ticket.assigned_engineer_id == current_user.id)
            )
    elif current_user.role == UserRole.CITY_ADMIN:
        query = query.filter(Ticket.city_id == current_user.city_id)
    elif current_user.role == UserRole.STATE_ADMIN:
        query = query.filter(Ticket.state_id == current_user.state_id)
    elif current_user.role == UserRole.COUNTRY_ADMIN:
        query = query.filter(Ticket.country_id == current_user.country_id)
    elif current_user.role == UserRole.ORGANIZATION_ADMIN:
        query = query.filter(Ticket.organization_id == current_user.organization_id)
    
    # Apply filters
    if status_filter:
        query = query.filter(Ticket.status == status_filter)
    if priority_filter:
        query = query.filter(Ticket.priority == priority_filter)
    if city_id:
        query = query.filter(Ticket.city_id == city_id)
    if state_id:
        query = query.filter(Ticket.state_id == state_id)
    
    tickets = query.offset(skip).limit(limit).all()
    
    return [
        {
            "id": t.id,
            "ticket_number": t.ticket_number,
            "status": t.status.value,
            "priority": t.priority.value,
            "issue_category": t.issue_category,
            "issue_description": t.issue_description,
            "created_at": t.created_at.isoformat(),
            "assigned_engineer_id": t.assigned_engineer_id,
            "service_address": t.service_address,
            "service_latitude": t.service_latitude,
            "service_longitude": t.service_longitude,
            "warranty_status": t.warranty_status,
            "is_chargeable": t.is_chargeable,
            "preferred_time_slots": t.preferred_time_slots or [],
            "contact_preferences": t.contact_preferences or [],
            "status_timeline": build_status_timeline(t),
            "parent_ticket_id": t.parent_ticket_id,
            "follow_up_preferred_date": t.follow_up_preferred_date.isoformat() if t.follow_up_preferred_date else None,
            "sla_deadline": t.sla_deadline.isoformat() if t.sla_deadline else None,
            "customer_name": t.customer.full_name if t.customer else None,
            "parts_ready": t.status != TicketStatus.WAITING_PARTS
        }
        for t in tickets
    ]


@router.get("/{ticket_id}")
async def get_ticket(
    ticket_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get ticket details"""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    # Check access
    if current_user.role == UserRole.CUSTOMER:
        if ticket.customer_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
    
    # Get SLA breach prediction
    if ticket.sla_deadline:
        sla_prediction = await sla_service.predict_breach_risk(
            ticket_id=ticket.id,
            current_status=ticket.status.value,
            sla_deadline=ticket.sla_deadline,
            created_at=ticket.created_at,
            assigned_at=ticket.assigned_at
        )
    else:
        sla_prediction = None
    
    follow_up_comments = db.query(TicketComment).filter(
        TicketComment.ticket_id == ticket.id,
        TicketComment.comment_type == "follow_up"
    ).order_by(TicketComment.created_at.desc()).all()

    follow_up_actions = [
        {
            "action_type": (c.extra_data or {}).get("action_type"),
            "preferred_date": (c.extra_data or {}).get("preferred_date"),
            "goodwill": (c.extra_data or {}).get("goodwill"),
            "notes": c.comment_text,
            "created_at": c.created_at.isoformat() if c.created_at else None
        }
        for c in follow_up_comments
    ]

    return {
        "id": ticket.id,
        "ticket_number": ticket.ticket_number,
        "status": ticket.status.value,
        "priority": ticket.priority.value,
        "city_id": ticket.city_id,
        "state_id": ticket.state_id,
        "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
        "sla_deadline": ticket.sla_deadline.isoformat() if ticket.sla_deadline else None,
        "resolved_at": ticket.resolved_at.isoformat() if ticket.resolved_at else None,
        "parent_ticket_id": ticket.parent_ticket_id,
        "follow_up_preferred_date": ticket.follow_up_preferred_date.isoformat() if ticket.follow_up_preferred_date else None,
        "issue_description": ticket.issue_description,
        "issue_photos": ticket.issue_photos or [],
        "issue_language": ticket.issue_language,
        "contact_preferences": ticket.contact_preferences or [],
        "preferred_time_slots": ticket.preferred_time_slots or [],
        "service_address": ticket.service_address,
        "service_latitude": ticket.service_latitude,
        "service_longitude": ticket.service_longitude,
        "customer": {
            "id": ticket.customer.id,
            "full_name": ticket.customer.full_name,
            "phone": ticket.customer.phone,
            "email": ticket.customer.email
        } if ticket.customer_id and ticket.customer else None,
        "assigned_engineer": {
            "id": ticket.assigned_engineer.id,
            "full_name": ticket.assigned_engineer.full_name,
            "phone": ticket.assigned_engineer.phone,
            "email": ticket.assigned_engineer.email
        } if ticket.assigned_engineer_id and ticket.assigned_engineer else None,
        "device": {
            "id": ticket.device.id,
            "brand": ticket.device.brand,
            "model_number": ticket.device.model_number,
            "serial_number": ticket.device.serial_number,
            "product_category": ticket.device.product_category,
            "product_model_id": ticket.device.product_model_id,
            "product_id": ticket.device.product_id,
            "service_instructions": ticket.device.product_model.service_instructions if ticket.device.product_model else None
        } if ticket.device else None,
        "oem_instructions": ticket.device.product_model.service_instructions if ticket.device and ticket.device.product_model else None,
        "warranty_status": ticket.warranty_status,
        "is_chargeable": ticket.is_chargeable,
        "parts_used": ticket.parts_used or [],
        "resolution_notes": ticket.resolution_notes,
        "resolution_photos": ticket.resolution_photos or [],
        "engineer_eta_start": ticket.engineer_eta_start.isoformat() if ticket.engineer_eta_start else None,
        "engineer_eta_end": ticket.engineer_eta_end.isoformat() if ticket.engineer_eta_end else None,
        "arrival_confirmed_at": ticket.arrival_confirmed_at.isoformat() if ticket.arrival_confirmed_at else None,
        "arrival_latitude": ticket.arrival_latitude,
        "arrival_longitude": ticket.arrival_longitude,
        "customer_rating": ticket.customer_rating,
        "customer_feedback": ticket.customer_feedback,
        "customer_dispute_tags": ticket.customer_dispute_tags or [],
        "ai_triage": {
            "category": ticket.ai_triage_category,
            "confidence": ticket.ai_triage_confidence,
            "suggested_parts": ticket.ai_suggested_parts
        },
        "sla_prediction": sla_prediction,
        "status_timeline": build_status_timeline(ticket, follow_up_comments),
        "follow_up_actions": follow_up_actions,
        "parent_ticket": {
            "id": ticket.parent_ticket.id,
            "ticket_number": ticket.parent_ticket.ticket_number,
            "status": ticket.parent_ticket.status.value
        } if ticket.parent_ticket else None,
        "follow_up_tickets": [
            {
                "id": t.id,
                "ticket_number": t.ticket_number,
                "status": t.status.value,
                "follow_up_preferred_date": t.follow_up_preferred_date.isoformat() if t.follow_up_preferred_date else None
            }
            for t in ticket.follow_up_tickets
        ] if ticket.follow_up_tickets else []
    }


@router.get("/{ticket_id}/tracking")
async def get_ticket_tracking(
    ticket_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get assigned engineer live location for customer"""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if current_user.role == UserRole.CUSTOMER and ticket.customer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    if not ticket.assigned_engineer:
        raise HTTPException(status_code=400, detail="Engineer not assigned")

    return {
        "engineer_id": ticket.assigned_engineer.id,
        "latitude": ticket.assigned_engineer.current_location_lat,
        "longitude": ticket.assigned_engineer.current_location_lng
    }


@router.get("/{ticket_id}/estimate")
async def get_ticket_estimate(
    ticket_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Estimate cost based on suggested parts and warranty"""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if current_user.role == UserRole.CUSTOMER and ticket.customer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    if ticket.warranty_status == "in_warranty" and not ticket.is_chargeable:
        return {"total_estimate": 0, "parts": [], "labour": 0, "note": "Covered under warranty"}

    labour_cost = 300
    part_ids = []
    for item in ticket.ai_suggested_parts or []:
        if isinstance(item, dict) and item.get("part_id"):
            part_ids.append(item["part_id"])
        elif isinstance(item, int):
            part_ids.append(item)

    parts = db.query(Part).filter(Part.id.in_(part_ids)).all() if part_ids else []
    parts_breakdown = [
        {
            "part_id": p.id,
            "part_name": p.name,
            "price": p.selling_price or 0
        }
        for p in parts
    ]
    parts_total = sum(p["price"] for p in parts_breakdown)
    total = parts_total + labour_cost

    return {
        "total_estimate": total,
        "parts": parts_breakdown,
        "labour": labour_cost,
        "note": "Estimated based on suggested parts"
    }


@router.post("/{ticket_id}/assign")
async def assign_ticket(
    ticket_id: int,
    engineer_id: Optional[int] = None,
    current_user: User = Depends(require_role([UserRole.CITY_ADMIN, UserRole.STATE_ADMIN, UserRole.ORGANIZATION_ADMIN])),
    db: Session = Depends(get_db)
):
    """Assign ticket to engineer"""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    if engineer_id:
        engineer = db.query(User).filter(
            User.id == engineer_id,
            User.role == UserRole.SUPPORT_ENGINEER
        ).first()
        
        if not engineer:
            raise HTTPException(status_code=404, detail="Engineer not found")
        
        ticket.assigned_engineer_id = engineer_id
        ticket.assigned_at = datetime.utcnow()
        ticket.status = TicketStatus.ASSIGNED

        _queue_customer_notifications(
            db,
            ticket,
            title="Ticket assigned",
            message=f"Your ticket {ticket.ticket_number} has been assigned to an engineer.",
            notification_type=NotificationType.TICKET_ASSIGNED
        )
    
    db.commit()
    
    return {"message": "Ticket assigned successfully"}


@router.post("/{ticket_id}/start")
async def start_ticket(
    ticket_id: int,
    start_data: dict = Body(default={}),
    current_user: User = Depends(require_role([UserRole.SUPPORT_ENGINEER])),
    db: Session = Depends(get_db)
):
    """Engineer starts working on ticket"""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    if ticket.assigned_engineer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Ticket not assigned to you")
    
    ticket.status = TicketStatus.IN_PROGRESS
    ticket.started_at = datetime.utcnow()
    eta_start = start_data.get("eta_start")
    eta_end = start_data.get("eta_end")
    if eta_start:
        try:
            ticket.engineer_eta_start = datetime.fromisoformat(eta_start.replace('Z', '+00:00'))
        except Exception:
            pass
    if eta_end:
        try:
            ticket.engineer_eta_end = datetime.fromisoformat(eta_end.replace('Z', '+00:00'))
        except Exception:
            pass

    _queue_customer_notifications(
        db,
        ticket,
        title="Work started",
        message="Your engineer has started working on your ticket.",
        notification_type=NotificationType.TICKET_UPDATED
    )
    
    if ticket.customer_id and (ticket.engineer_eta_start or ticket.engineer_eta_end):
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
                notification_type=NotificationType.ENGINEER_ETA,
                channel=channel,
                title="Engineer ETA updated",
                message="Your engineer has shared an updated ETA.",
                ticket_id=ticket.id,
                status=NotificationStatus.PENDING,
                action_url=f"/customer/ticket/{ticket.id}"
            )
            db.add(notification)

    db.commit()
    
    return {"message": "Ticket started"}


@router.post("/{ticket_id}/eta")
async def update_ticket_eta(
    ticket_id: int,
    eta_data: dict = Body(...),
    current_user: User = Depends(require_role([UserRole.SUPPORT_ENGINEER])),
    db: Session = Depends(get_db)
):
    """Update engineer ETA and notify customer"""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.assigned_engineer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Ticket not assigned to you")

    eta_start = eta_data.get("eta_start")
    eta_end = eta_data.get("eta_end")
    if eta_start:
        try:
            ticket.engineer_eta_start = datetime.fromisoformat(eta_start.replace('Z', '+00:00'))
        except Exception:
            pass
    if eta_end:
        try:
            ticket.engineer_eta_end = datetime.fromisoformat(eta_end.replace('Z', '+00:00'))
        except Exception:
            pass

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
                notification_type=NotificationType.ENGINEER_ETA,
                channel=channel,
                title="Engineer ETA updated",
                message="Your engineer has shared an updated ETA.",
                ticket_id=ticket.id,
                status=NotificationStatus.PENDING,
                action_url=f"/customer/ticket/{ticket.id}"
            )
            db.add(notification)

    db.commit()
    return {"message": "ETA updated"}


@router.post("/{ticket_id}/resolve")
async def resolve_ticket(
    ticket_id: int,
    resolution_data: dict = Body(...),
    current_user: User = Depends(require_role([UserRole.SUPPORT_ENGINEER])),
    db: Session = Depends(get_db)
):
    """Resolve a ticket"""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    resolution_notes = resolution_data.get("resolution_notes") or ""
    if not resolution_notes.strip():
        raise HTTPException(status_code=400, detail="resolution_notes is required")

    parts_used = resolution_data.get("parts_used") or []
    resolution_photos = resolution_data.get("resolution_photos") or []
    customer_signature = resolution_data.get("customer_signature")
    customer_otp_verified = bool(resolution_data.get("customer_otp_verified"))

    ticket.status = TicketStatus.RESOLVED
    ticket.resolution_notes = resolution_notes
    ticket.resolution_photos = resolution_photos
    ticket.parts_used = parts_used
    ticket.customer_signature = customer_signature
    ticket.customer_otp_verified = customer_otp_verified
    ticket.resolved_at = datetime.utcnow()
    
    # Parts will be deducted after City Admin approval
    # Inventory deduction happens in city_admin.approve_parts_usage endpoint
    
    # Create comment for resolution
    from app.models.ticket import TicketComment
    comment = TicketComment(
        ticket_id=ticket.id,
        user_id=current_user.id,
        comment_text=f"Ticket resolved. Parts used: {len(parts_used) if parts_used else 0}",
        comment_type="resolution"
    )
    db.add(comment)

    _queue_customer_notifications(
        db,
        ticket,
        title="Ticket resolved",
        message=f"Your ticket {ticket.ticket_number} has been resolved.",
        notification_type=NotificationType.TICKET_RESOLVED
    )
    
    db.commit()
    
    return {"message": "Ticket resolved. Parts usage pending City Admin approval."}


@router.post("/{ticket_id}/resolution-photo")
async def upload_resolution_photo(
    ticket_id: int,
    photo: UploadFile = File(...),
    current_user: User = Depends(require_role([UserRole.SUPPORT_ENGINEER])),
    db: Session = Depends(get_db)
):
    """Upload resolution photo for a ticket"""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.assigned_engineer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Ticket not assigned to you")

    url = _save_upload_file(photo, "ticket-resolutions")
    return {"url": url}


@router.post("/{ticket_id}/parts/ordered")
async def mark_parts_ordered(
    ticket_id: int,
    parts_data: dict = Body(default={}),
    current_user: User = Depends(require_role([UserRole.SUPPORT_ENGINEER, UserRole.CITY_ADMIN, UserRole.STATE_ADMIN, UserRole.ORGANIZATION_ADMIN])),
    db: Session = Depends(get_db)
):
    """Mark parts as ordered for a ticket"""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    part_refs = parts_data.get("parts") or []
    ticket.status = TicketStatus.WAITING_PARTS

    comment = TicketComment(
        ticket_id=ticket.id,
        user_id=current_user.id,
        comment_text="Parts ordered for this ticket",
        comment_type="part_ordered",
        extra_data={"parts": part_refs}
    )
    db.add(comment)

    _queue_customer_notifications(
        db,
        ticket,
        title="Part ordered",
        message="Parts have been ordered for your ticket.",
        notification_type=NotificationType.PART_ORDERED
    )

    db.commit()
    return {"message": "Parts marked as ordered"}


@router.post("/{ticket_id}/parts/photo")
async def upload_part_photo(
    ticket_id: int,
    photo: UploadFile = File(...),
    current_user: User = Depends(require_role([UserRole.SUPPORT_ENGINEER])),
    db: Session = Depends(get_db)
):
    """Upload part photo for a ticket"""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.assigned_engineer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Ticket not assigned to you")

    url = _save_upload_file(photo, "ticket-parts")
    return {"url": url}


@router.post("/{ticket_id}/parts/received")
async def mark_parts_received(
    ticket_id: int,
    parts_data: dict = Body(default={}),
    current_user: User = Depends(require_role([UserRole.SUPPORT_ENGINEER, UserRole.CITY_ADMIN, UserRole.STATE_ADMIN, UserRole.ORGANIZATION_ADMIN])),
    db: Session = Depends(get_db)
):
    """Mark parts as received for a ticket"""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    part_refs = parts_data.get("parts") or []
    if ticket.status == TicketStatus.WAITING_PARTS:
        ticket.status = TicketStatus.IN_PROGRESS

    comment = TicketComment(
        ticket_id=ticket.id,
        user_id=current_user.id,
        comment_text="Parts received for this ticket",
        comment_type="part_received",
        extra_data={"parts": part_refs}
    )
    db.add(comment)

    _queue_customer_notifications(
        db,
        ticket,
        title="Part received",
        message="Parts have been received and work will resume shortly.",
        notification_type=NotificationType.TICKET_UPDATED
    )

    db.commit()
    return {"message": "Parts marked as received"}


@router.post("/{ticket_id}/parts/request")
async def request_parts_approval(
    ticket_id: int,
    parts_data: dict = Body(default={}),
    current_user: User = Depends(require_role([UserRole.SUPPORT_ENGINEER])),
    db: Session = Depends(get_db)
):
    """Engineer requests parts approval before using expensive parts"""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.assigned_engineer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Ticket not assigned to you")

    parts = parts_data.get("parts") or []
    if not parts:
        raise HTTPException(status_code=400, detail="Parts list is required")

    comment = TicketComment(
        ticket_id=ticket.id,
        user_id=current_user.id,
        comment_text="Parts approval requested",
        comment_type="parts_request",
        extra_data={"parts": parts}
    )
    db.add(comment)

    ticket.status = TicketStatus.WAITING_PARTS

    _queue_customer_notifications(
        db,
        ticket,
        title="Parts approval requested",
        message="Parts approval requested. We will update you once approved.",
        notification_type=NotificationType.TICKET_UPDATED
    )

    db.commit()
    return {"message": "Parts approval request submitted"}


@router.post("/{ticket_id}/arrival")
async def confirm_arrival(
    ticket_id: int,
    arrival_data: dict = Body(...),
    current_user: User = Depends(require_role([UserRole.SUPPORT_ENGINEER])),
    db: Session = Depends(get_db)
):
    """Engineer confirms arrival with geo-tag"""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.assigned_engineer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Ticket not assigned to you")

    ticket.arrival_latitude = arrival_data.get("arrival_latitude")
    ticket.arrival_longitude = arrival_data.get("arrival_longitude")
    ticket.arrival_confirmed_at = datetime.utcnow()

    comment = TicketComment(
        ticket_id=ticket.id,
        user_id=current_user.id,
        comment_text="Engineer arrived on-site",
        comment_type="arrival",
        extra_data={
            "arrival_latitude": ticket.arrival_latitude,
            "arrival_longitude": ticket.arrival_longitude
        }
    )
    db.add(comment)
    db.commit()
    return {"message": "Arrival confirmed"}


@router.post("/{ticket_id}/feedback")
async def submit_feedback(
    ticket_id: int,
    feedback_data: dict = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Customer submits feedback/dispute after resolution"""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if current_user.role == UserRole.CUSTOMER and ticket.customer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    rating = feedback_data.get("rating")
    feedback = feedback_data.get("feedback")
    dispute_tags = feedback_data.get("dispute_tags") or []

    ticket.customer_rating = rating
    ticket.customer_feedback = feedback
    ticket.customer_dispute_tags = dispute_tags

    sentiment = await sentiment_service.analyze_feedback(
        feedback_text=feedback,
        rating=rating
    )
    ticket.sentiment_score = sentiment.get("sentiment_score")

    if (rating is not None and rating <= 2) or (ticket.sentiment_score is not None and ticket.sentiment_score < -0.2) or dispute_tags:
        escalation = Escalation(
            organization_id=ticket.organization_id or current_user.organization_id,
            ticket_id=ticket.id,
            escalation_type=EscalationType.NEGATIVE_SENTIMENT,
            escalation_level=EscalationLevel.CITY,
            reason="Customer feedback flagged for review",
            escalated_by_id=current_user.id,
            extra_data={
                "rating": rating,
                "dispute_tags": dispute_tags,
                "feedback": feedback
            }
        )
        db.add(escalation)

    db.commit()
    return {"message": "Feedback submitted"}


@router.post("/{ticket_id}/escalate")
async def escalate_ticket(
    ticket_id: int,
    escalation_data: dict = Body(...),
    current_user: User = Depends(require_role([UserRole.SUPPORT_ENGINEER, UserRole.CITY_ADMIN])),
    db: Session = Depends(get_db)
):
    """Escalate ticket with reason and type"""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    escalation_type = escalation_data.get("escalation_type") or "technical_issue"
    escalation_level = escalation_data.get("escalation_level") or "city"
    reason = escalation_data.get("reason")
    if not reason:
        raise HTTPException(status_code=400, detail="Escalation reason is required")

    try:
        escalation_type_enum = EscalationType(escalation_type)
        escalation_level_enum = EscalationLevel(escalation_level)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid escalation type or level")

    escalation = Escalation(
        organization_id=ticket.organization_id or current_user.organization_id,
        ticket_id=ticket.id,
        escalation_type=escalation_type_enum,
        escalation_level=escalation_level_enum,
        reason=reason,
        escalated_by_id=current_user.id,
        extra_data=escalation_data.get("extra_data") or {}
    )
    ticket.status = TicketStatus.ESCALATED
    db.add(escalation)
    db.commit()
    return {"message": "Ticket escalated"}


@router.get("/assigned/calendar")
async def export_assigned_calendar(
    current_user: User = Depends(require_role([UserRole.SUPPORT_ENGINEER])),
    db: Session = Depends(get_db)
):
    """Export assigned tickets as an ICS calendar"""
    tickets = db.query(Ticket).filter(
        Ticket.assigned_engineer_id == current_user.id,
        Ticket.status.in_([TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS, TicketStatus.CREATED])
    ).all()

    def format_dt(dt):
        return dt.strftime("%Y%m%dT%H%M%SZ") if dt else None

    events = []
    for t in tickets:
        start = t.follow_up_preferred_date or t.engineer_eta_start or t.sla_deadline
        if not start:
            continue
        end = t.engineer_eta_end or (start + timedelta(hours=1))
        events.append({
            "uid": f"ticket-{t.id}@erepairing",
            "start": format_dt(start),
            "end": format_dt(end),
            "summary": f"{t.ticket_number} - {t.issue_category or 'Service Visit'}",
            "description": t.issue_description or "",
            "location": t.service_address or ""
        })

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//eRepairing//Engineer Calendar//EN"
    ]
    for event in events:
        lines.extend([
            "BEGIN:VEVENT",
            f"UID:{event['uid']}",
            f"DTSTART:{event['start']}",
            f"DTEND:{event['end']}",
            f"SUMMARY:{event['summary']}",
            f"DESCRIPTION:{event['description']}",
            f"LOCATION:{event['location']}",
            "END:VEVENT"
        ])
    lines.append("END:VCALENDAR")

    ics_content = "\r\n".join(lines)
    return Response(content=ics_content, media_type="text/calendar")


@router.post("/{ticket_id}/accept")
async def accept_ticket(
    ticket_id: int,
    current_user: User = Depends(require_role([UserRole.SUPPORT_ENGINEER])),
    db: Session = Depends(get_db)
):
    """Engineer accepts an assigned ticket"""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    if ticket.assigned_engineer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Ticket not assigned to you")
    
    if ticket.status != TicketStatus.ASSIGNED:
        raise HTTPException(status_code=400, detail="Ticket must be in ASSIGNED status to accept")
    
    # Accept the ticket - status remains ASSIGNED, engineer can now start it
    # Create a comment to log the acceptance
    from app.models.ticket import TicketComment
    comment = TicketComment(
        ticket_id=ticket.id,
        user_id=current_user.id,
        comment_text="Ticket accepted by engineer",
        comment_type="acceptance"
    )
    db.add(comment)
    
    db.commit()
    
    return {"message": "Ticket accepted successfully"}


@router.post("/{ticket_id}/reject")
async def reject_ticket(
    ticket_id: int,
    rejection_reason: str,
    current_user: User = Depends(require_role([UserRole.SUPPORT_ENGINEER])),
    db: Session = Depends(get_db)
):
    """Engineer rejects an assigned ticket with reason"""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    if ticket.assigned_engineer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Ticket not assigned to you")
    
    if ticket.status != TicketStatus.ASSIGNED:
        raise HTTPException(status_code=400, detail="Ticket must be in ASSIGNED status to reject")
    
    # Reject the ticket - unassign engineer and set status back to CREATED
    from app.models.ticket import TicketComment
    comment = TicketComment(
        ticket_id=ticket.id,
        user_id=current_user.id,
        comment_text=f"Ticket rejected by engineer. Reason: {rejection_reason}",
        comment_type="rejection",
        extra_data={"rejection_reason": rejection_reason}
    )
    db.add(comment)
    
    # Unassign engineer and reset status
    ticket.assigned_engineer_id = None
    ticket.assigned_by_id = None
    ticket.assigned_at = None
    ticket.status = TicketStatus.CREATED
    
    db.commit()
    
    return {"message": "Ticket rejected successfully"}


@router.post("/{ticket_id}/reschedule")
async def reschedule_ticket(
    ticket_id: int,
    reschedule_data: dict = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Customer reschedules a ticket - creates new ticket with updated schedule"""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    # Only customer who created the ticket can reschedule
    if ticket.customer_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only reschedule your own tickets")
    
    # Only assigned tickets can be rescheduled
    if ticket.status != TicketStatus.ASSIGNED:
        raise HTTPException(status_code=400, detail="Only assigned tickets can be rescheduled")
    
    new_service_address = reschedule_data.get("service_address", ticket.service_address)
    new_service_latitude = reschedule_data.get("service_latitude", ticket.service_latitude)
    new_service_longitude = reschedule_data.get("service_longitude", ticket.service_longitude)
    reschedule_reason = reschedule_data.get("reason", "Customer requested reschedule")
    preferred_date = reschedule_data.get("preferred_date")  # ISO format date string
    
    # Create comment for reschedule request
    from app.models.ticket import TicketComment
    comment = TicketComment(
        ticket_id=ticket.id,
        user_id=current_user.id,
        comment_text=f"Reschedule requested. Reason: {reschedule_reason}. Preferred date: {preferred_date}",
        comment_type="reschedule_request",
        extra_data={
            "reschedule_reason": reschedule_reason,
            "preferred_date": preferred_date,
            "new_service_address": new_service_address
        }
    )
    db.add(comment)
    
    # Update ticket with new service details
    ticket.service_address = new_service_address
    ticket.service_latitude = new_service_latitude
    ticket.service_longitude = new_service_longitude
    
    # Reset assignment to allow reassignment
    ticket.assigned_engineer_id = None
    ticket.assigned_by_id = None
    ticket.assigned_at = None
    ticket.status = TicketStatus.CREATED
    
    # Update SLA deadline if preferred_date is provided
    if preferred_date:
        try:
            from datetime import datetime
            preferred_dt = datetime.fromisoformat(preferred_date.replace('Z', '+00:00'))
            # Set SLA deadline to preferred date + standard SLA hours
            ticket.sla_deadline = preferred_dt
        except:
            pass  # If date parsing fails, keep existing SLA

    _queue_customer_notifications(
        db,
        ticket,
        title="Visit rescheduled",
        message="Your visit has been rescheduled. We'll assign a new engineer shortly.",
        notification_type=NotificationType.TICKET_UPDATED
    )
    
    db.commit()
    
    return {
        "message": "Ticket rescheduled successfully",
        "ticket_id": ticket.id,
        "ticket_number": ticket.ticket_number,
        "status": ticket.status.value,
        "preferred_date": preferred_date
    }


