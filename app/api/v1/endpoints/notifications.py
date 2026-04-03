"""
Notification endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from app.core.database import get_db
from app.core.permissions import get_current_user
from app.models.user import User
from app.models.notification import Notification, NotificationStatus

router = APIRouter()


@router.get("/")
async def list_notifications(
    unread_only: bool = False,
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List notifications for current user"""
    query = db.query(Notification).filter(Notification.user_id == current_user.id)
    if unread_only:
        query = query.filter(Notification.read_at.is_(None))
    notifications = query.order_by(Notification.created_at.desc()).limit(limit).all()

    return [
        {
            "id": n.id,
            "title": n.title,
            "message": n.message,
            "notification_type": n.notification_type.value,
            "channel": n.channel.value,
            "status": n.status.value,
            "ticket_id": n.ticket_id,
            "device_id": n.device_id,
            "action_url": n.action_url,
            "created_at": n.created_at.isoformat() if n.created_at else None,
            "read_at": n.read_at.isoformat() if n.read_at else None
        }
        for n in notifications
    ]


@router.post("/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark a notification as read"""
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id
    ).first()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    notification.read_at = datetime.utcnow()
    notification.status = NotificationStatus.READ
    db.commit()
    return {"message": "Notification marked as read"}


@router.post("/dispatch")
async def dispatch_notifications(
    dispatch_data: dict = Body(default={}),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Simulate dispatch of pending notifications (SMS/WhatsApp/In-app)"""
    channel = dispatch_data.get("channel")
    query = db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.status == NotificationStatus.PENDING
    )
    if channel:
        query = query.filter(Notification.channel == channel)
    notifications = query.all()
    for notification in notifications:
        notification.status = NotificationStatus.SENT
        notification.sent_at = datetime.utcnow()
    db.commit()
    return {"message": f"Dispatched {len(notifications)} notifications"}
