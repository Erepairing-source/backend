"""
Ticket schemas
"""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.models.ticket import TicketStatus, TicketPriority


class TicketBase(BaseModel):
    customer_name: str
    customer_company: str
    customer_phone: str
    issue_description: Optional[str] = None
    device_id: Optional[int] = None
    service_address: Optional[str] = None
    priority: Optional[TicketPriority] = TicketPriority.MEDIUM


class TicketCreate(TicketBase):
    issue_photos: Optional[List[str]] = None
    service_latitude: Optional[str] = None
    service_longitude: Optional[str] = None


class TicketUpdate(BaseModel):
    status: Optional[TicketStatus] = None
    assigned_engineer_id: Optional[int] = None
    resolution_notes: Optional[str] = None
    parts_used: Optional[List[dict]] = None


class TicketResponse(TicketBase):
    id: int
    ticket_number: str
    status: TicketStatus
    priority: TicketPriority
    created_at: datetime
    
    class Config:
        from_attributes = True




