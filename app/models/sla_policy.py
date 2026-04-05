"""
SLA and Service Policy models
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Integer as IntCol, JSON, TypeDecorator
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.core.database import Base


class SLAType(str, enum.Enum):
    """SLA type.

    String values match MySQL native ENUM labels used in production (uppercase).
    API and frontend use lowercase slugs via coerce_sla_type / sla_type_to_api.
    """

    FIRST_RESPONSE = "FIRST_RESPONSE"
    ASSIGNMENT = "ASSIGNMENT"
    RESOLUTION = "RESOLUTION"
    ON_SITE = "ON_SITE"


_SLA_SLUG_TO_ENUM = {
    "first_response": SLAType.FIRST_RESPONSE,
    "assignment": SLAType.ASSIGNMENT,
    "resolution": SLAType.RESOLUTION,
    "on_site": SLAType.ON_SITE,
}


def coerce_sla_type(raw):
    """Parse API/body value into SLAType (accepts lowercase slugs or ENUM labels)."""
    if raw is None:
        raise ValueError("sla_type is required")
    if isinstance(raw, SLAType):
        return raw
    s = str(raw).strip()
    key = s.lower().replace("-", "_")
    if key in _SLA_SLUG_TO_ENUM:
        return _SLA_SLUG_TO_ENUM[key]
    if s in SLAType.__members__:
        return SLAType[s]
    su = s.upper()
    if su in SLAType.__members__:
        return SLAType[su]
    for member in SLAType:
        if member.value == s:
            return member
    raise ValueError(f"Invalid sla_type: {raw!r}")


def sla_type_to_api(member: SLAType) -> str:
    """Stable lowercase slug for JSON (matches frontend Select values)."""
    return member.name.lower()


class CoercedSLAType(TypeDecorator):
    """
    MySQL native ENUM `slatype` stores FIRST_RESPONSE, ASSIGNMENT, …

    API sends lowercase slugs (resolution, first_response). SQLAlchemy's Enum
    bind passes lowercase strings through unchanged, which MySQL rejects.
    We always coerce and bind the canonical **string value** (e.g. RESOLUTION).

    impl is String so we never double-process through Enum(); the DB column
    stays MySQL ENUM from migrations — only the bound parameter must match.
    """

    impl = String(32)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return coerce_sla_type(value).value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, SLAType):
            return value
        return coerce_sla_type(value)


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
    sla_type = Column(CoercedSLAType(), nullable=False)
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



