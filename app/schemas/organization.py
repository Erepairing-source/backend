"""
Organization schemas
"""
from pydantic import BaseModel
from typing import Optional, Dict
from app.models.organization import OrganizationType


class OrganizationBase(BaseModel):
    name: str
    org_type: OrganizationType
    email: str
    phone: str


class OrganizationCreate(OrganizationBase):
    address: Optional[str] = None
    country_id: Optional[int] = None
    state_id: Optional[int] = None
    city_id: Optional[int] = None


class OrganizationResponse(OrganizationBase):
    id: int
    feature_flags: Dict
    is_active: bool
    
    class Config:
        from_attributes = True




