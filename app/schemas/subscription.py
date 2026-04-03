"""
Subscription schemas
"""
from pydantic import BaseModel
from typing import Optional, Dict
from datetime import datetime
from app.models.subscription import PlanType, BillingPeriod


class PlanBase(BaseModel):
    name: str
    plan_type: PlanType
    monthly_price: float
    annual_price: float


class PlanResponse(PlanBase):
    id: int
    max_engineers: Optional[int] = None
    features: Dict
    description: Optional[str] = None
    
    class Config:
        from_attributes = True


class SubscriptionBase(BaseModel):
    plan_id: int
    billing_period: BillingPeriod


class SubscriptionResponse(BaseModel):
    id: int
    organization_id: int
    plan: PlanResponse
    status: str
    start_date: datetime
    end_date: datetime
    
    class Config:
        from_attributes = True




