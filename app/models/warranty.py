"""
Warranty models
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Text, Float, Boolean, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.core.database import Base


class WarrantyStatus(str, enum.Enum):
    """Warranty status"""
    ACTIVE = "active"
    EXPIRED = "expired"
    VOID = "void"
    EXTENDED = "extended"


class Warranty(Base):
    """Warranty model"""
    __tablename__ = "warranties"
    
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    
    # Warranty details
    warranty_type = Column(String(50), nullable=False)  # standard, extended, parts_only, labor_only
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=False, index=True)
    status = Column(Enum(WarrantyStatus), default=WarrantyStatus.ACTIVE, index=True)
    
    # Coverage
    covered_parts = Column(JSON, default=list)  # Array of part categories or specific parts
    covered_services = Column(JSON, default=list)  # repair, replacement, etc.
    terms_and_conditions = Column(Text, nullable=True)
    
    # Additional info
    warranty_number = Column(String(100), unique=True, index=True, nullable=True)
    invoice_number = Column(String(100), nullable=True)
    purchase_date = Column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    device = relationship("Device", back_populates="warranties")
    organization = relationship("Organization")
    claims = relationship("WarrantyClaim", back_populates="warranty")
    
    def __repr__(self):
        return f"<Warranty {self.warranty_number} ({self.status})>"


class WarrantyClaim(Base):
    """Warranty claim record"""
    __tablename__ = "warranty_claims"
    
    id = Column(Integer, primary_key=True, index=True)
    warranty_id = Column(Integer, ForeignKey("warranties.id"), nullable=False, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=True, index=True)
    
    claim_type = Column(String(50), nullable=False)  # repair, replacement, refund
    claim_amount = Column(Float, nullable=True)
    approved_amount = Column(Float, nullable=True)
    
    # Status
    status = Column(String(50), default="pending", index=True)  # pending, approved, rejected, processed
    approved_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    
    # Details
    claim_description = Column(Text, nullable=True)
    supporting_documents = Column(JSON, default=list)  # Array of document URLs
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    warranty = relationship("Warranty", back_populates="claims")
    ticket = relationship("Ticket")
    approved_by = relationship("User")




