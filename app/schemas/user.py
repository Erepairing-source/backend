"""
User schemas
"""
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
from app.models.user import UserRole


class UserBase(BaseModel):
    email: EmailStr
    phone: str
    full_name: str
    role: UserRole


class UserCreate(UserBase):
    password: Optional[str] = None  # If omitted, set-password link is sent by email (all roles)
    organization_id: Optional[int] = None
    country_id: Optional[int] = None
    country_code: Optional[str] = None  # ISO2/3 when country list has no DB id (e.g. IN)
    state_id: Optional[int] = None
    state_name: Optional[str] = None
    state_code: Optional[str] = None
    city_id: Optional[int] = None
    city_name: Optional[str] = None
    engineer_skill_level: Optional[str] = None
    engineer_specialization: Optional[List[str]] = None


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    full_name: Optional[str] = None
    password: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    is_available: Optional[bool] = None
    country_id: Optional[int] = None
    country_code: Optional[str] = None
    state_id: Optional[int] = None
    state_name: Optional[str] = None
    state_code: Optional[str] = None
    city_id: Optional[int] = None
    city_name: Optional[str] = None
    engineer_skill_level: Optional[str] = None
    engineer_specialization: Optional[List[str]] = None
    current_location_lat: Optional[str] = None
    current_location_lng: Optional[str] = None


class UserResponse(UserBase):
    id: int
    organization_id: Optional[int] = None
    country_id: Optional[int] = None
    state_id: Optional[int] = None
    city_id: Optional[int] = None
    state_name: Optional[str] = None
    city_name: Optional[str] = None
    is_available: Optional[bool] = None
    engineer_skill_level: Optional[str] = None
    engineer_specialization: Optional[str] = None
    is_active: bool
    is_verified: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


