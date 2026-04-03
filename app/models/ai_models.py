"""
AI model results and predictions
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Float, JSON, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class AITriageResult(Base):
    """AI Case Triage results"""
    __tablename__ = "ai_triage_results"
    
    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=False, unique=True, index=True)
    
    # Triage results
    suggested_category = Column(String(100), nullable=True)
    suggested_priority = Column(String(50), nullable=True)
    confidence_score = Column(Float, nullable=True)
    
    # Suggested parts
    suggested_parts = Column(JSON, default=list)  # Array of {part_id, confidence, reason}
    
    # Model info
    model_version = Column(String(50), nullable=True)
    processing_time_ms = Column(Integer, nullable=True)
    
    # Input data
    input_text = Column(Text, nullable=True)
    input_images = Column(JSON, default=list)  # Array of image URLs
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    ticket = relationship("Ticket")
    
    def __repr__(self):
        return f"<AITriageResult ticket_id={self.ticket_id} category={self.suggested_category}>"


class AIPrediction(Base):
    """AI predictions (demand forecasting, SLA breach, etc.)"""
    __tablename__ = "ai_predictions"
    
    id = Column(Integer, primary_key=True, index=True)
    prediction_type = Column(String(50), nullable=False, index=True)  # demand_forecast, sla_breach, etc.
    
    # Target entity
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    part_id = Column(Integer, ForeignKey("parts.id"), nullable=True)
    city_id = Column(Integer, ForeignKey("cities.id"), nullable=True)
    state_id = Column(Integer, ForeignKey("states.id"), nullable=True)
    
    # Prediction details
    predicted_value = Column(Float, nullable=True)
    confidence_interval_lower = Column(Float, nullable=True)
    confidence_interval_upper = Column(Float, nullable=True)
    prediction_date = Column(DateTime(timezone=True), nullable=False, index=True)
    
    # Model info
    model_version = Column(String(50), nullable=True)
    input_features = Column(JSON, default=dict)
    prediction_metadata = Column(JSON, default=dict)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    organization = relationship("Organization")
    part = relationship("Part")
    city = relationship("City")
    state = relationship("State")
    
    def __repr__(self):
        return f"<AIPrediction {self.prediction_type} value={self.predicted_value}>"


class SentimentAnalysis(Base):
    """Customer sentiment analysis results"""
    __tablename__ = "sentiment_analyses"
    
    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=True, index=True)
    feedback_id = Column(Integer, nullable=True)  # If separate feedback system
    
    # Sentiment scores
    sentiment_score = Column(Float, nullable=False)  # -1 to 1
    sentiment_label = Column(String(50), nullable=False)  # positive, neutral, negative
    confidence = Column(Float, nullable=True)
    
    # Analysis details
    analyzed_text = Column(Text, nullable=False)
    key_phrases = Column(JSON, default=list)
    topics = Column(JSON, default=list)
    
    # Entity context
    engineer_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    city_id = Column(Integer, ForeignKey("cities.id"), nullable=True)
    
    # Model info
    model_version = Column(String(50), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Relationships
    ticket = relationship("Ticket")
    engineer = relationship("User")
    organization = relationship("Organization")
    city = relationship("City")
    
    def __repr__(self):
        return f"<SentimentAnalysis {self.sentiment_label} score={self.sentiment_score}>"


class AIKnowledgeBase(Base):
    """Knowledge base documents for RAG"""
    __tablename__ = "ai_knowledge_base"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    tags = Column(JSON, default=list)
    role = Column(String(50), nullable=True)
    source = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<AIKnowledgeBase {self.title}>"


class ChatSession(Base):
    """Chat session with persisted history"""
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(64), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    role = Column(String(50), nullable=True)
    context_type = Column(String(50), nullable=True)  # role_assistant, chatbot
    title = Column(String(255), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    """Chat message in a session"""
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id"), nullable=False, index=True)
    sender = Column(String(20), nullable=False)  # user, assistant, system
    message = Column(Text, nullable=False)
    extra_data = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    session = relationship("ChatSession", back_populates="messages")




