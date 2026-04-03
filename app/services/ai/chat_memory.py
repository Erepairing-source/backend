"""
Chat memory persistence helpers
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import uuid

from sqlalchemy.orm import Session

from app.models.ai_models import ChatSession, ChatMessage


def get_or_create_session(
    db: Session,
    user_id: Optional[int],
    role: Optional[str],
    context_type: str,
    session_id: Optional[str] = None
) -> ChatSession:
    if session_id:
        existing = db.query(ChatSession).filter(ChatSession.session_id == session_id).first()
        if existing:
            return existing

    session_id = session_id or uuid.uuid4().hex
    session = ChatSession(
        session_id=session_id,
        user_id=user_id,
        role=role,
        context_type=context_type,
        created_at=datetime.now(timezone.utc)
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def add_message(
    db: Session,
    session: ChatSession,
    sender: str,
    message: str,
    metadata: Optional[Dict[str, Any]] = None
) -> ChatMessage:
    msg = ChatMessage(
        session_id=session.id,
        sender=sender,
        message=message,
        extra_data=metadata or {}
    )
    db.add(msg)
    session.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(msg)
    return msg


def get_recent_messages(
    db: Session,
    session: ChatSession,
    limit: int = 10
) -> List[ChatMessage]:
    return (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
        .all()[::-1]
    )
