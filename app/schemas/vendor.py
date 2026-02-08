"""
Vendor schemas
"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class VendorBase(BaseModel):
    name: str
    email: str
    phone: str


class VendorCreate(VendorBase):
    country_id: Optional[int] = None
    state_id: Optional[int] = None
    city_id: Optional[int] = None
    commission_rate: float = 0.15


class VendorResponse(VendorBase):
    id: int
    vendor_code: str
    commission_rate: float
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True




