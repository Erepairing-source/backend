"""
Ticket models
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum, Text, JSON, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.core.database import Base


class TicketStatus(str, enum.Enum):
    """Ticket status"""
    CREATED = "created"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    WAITING_PARTS = "waiting_parts"
    RESOLVED = "resolved"
    CLOSED = "closed"
    CANCELLED = "cancelled"
    ESCALATED = "escalated"


class TicketPriority(str, enum.Enum):
    """Ticket priority"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class Ticket(Base):
    """Ticket model"""
    __tablename__ = "tickets"
    
    id = Column(Integer, primary_key=True, index=True)
    ticket_number = Column(String(50), unique=True, index=True, nullable=False)
    
    # Organization and customer
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=True, index=True)
    
    # Assignment
    assigned_engineer_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    assigned_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    parent_ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=True, index=True)
    
    # Location
    country_id = Column(Integer, ForeignKey("countries.id"), nullable=True)
    state_id = Column(Integer, ForeignKey("states.id"), nullable=True, index=True)
    city_id = Column(Integer, ForeignKey("cities.id"), nullable=True, index=True)
    service_address = Column(Text, nullable=False)
    service_latitude = Column(String(20), nullable=True)
    service_longitude = Column(String(20), nullable=True)
    
    # Issue details
    issue_category = Column(String(100), nullable=True, index=True)
    issue_description = Column(Text, nullable=False)
    issue_photos = Column(JSON, default=list)  # Array of photo URLs
    issue_language = Column(String(50), nullable=True)
    contact_preferences = Column(JSON, default=list)  # ["call", "whatsapp", "sms"]
    preferred_time_slots = Column(JSON, default=list)  # [{day, slot}]
    
    # Status and priority
    status = Column(Enum(TicketStatus), default=TicketStatus.CREATED, index=True)
    priority = Column(Enum(TicketPriority), default=TicketPriority.MEDIUM, index=True)
    
    # AI Triage results
    ai_triage_category = Column(String(100), nullable=True)
    ai_triage_confidence = Column(Float, nullable=True)
    ai_suggested_parts = Column(JSON, default=list)  # Array of part IDs with confidence
    
    # SLA
    sla_deadline = Column(DateTime(timezone=True), nullable=True, index=True)
    sla_breach_risk = Column(Float, nullable=True)  # 0-1 score from AI
    first_response_time = Column(DateTime(timezone=True), nullable=True)
    resolution_time = Column(DateTime(timezone=True), nullable=True)
    engineer_eta_start = Column(DateTime(timezone=True), nullable=True)
    engineer_eta_end = Column(DateTime(timezone=True), nullable=True)
    follow_up_preferred_date = Column(DateTime(timezone=True), nullable=True)
    
    # Warranty
    warranty_status = Column(String(50), nullable=True)  # in_warranty, out_of_warranty, extended
    is_chargeable = Column(Boolean, default=False)
    
    # Resolution
    resolution_notes = Column(Text, nullable=True)
    resolution_photos = Column(JSON, default=list)
    parts_used = Column(JSON, default=list)  # Array of {part_id, quantity}
    customer_signature = Column(Text, nullable=True)  # Base64 or URL
    customer_otp_verified = Column(Boolean, default=False)
    arrival_latitude = Column(String(20), nullable=True)
    arrival_longitude = Column(String(20), nullable=True)
    arrival_confirmed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Feedback
    customer_rating = Column(Integer, nullable=True)  # 1-5
    customer_feedback = Column(Text, nullable=True)
    sentiment_score = Column(Float, nullable=True)  # -1 to 1 from AI
    customer_dispute_tags = Column(JSON, default=list)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    assigned_at = Column(DateTime(timezone=True), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    organization = relationship("Organization", back_populates="tickets")
    customer = relationship("User", foreign_keys=[customer_id], backref="customer_tickets")
    device = relationship("Device", back_populates="tickets")
    assigned_engineer = relationship("User", foreign_keys=[assigned_engineer_id], back_populates="assigned_tickets")
    created_by = relationship("User", foreign_keys=[created_by_id], back_populates="created_tickets")
    parent_ticket = relationship("Ticket", remote_side=[id], backref="follow_up_tickets")
    comments = relationship("TicketComment", back_populates="ticket", cascade="all, delete-orphan")
    escalations = relationship("Escalation", back_populates="ticket")
    notifications = relationship("Notification", back_populates="ticket")
    
    def __repr__(self):
        return f"<Ticket {self.ticket_number} ({self.status})>"


class TicketComment(Base):
    """Ticket comment/activity log"""
    __tablename__ = "ticket_comments"
    
    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    comment_text = Column(Text, nullable=False)
    comment_type = Column(String(50), nullable=True)  # comment, status_change, assignment, etc.
    extra_data = Column(JSON, default=dict)  # Additional metadata (renamed from metadata to avoid SQLAlchemy conflict)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    ticket = relationship("Ticket", back_populates="comments")
    user = relationship("User")

