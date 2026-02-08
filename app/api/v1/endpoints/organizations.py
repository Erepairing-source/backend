"""
Organization endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from sqlalchemy import func

from app.core.database import get_db
from app.core.permissions import get_current_user, require_role
from app.models.user import User, UserRole
from app.models.organization import Organization
from app.models.ticket import Ticket
from app.models.subscription import Subscription

router = APIRouter()


@router.get("/", response_model=List[dict])
async def list_organizations(
    current_user: User = Depends(require_role([UserRole.PLATFORM_ADMIN, UserRole.ORGANIZATION_ADMIN])),
    db: Session = Depends(get_db)
):
    """List organizations"""
    query = db.query(Organization)
    
    if current_user.role == UserRole.ORGANIZATION_ADMIN:
        query = query.filter(Organization.id == current_user.organization_id)
    
    orgs = query.all()
    
    return [
        {
            "id": org.id,
            "name": org.name,
            "org_type": org.org_type.value,
            "email": org.email,
            "is_active": org.is_active
        }
        for org in orgs
    ]


@router.get("/{organization_id}")
async def get_organization(
    organization_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get organization details"""
    org = db.query(Organization).filter(Organization.id == organization_id).first()
    
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    # Check access
    if current_user.role != UserRole.PLATFORM_ADMIN:
        if current_user.organization_id != organization_id:
            raise HTTPException(status_code=403, detail="Access denied")
    
    return {
        "id": org.id,
        "name": org.name,
        "org_type": org.org_type.value,
        "feature_flags": org.feature_flags,
        "sla_config": org.sla_config
    }


@router.get("/me/stats")
async def get_organization_stats(
    current_user: User = Depends(require_role([UserRole.ORGANIZATION_ADMIN])),
    db: Session = Depends(get_db)
):
    """Get statistics for organization admin's organization"""
    org_id = current_user.organization_id
    
    if not org_id:
        raise HTTPException(status_code=404, detail="User is not associated with an organization")
    
    # Get organization
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    # Count tickets by status
    ticket_counts = db.query(
        Ticket.status,
        func.count(Ticket.id).label('count')
    ).filter(
        Ticket.organization_id == org_id
    ).group_by(Ticket.status).all()
    
    ticket_stats = {status.value: count for status, count in ticket_counts}
    
    # Count users by role
    user_counts = db.query(
        User.role,
        func.count(User.id).label('count')
    ).filter(
        User.organization_id == org_id
    ).group_by(User.role).all()
    
    user_stats = {role.value: count for role, count in user_counts}
    
    # Get subscription info
    subscription = db.query(Subscription).filter(
        Subscription.organization_id == org_id
    ).first()
    
    # Count total tickets
    total_tickets = db.query(func.count(Ticket.id)).filter(
        Ticket.organization_id == org_id
    ).scalar() or 0
    
    # Count active engineers
    active_engineers = db.query(func.count(User.id)).filter(
        User.organization_id == org_id,
        User.role == UserRole.SUPPORT_ENGINEER,
        User.is_active == True
    ).scalar() or 0
    
    return {
        "organization": {
            "id": org.id,
            "name": org.name,
            "email": org.email,
            "org_type": org.org_type.value
        },
        "tickets": {
            "total": total_tickets,
            "by_status": ticket_stats
        },
        "users": {
            "total": sum(user_stats.values()),
            "by_role": user_stats,
            "active_engineers": active_engineers
        },
        "subscription": {
            "plan_name": subscription.plan.name if subscription and subscription.plan else None,
            "status": subscription.status if subscription else None,
            "end_date": subscription.end_date.isoformat() if subscription and subscription.end_date else None
        } if subscription else None
    }
