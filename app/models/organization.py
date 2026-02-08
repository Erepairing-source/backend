"""
Organization models
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.core.database import Base


class OrganizationType(str, enum.Enum):
    """Organization type"""
    OEM = "oem"  # Original Equipment Manufacturer
    SERVICE_COMPANY = "service_company"  # Authorized service partner
    DEALER = "dealer"
    REPAIR_SHOP = "repair_shop"


class Organization(Base):
    """Organization model"""
    __tablename__ = "organizations"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    org_type = Column(Enum(OrganizationType), nullable=False, index=True)
    
    # Contact
    email = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=False)
    address = Column(Text, nullable=True)
    
    # Location hierarchy
    country_id = Column(Integer, ForeignKey("countries.id"), nullable=True)
    state_id = Column(Integer, ForeignKey("states.id"), nullable=True)
    city_id = Column(Integer, ForeignKey("cities.id"), nullable=True)
    
    # Parent organization (for OEM -> Service Partner relationships)
    parent_organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    
    # Configuration
    feature_flags = Column(JSON, default=dict)  # Feature toggles
    sla_config = Column(JSON, default=dict)  # SLA settings per product/region
    warranty_policy = Column(JSON, default=dict)  # Warranty rules
    
    # Subscription
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    country = relationship("Country", back_populates="organizations")
    state = relationship("State", back_populates="organizations")
    city = relationship("City", back_populates="organizations")
    parent_organization = relationship("Organization", remote_side=[id], backref="child_organizations")
    users = relationship("User", back_populates="organization")
    tickets = relationship("Ticket", back_populates="organization")
    subscription = relationship("Subscription", foreign_keys=[subscription_id], backref="organization_ref", uselist=False)
    vendor_organizations = relationship("VendorOrganization", back_populates="organization")
    products = relationship("Product", back_populates="organization")
    sla_policies = relationship("SLAPolicy", back_populates="organization")
    service_policies = relationship("ServicePolicy", back_populates="organization")
    escalations = relationship("Escalation", back_populates="organization")
    integrations = relationship("Integration", back_populates="organization")
    notifications = relationship("Notification", back_populates="organization")
    
    def __repr__(self):
        return f"<Organization {self.name} ({self.org_type})>"


class OrganizationHierarchy(Base):
    """Organization hierarchy mapping"""
    __tablename__ = "organization_hierarchies"
    
    id = Column(Integer, primary_key=True, index=True)
    oem_organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    service_partner_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    
    # Service coverage
    product_categories = Column(JSON, default=list)  # Which products this partner handles
    service_regions = Column(JSON, default=list)  # Which cities/states
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    oem = relationship("Organization", foreign_keys=[oem_organization_id])
    service_partner = relationship("Organization", foreign_keys=[service_partner_id])

