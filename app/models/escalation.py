"""
Escalation models
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.core.database import Base


class EscalationLevel(str, enum.Enum):
    """Escalation levels"""
    CITY = "city"
    STATE = "state"
    COUNTRY = "country"
    ORGANIZATION = "organization"
    PLATFORM = "platform"


class EscalationType(str, enum.Enum):
    """Escalation types"""
    SLA_BREACH = "sla_breach"
    REPEATED_COMPLAINT = "repeated_complaint"
    NEGATIVE_SENTIMENT = "negative_sentiment"
    TECHNICAL_ISSUE = "technical_issue"
    PARTS_UNAVAILABLE = "parts_unavailable"
    UNSAFE_CONDITION = "unsafe_condition"
    FRAUD_SUSPICION = "fraud_suspicion"
    CUSTOMER_REQUEST = "customer_request"
    OTHER = "other"


class EscalationStatus(str, enum.Enum):
    """Escalation status"""
    PENDING = "pending"
    ACKNOWLEDGED = "acknowledged"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class Escalation(Base):
    """Ticket or issue escalation"""
    __tablename__ = "escalations"
    
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    
    # Related entities
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=True)
    
    # Escalation details
    escalation_type = Column(Enum(EscalationType), nullable=False)
    escalation_level = Column(Enum(EscalationLevel), nullable=False)
    reason = Column(Text, nullable=False)
    
    # Assignment
    escalated_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    assigned_to_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Status
    status = Column(Enum(EscalationStatus), default=EscalationStatus.PENDING, index=True)
    
    # Resolution
    resolution_notes = Column(Text, nullable=True)
    resolved_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    
    # Additional data
    extra_data = Column(JSON, default=dict)  # Additional context (renamed from metadata to avoid SQLAlchemy conflict)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    organization = relationship("Organization", back_populates="escalations")
    ticket = relationship("Ticket", back_populates="escalations")
    escalated_by = relationship("User", foreign_keys=[escalated_by_id])
    assigned_to = relationship("User", foreign_keys=[assigned_to_id])
    
    def __repr__(self):
        return f"<Escalation {self.escalation_type} - {self.status}>"

