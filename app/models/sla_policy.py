"""
SLA and Service Policy models
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum, Text, Integer as IntCol, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.core.database import Base


class SLAType(str, enum.Enum):
    """SLA type"""
    FIRST_RESPONSE = "first_response"  # Time to first response
    ASSIGNMENT = "assignment"  # Time to assign engineer
    RESOLUTION = "resolution"  # Time to resolve
    ON_SITE = "on_site"  # Time to reach customer location


class SLAPolicy(Base):
    """SLA Policy per product/region"""
    __tablename__ = "sla_policies"
    
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    
    # Scope
    product_category = Column(String(100), nullable=True)  # null = all products
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    country_id = Column(Integer, ForeignKey("countries.id"), nullable=True)
    state_id = Column(Integer, ForeignKey("states.id"), nullable=True)
    city_id = Column(Integer, ForeignKey("cities.id"), nullable=True)
    
    # SLA Rules
    sla_type = Column(Enum(SLAType), nullable=False)
    target_hours = Column(IntCol, nullable=False)  # Target time in hours
    
    # Priority-based overrides
    priority_overrides = Column(JSON, default=dict)  # {priority: hours}
    
    # Business hours
    business_hours_only = Column(Boolean, default=False)
    business_hours = Column(JSON, default=dict)  # {day: {start, end}}
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    organization = relationship("Organization", back_populates="sla_policies")
    product = relationship("Product")
    
    def __repr__(self):
        return f"<SLAPolicy {self.sla_type} - {self.target_hours}h>"


class ServicePolicy(Base):
    """Service rules and policies"""
    __tablename__ = "service_policies"
    
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    
    # Policy type
    policy_type = Column(String(100), nullable=False)  # warranty, chargeable, parts, etc.
    
    # Rules
    rules = Column(JSON, default=dict)  # Flexible rule structure
    
    # Scope
    product_category = Column(String(100), nullable=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    country_id = Column(Integer, ForeignKey("countries.id"), nullable=True)
    state_id = Column(Integer, ForeignKey("states.id"), nullable=True)
    city_id = Column(Integer, ForeignKey("cities.id"), nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    organization = relationship("Organization", back_populates="service_policies")
    
    def __repr__(self):
        return f"<ServicePolicy {self.policy_type}>"



