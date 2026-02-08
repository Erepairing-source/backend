"""
Subscription and plan models
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum, Text, Float, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.core.database import Base


class PlanType(str, enum.Enum):
    """Plan type"""
    STARTER = "starter"  # SME
    GROWTH = "growth"  # SME+/SMB
    ENTERPRISE = "enterprise"


class BillingPeriod(str, enum.Enum):
    """Billing period"""
    MONTHLY = "monthly"
    ANNUAL = "annual"


class Plan(Base):
    """Subscription plan"""
    __tablename__ = "plans"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    plan_type = Column(Enum(PlanType), nullable=False, index=True)
    
    # Pricing
    monthly_price = Column(Float, nullable=False)
    annual_price = Column(Float, nullable=False)
    
    # Limits
    max_engineers = Column(Integer, nullable=True)  # None = unlimited
    max_organizations = Column(Integer, nullable=True)
    max_tickets_per_month = Column(Integer, nullable=True)
    
    # Features
    features = Column(JSON, default=dict)  # Feature flags and limits
    
    # Status
    is_active = Column(Boolean, default=True)
    is_visible = Column(Boolean, default=True)  # Show on landing page
    
    # Display
    description = Column(Text, nullable=True)
    display_order = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    subscriptions = relationship("Subscription", back_populates="plan")
    plan_features = relationship("PlanFeature", back_populates="plan", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Plan {self.name} ({self.plan_type})>"


class PlanFeature(Base):
    """Plan feature mapping"""
    __tablename__ = "plan_features"
    
    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(Integer, ForeignKey("plans.id"), nullable=False)
    feature_name = Column(String(100), nullable=False)
    feature_value = Column(JSON, nullable=True)  # Can be boolean, number, or object
    is_enabled = Column(Boolean, default=True)
    
    # Relationships
    plan = relationship("Plan", back_populates="plan_features")


class Subscription(Base):
    """Organization subscription"""
    __tablename__ = "subscriptions"
    
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, unique=True, index=True)
    plan_id = Column(Integer, ForeignKey("plans.id"), nullable=False)
    
    # Billing
    billing_period = Column(Enum(BillingPeriod), nullable=False)
    current_price = Column(Float, nullable=False)
    currency = Column(String(3), default="INR")
    
    # Dates
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=False, index=True)
    trial_end_date = Column(DateTime(timezone=True), nullable=True)
    
    # Status
    status = Column(String(50), default="active", index=True)  # active, cancelled, expired, trial
    auto_renew = Column(Boolean, default=True)
    
    # Payment
    payment_method = Column(String(50), nullable=True)
    last_payment_date = Column(DateTime(timezone=True), nullable=True)
    next_billing_date = Column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    organization = relationship("Organization", foreign_keys=[organization_id], backref="subscription_ref")
    plan = relationship("Plan", back_populates="subscriptions")
    
    def __repr__(self):
        return f"<Subscription org_id={self.organization_id} plan={self.plan.name} status={self.status}>"


class Vendor(Base):
    """Vendor/reseller model"""
    __tablename__ = "vendors"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    phone = Column(String(20), nullable=False)
    
    # Location
    country_id = Column(Integer, ForeignKey("countries.id"), nullable=True)
    state_id = Column(Integer, ForeignKey("states.id"), nullable=True)
    city_id = Column(Integer, ForeignKey("cities.id"), nullable=True)
    
    # Vendor details
    vendor_code = Column(String(50), unique=True, index=True, nullable=False)
    commission_rate = Column(Float, default=0.15)  # 15% default
    is_active = Column(Boolean, default=True)
    
    # User account (vendor admin)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, unique=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    country = relationship("Country")
    state = relationship("State")
    city = relationship("City")
    user = relationship("User")
    vendor_organizations = relationship("VendorOrganization", back_populates="vendor")
    
    def __repr__(self):
        return f"<Vendor {self.name} ({self.vendor_code})>"


class VendorOrganization(Base):
    """Vendor-Organization relationship (tracks which orgs were signed up by which vendor)"""
    __tablename__ = "vendor_organizations"
    
    id = Column(Integer, primary_key=True, index=True)
    vendor_id = Column(Integer, ForeignKey("vendors.id"), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, unique=True, index=True)
    
    # Signup details
    signup_date = Column(DateTime(timezone=True), server_default=func.now())
    commission_earned = Column(Float, default=0.0)
    last_commission_date = Column(DateTime(timezone=True), nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    vendor = relationship("Vendor", back_populates="vendor_organizations")
    organization = relationship("Organization", back_populates="vendor_organizations")
    
    def __repr__(self):
        return f"<VendorOrganization vendor_id={self.vendor_id} org_id={self.organization_id}>"

