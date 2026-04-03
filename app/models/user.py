"""
User and Role models
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.core.database import Base


class UserRole(str, enum.Enum):
    """User role types"""
    CUSTOMER = "customer"
    SUPPORT_ENGINEER = "support_engineer"
    CITY_ADMIN = "city_admin"
    STATE_ADMIN = "state_admin"
    COUNTRY_ADMIN = "country_admin"
    ORGANIZATION_ADMIN = "organization_admin"
    PLATFORM_ADMIN = "platform_admin"
    VENDOR = "vendor"


class User(Base):
    """User model"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    phone = Column(String(20), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    
    # Role and organization
    role = Column(Enum(UserRole), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    
    # Location hierarchy
    country_id = Column(Integer, ForeignKey("countries.id"), nullable=True)
    state_id = Column(Integer, ForeignKey("states.id"), nullable=True)
    city_id = Column(Integer, ForeignKey("cities.id"), nullable=True)
    
    # Engineer specific
    engineer_skill_level = Column(String(50), nullable=True)  # junior, senior, expert
    engineer_specialization = Column(Text, nullable=True)  # JSON array of product categories
    is_available = Column(Boolean, default=True)
    current_location_lat = Column(String(20), nullable=True)
    current_location_lng = Column(String(20), nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    last_login = Column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    organization = relationship("Organization", back_populates="users")
    country = relationship("Country", back_populates="users")
    state = relationship("State", back_populates="users")
    city = relationship("City", back_populates="users")
    assigned_tickets = relationship("Ticket", foreign_keys="Ticket.assigned_engineer_id", back_populates="assigned_engineer")
    notifications = relationship("Notification", back_populates="user")
    created_tickets = relationship("Ticket", foreign_keys="Ticket.created_by_id", back_populates="created_by")
    
    def __repr__(self):
        return f"<User {self.email} ({self.role})>"


