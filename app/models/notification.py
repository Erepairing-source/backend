"""
Notification models for real-time updates
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.core.database import Base


class NotificationType(str, enum.Enum):
    """Notification types"""
    TICKET_CREATED = "ticket_created"
    TICKET_ASSIGNED = "ticket_assigned"
    TICKET_UPDATED = "ticket_updated"
    TICKET_RESOLVED = "ticket_resolved"
    SLA_BREACH_WARNING = "sla_breach_warning"
    ESCALATION = "escalation"
    INVENTORY_LOW = "inventory_low"
    PART_ORDERED = "part_ordered"
    ENGINEER_ETA = "engineer_eta"
    FEEDBACK_RECEIVED = "feedback_received"
    SYSTEM_ALERT = "system_alert"


class NotificationChannel(str, enum.Enum):
    """Notification channels"""
    IN_APP = "in_app"
    EMAIL = "email"
    SMS = "sms"
    WHATSAPP = "whatsapp"
    PUSH = "push"


class NotificationStatus(str, enum.Enum):
    """Notification status"""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


class Notification(Base):
    """User notification"""
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    
    # Recipient
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Notification details
    notification_type = Column(Enum(NotificationType), nullable=False, index=True)
    channel = Column(Enum(NotificationChannel), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    
    # Related entities
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=True)
    
    # Status
    status = Column(Enum(NotificationStatus), default=NotificationStatus.PENDING, index=True)
    read_at = Column(DateTime(timezone=True), nullable=True)
    
    # Additional data
    extra_data = Column(JSON, default=dict)  # Additional data (renamed from metadata to avoid SQLAlchemy conflict)
    action_url = Column(String(500), nullable=True)  # Deep link
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    organization = relationship("Organization", back_populates="notifications")
    user = relationship("User", back_populates="notifications")
    ticket = relationship("Ticket", back_populates="notifications")
    
    def __repr__(self):
        return f"<Notification {self.notification_type} to {self.user_id}>"

