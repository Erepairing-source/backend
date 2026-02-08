"""
Integration models for external systems
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.core.database import Base


class IntegrationType(str, enum.Enum):
    """Integration types"""
    ERP = "erp"  # Enterprise Resource Planning
    CRM = "crm"  # Customer Relationship Management
    WAREHOUSE = "warehouse"
    PAYMENT_GATEWAY = "payment_gateway"
    SMS_PROVIDER = "sms_provider"
    EMAIL_PROVIDER = "email_provider"
    WEBHOOK = "webhook"
    API = "api"
    IOT = "iot"


class IntegrationStatus(str, enum.Enum):
    """Integration status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    TESTING = "testing"


class Integration(Base):
    """External system integration"""
    __tablename__ = "integrations"
    
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    
    # Integration details
    name = Column(String(255), nullable=False)
    integration_type = Column(Enum(IntegrationType), nullable=False)
    provider = Column(String(100), nullable=True)  # e.g., "SAP", "Salesforce"
    
    # Configuration
    config = Column(JSON, default=dict)  # Encrypted credentials and settings
    webhook_url = Column(String(500), nullable=True)
    api_endpoint = Column(String(500), nullable=True)
    
    # Sync settings
    sync_direction = Column(String(50), default="bidirectional")  # inbound, outbound, bidirectional
    sync_frequency = Column(String(50), default="realtime")  # realtime, hourly, daily
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    
    # Status
    status = Column(Enum(IntegrationStatus), default=IntegrationStatus.INACTIVE)
    is_active = Column(Boolean, default=False)
    
    # Error tracking
    last_error = Column(Text, nullable=True)
    error_count = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    organization = relationship("Organization", back_populates="integrations")
    
    def __repr__(self):
        return f"<Integration {self.name} ({self.integration_type})>"



