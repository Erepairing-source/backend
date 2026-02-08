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
    password: str
    organization_id: Optional[int] = None
    country_id: Optional[int] = None
    state_id: Optional[int] = None
    city_id: Optional[int] = None
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
    state_id: Optional[int] = None
    city_id: Optional[int] = None
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
    is_available: Optional[bool] = None
    engineer_skill_level: Optional[str] = None
    engineer_specialization: Optional[str] = None
    is_active: bool
    is_verified: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


