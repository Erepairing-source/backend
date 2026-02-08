"""
AI service endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.database import get_db
from app.core.permissions import get_current_user, require_role
from app.models.user import User
from app.services.ai.chat_memory import get_or_create_session, add_message, get_recent_messages
from app.services.ai.case_triage import CaseTriageService
from app.services.ai.demand_forecasting import DemandForecastingService
from app.services.ai.knowledge_assistant import KnowledgeAssistantService
from app.services.ai.chatbot import MultilingualChatbotService
from app.services.ai.sentiment_analyzer import SentimentAnalyzerService
from app.services.ai.route_optimization import RouteOptimizationService
from app.services.ai.load_balancer import LoadBalancerService
from app.services.ai.role_assistant import RoleAssistantService
from app.services.ai.self_diagnosis import SelfDiagnosisService
from app.services.ai.photo_quality import check_photo_quality
from app.services.ai.insights import (
    build_ticket_summary,
    build_checklist,
    build_parts_suggestions,
    build_sla_risk_explanation,
    predict_satisfaction_risk,
    generate_auto_notes
)
from app.models.ticket import Ticket, TicketComment, TicketStatus
from app.models.user import UserRole
from app.models.ai_models import AIKnowledgeBase
from app.services.ai.role_assistant import ROLE_GUIDES
from app.models.notification import Notification, NotificationType, NotificationChannel, NotificationStatus

router = APIRouter()

triage_service = CaseTriageService()
forecast_service = DemandForecastingService()
knowledge_service = KnowledgeAssistantService()
chatbot_service = MultilingualChatbotService()
sentiment_service = SentimentAnalyzerService()
route_service = RouteOptimizationService()
load_balancer_service = LoadBalancerService()
role_assistant_service = RoleAssistantService()
self_diagnosis_service = SelfDiagnosisService()


def _notify_customer_for_ticket(
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


@router.post("/triage")
async def ai_triage(
    triage_data: dict = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """AI Case Triage - accepts JSON body with issue_description, issue_photos, device_category, device_model"""
    issue_description = triage_data.get("issue_description", "")
    issue_photos = triage_data.get("issue_photos")
    device_category = triage_data.get("device_category")
    device_model = triage_data.get("device_model")
    
    if not issue_description:
        raise HTTPException(status_code=400, detail="issue_description is required")
    
    result = await triage_service.triage_ticket(
        issue_description=issue_description,
        issue_photos=issue_photos,
        device_category=device_category,
        device_model=device_model
    )
    return result


@router.post("/forecast")
async def forecast_demand(
    part_id: int,
    city_id: Optional[int] = None,
    state_id: Optional[int] = None,
    forecast_days: int = 30,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Parts Demand Forecasting"""
    result = await forecast_service.forecast_demand(
        part_id=part_id,
        city_id=city_id,
        state_id=state_id,
        organization_id=current_user.organization_id,
        forecast_days=forecast_days
    )
    return result


@router.post("/copilot/query")
async def knowledge_assistant(
    query: str,
    device_category: Optional[str] = None,
    device_model: Optional[str] = None,
    language: str = "en",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """AI Knowledge Assistant (Copilot)"""
    result = await knowledge_service.answer_query(
        query=query,
        device_category=device_category,
        device_model=device_model,
        language=language,
        db=db,
        role=current_user.role.value
    )
    return result


@router.post("/chatbot/message")
async def chatbot_message(
    message: str,
    session_id: str = "",
    language: str = "en",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Multilingual Chatbot"""
    session = get_or_create_session(
        db,
        user_id=current_user.id,
        role=current_user.role.value,
        context_type="chatbot",
        session_id=session_id or None
    )
    add_message(db, session, "user", message)
    history = get_recent_messages(db, session, limit=10)
    result = await chatbot_service.process_message(
        message=message,
        user_id=current_user.id,
        session_id=session.session_id,
        language=language,
        history=[{"role": m.sender, "text": m.message} for m in history]
    )
    add_message(db, session, "assistant", result.get("response", ""))
    result["session_id"] = session.session_id
    return result


@router.post("/chatbot/reschedule")
async def chatbot_reschedule_ticket(
    payload: dict = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Reschedule ticket via chatbot for customers"""
    if current_user.role != UserRole.CUSTOMER:
        raise HTTPException(status_code=403, detail="Only customers can reschedule tickets")

    ticket_id = payload.get("ticket_id")
    preferred_date = payload.get("preferred_date")
    reason = payload.get("reason", "Customer requested reschedule via chatbot")
    service_address = payload.get("service_address")
    service_latitude = payload.get("service_latitude")
    service_longitude = payload.get("service_longitude")

    if not ticket_id:
        raise HTTPException(status_code=400, detail="ticket_id is required")

    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.customer_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only reschedule your own tickets")
    if ticket.status != TicketStatus.ASSIGNED:
        raise HTTPException(status_code=400, detail="Only assigned tickets can be rescheduled")

    # Log reschedule comment
    comment = TicketComment(
        ticket_id=ticket.id,
        user_id=current_user.id,
        comment_text=f"Reschedule requested via chatbot. Reason: {reason}. Preferred date: {preferred_date}",
        comment_type="reschedule_request",
        extra_data={
            "reschedule_reason": reason,
            "preferred_date": preferred_date,
            "new_service_address": service_address or ticket.service_address
        }
    )
    db.add(comment)

    ticket.service_address = service_address or ticket.service_address
    ticket.service_latitude = service_latitude or ticket.service_latitude
    ticket.service_longitude = service_longitude or ticket.service_longitude
    ticket.assigned_engineer_id = None
    ticket.assigned_by_id = None
    ticket.assigned_at = None
    ticket.status = TicketStatus.CREATED

    if preferred_date:
        try:
            from datetime import datetime
            preferred_dt = datetime.fromisoformat(preferred_date.replace('Z', '+00:00'))
            ticket.sla_deadline = preferred_dt
        except Exception:
            pass

    _notify_customer_for_ticket(
        db,
        ticket,
        title="Visit rescheduled",
        message="Your visit has been rescheduled via chatbot.",
        notification_type=NotificationType.TICKET_UPDATED
    )

    db.commit()
    return {"message": "Ticket rescheduled successfully", "ticket_id": ticket.id}


@router.post("/sentiment/analyze")
async def analyze_sentiment(
    text: str,
    rating: Optional[int] = None,
    language: str = "en",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Customer Sentiment Analysis"""
    result = await sentiment_service.analyze_feedback(
        feedback_text=text,
        rating=rating,
        language=language
    )
    return result


@router.post("/route/optimize")
async def optimize_route(
    engineer_id: int,
    ticket_ids: List[int],
    engineer_location: tuple,
    ticket_locations: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Route Optimization"""
    result = await route_service.optimize_routes(
        engineer_id=engineer_id,
        ticket_ids=ticket_ids,
        engineer_location=engineer_location,
        ticket_locations=ticket_locations
    )
    return result


@router.post("/load-balance")
async def balance_workload(
    engineers: List[dict],
    pending_tickets: List[dict],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Predictive Load Balancing"""
    result = await load_balancer_service.balance_workload(
        engineers=engineers,
        pending_tickets=pending_tickets
    )
    return result


@router.post("/role-assistant")
async def role_assistant(
    payload: dict = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Role-based dashboard assistant"""
    message = payload.get("message", "")
    role = payload.get("role") or current_user.role.value
    page = payload.get("page")
    session_id = payload.get("session_id")

    if db.query(AIKnowledgeBase).count() == 0:
        for role_key, guide in ROLE_GUIDES.items():
            entry = AIKnowledgeBase(
                title=f"{guide['role_name']} Guide",
                content=guide["overview"] + "\n" + "\n".join(guide["access"]),
                tags=["role", role_key],
                role=role_key,
                source="role_guides"
            )
            db.add(entry)
        db.commit()

    result = role_assistant_service.answer(
        role=role,
        message=message,
        page=page,
        session_id=session_id,
        db=db,
        user_id=current_user.id
    )
    return result


@router.post("/self-diagnosis/questions")
async def self_diagnosis_questions(
    payload: dict = Body(default={}),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    device_category = payload.get("device_category")
    questions = self_diagnosis_service.get_questions(device_category=device_category)
    return {"questions": questions}


@router.post("/self-diagnosis/assess")
async def self_diagnosis_assess(
    payload: dict = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    issue_description = payload.get("issue_description", "")
    answers = payload.get("answers") or {}
    assessment = self_diagnosis_service.assess(answers)
    assessment["probable_parts"] = self_diagnosis_service.suggest_parts(assessment.get("signals", []))

    combined_text = issue_description + " " + " ".join([f"{k}:{v}" for k, v in answers.items()])
    triage = await triage_service.triage_ticket(
        issue_description=combined_text,
        issue_photos=None,
        device_category=payload.get("device_category"),
        device_model=payload.get("device_model")
    )

    return {
        "assessment": assessment,
        "triage": triage
    }


@router.post("/tickets/auto-summary")
async def ticket_auto_summary(
    payload: dict = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Convert free-text into structured issue + priority"""
    issue_description = payload.get("issue_description", "")
    if not issue_description:
        raise HTTPException(status_code=400, detail="issue_description is required")
    triage = await triage_service.triage_ticket(
        issue_description=issue_description,
        issue_photos=payload.get("issue_photos") or [],
        device_category=payload.get("device_category"),
        device_model=payload.get("device_model")
    )
    return {
        "issue_category": triage.get("suggested_category"),
        "priority": triage.get("suggested_priority"),
        "summary": triage.get("summary"),
        "key_symptoms": triage.get("key_symptoms", [])
    }


@router.post("/knowledge-base/upsert")
async def upsert_knowledge_base(
    payload: dict = Body(...),
    current_user: User = Depends(require_role([UserRole.PLATFORM_ADMIN])),
    db: Session = Depends(get_db)
):
    """Create or update knowledge base entry"""
    entry_id = payload.get("id")
    title = payload.get("title")
    content = payload.get("content")
    if not title or not content:
        raise HTTPException(status_code=400, detail="title and content are required")

    if entry_id:
        entry = db.query(AIKnowledgeBase).filter(AIKnowledgeBase.id == entry_id).first()
        if not entry:
            raise HTTPException(status_code=404, detail="Entry not found")
        entry.title = title
        entry.content = content
        entry.tags = payload.get("tags", entry.tags)
        entry.role = payload.get("role", entry.role)
        entry.source = payload.get("source", entry.source)
        entry.is_active = payload.get("is_active", entry.is_active)
    else:
        entry = AIKnowledgeBase(
            title=title,
            content=content,
            tags=payload.get("tags", []),
            role=payload.get("role"),
            source=payload.get("source"),
            is_active=payload.get("is_active", True)
        )
        db.add(entry)

    db.commit()
    db.refresh(entry)
    return {"id": entry.id, "title": entry.title}


@router.post("/knowledge-base/search")
async def search_knowledge_base(
    payload: dict = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = payload.get("query", "")
    if not query:
        raise HTTPException(status_code=400, detail="query is required")
    entries = db.query(AIKnowledgeBase).filter(AIKnowledgeBase.is_active == True).limit(20).all()
    results = []
    for entry in entries:
        if query.lower() in entry.content.lower() or query.lower() in entry.title.lower():
            results.append({
                "id": entry.id,
                "title": entry.title,
                "source": entry.source,
                "role": entry.role
            })
    return results


@router.get("/knowledge-base")
async def list_knowledge_base(
    current_user: User = Depends(require_role([UserRole.PLATFORM_ADMIN])),
    db: Session = Depends(get_db)
):
    entries = db.query(AIKnowledgeBase).order_by(AIKnowledgeBase.created_at.desc()).all()
    return [
        {
            "id": e.id,
            "title": e.title,
            "role": e.role,
            "tags": e.tags,
            "source": e.source,
            "is_active": e.is_active
        }
        for e in entries
    ]


@router.get("/knowledge-base/{entry_id}")
async def get_knowledge_base_entry(
    entry_id: int,
    current_user: User = Depends(require_role([UserRole.PLATFORM_ADMIN])),
    db: Session = Depends(get_db)
):
    entry = db.query(AIKnowledgeBase).filter(AIKnowledgeBase.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    return {
        "id": entry.id,
        "title": entry.title,
        "content": entry.content,
        "role": entry.role,
        "tags": entry.tags,
        "source": entry.source,
        "is_active": entry.is_active
    }


@router.delete("/knowledge-base/{entry_id}")
async def delete_knowledge_base(
    entry_id: int,
    current_user: User = Depends(require_role([UserRole.PLATFORM_ADMIN])),
    db: Session = Depends(get_db)
):
    entry = db.query(AIKnowledgeBase).filter(AIKnowledgeBase.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    db.delete(entry)
    db.commit()
    return {"message": "Deleted"}


def _get_ticket_with_access(ticket_id: int, current_user: User, db: Session) -> Ticket:
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if current_user.role == UserRole.CUSTOMER and ticket.customer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    if current_user.role == UserRole.SUPPORT_ENGINEER and ticket.assigned_engineer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    if current_user.organization_id and ticket.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return ticket


@router.post("/tickets/summary")
async def ticket_summary(
    payload: dict = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    ticket_id = payload.get("ticket_id")
    if not ticket_id:
        raise HTTPException(status_code=400, detail="ticket_id is required")
    ticket = _get_ticket_with_access(ticket_id, current_user, db)
    return build_ticket_summary(ticket)


@router.post("/tickets/checklist")
async def ticket_checklist(
    payload: dict = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    ticket_id = payload.get("ticket_id")
    if not ticket_id:
        raise HTTPException(status_code=400, detail="ticket_id is required")
    ticket = _get_ticket_with_access(ticket_id, current_user, db)
    return build_checklist(ticket)


@router.post("/tickets/parts-suggestions")
async def ticket_parts_suggestions(
    payload: dict = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    ticket_id = payload.get("ticket_id")
    if not ticket_id:
        raise HTTPException(status_code=400, detail="ticket_id is required")
    ticket = _get_ticket_with_access(ticket_id, current_user, db)
    return build_parts_suggestions(ticket)


@router.post("/tickets/sla-risk")
async def ticket_sla_risk(
    payload: dict = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    ticket_id = payload.get("ticket_id")
    if not ticket_id:
        raise HTTPException(status_code=400, detail="ticket_id is required")
    ticket = _get_ticket_with_access(ticket_id, current_user, db)
    return build_sla_risk_explanation(ticket)


@router.post("/tickets/satisfaction-risk")
async def ticket_satisfaction_risk(
    payload: dict = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    ticket_id = payload.get("ticket_id")
    if not ticket_id:
        raise HTTPException(status_code=400, detail="ticket_id is required")
    ticket = _get_ticket_with_access(ticket_id, current_user, db)
    return predict_satisfaction_risk(ticket)


@router.post("/tickets/auto-notes")
async def ticket_auto_notes(
    payload: dict = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    ticket_id = payload.get("ticket_id")
    if not ticket_id:
        raise HTTPException(status_code=400, detail="ticket_id is required")
    ticket = _get_ticket_with_access(ticket_id, current_user, db)
    return generate_auto_notes(ticket)


@router.post("/photos/quality")
async def photo_quality_check(
    payload: dict = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    urls = payload.get("urls") or []
    if not isinstance(urls, list):
        raise HTTPException(status_code=400, detail="urls must be a list")
    return check_photo_quality(urls)




