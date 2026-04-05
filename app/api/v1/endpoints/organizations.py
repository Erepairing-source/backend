"""
Organization endpoints
"""
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Any, Dict
from sqlalchemy import func

from app.core.database import get_db
from app.core.permissions import get_current_user, require_role
from app.models.user import User, UserRole
from app.models.organization import Organization
from app.models.ticket import Ticket
from app.models.subscription import Subscription
from app.models.sla_policy import SLAPolicy, ServicePolicy, sla_type_to_api

router = APIRouter()


@router.get("/me/stats")
async def get_organization_stats(
    current_user: User = Depends(require_role([UserRole.ORGANIZATION_ADMIN])),
    db: Session = Depends(get_db),
):
    """Get statistics for organization admin's organization"""
    org_id = current_user.organization_id

    if not org_id:
        raise HTTPException(status_code=404, detail="User is not associated with an organization")

    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    ticket_counts = (
        db.query(Ticket.status, func.count(Ticket.id).label("count"))
        .filter(Ticket.organization_id == org_id)
        .group_by(Ticket.status)
        .all()
    )

    ticket_stats = {status.value: count for status, count in ticket_counts}

    user_counts = (
        db.query(User.role, func.count(User.id).label("count"))
        .filter(User.organization_id == org_id)
        .group_by(User.role)
        .all()
    )

    user_stats = {role.value: count for role, count in user_counts}

    subscription = db.query(Subscription).filter(Subscription.organization_id == org_id).first()

    total_tickets = db.query(func.count(Ticket.id)).filter(Ticket.organization_id == org_id).scalar() or 0

    active_engineers = (
        db.query(func.count(User.id))
        .filter(
            User.organization_id == org_id,
            User.role == UserRole.SUPPORT_ENGINEER,
            User.is_active == True,  # noqa: E712
        )
        .scalar()
        or 0
    )

    return {
        "organization": {
            "id": org.id,
            "name": org.name,
            "email": org.email,
            "org_type": org.org_type.value,
        },
        "tickets": {"total": total_tickets, "by_status": ticket_stats},
        "users": {
            "total": sum(user_stats.values()),
            "by_role": user_stats,
            "active_engineers": active_engineers,
        },
        "subscription": {
            "plan_name": subscription.plan.name if subscription and subscription.plan else None,
            "status": subscription.status if subscription else None,
            "end_date": subscription.end_date.isoformat() if subscription and subscription.end_date else None,
        }
        if subscription
        else None,
    }


@router.get("/me/sla-policies")
async def list_customer_org_sla_policies(
    current_user: User = Depends(require_role([UserRole.CUSTOMER])),
    db: Session = Depends(get_db),
):
    """Active SLA policies for the customer's organization (read-only, for transparency)."""
    if not current_user.organization_id:
        return []

    policies = (
        db.query(SLAPolicy)
        .filter(
            SLAPolicy.organization_id == current_user.organization_id,
            SLAPolicy.is_active == True,  # noqa: E712
        )
        .order_by(SLAPolicy.sla_type)
        .all()
    )

    return [
        {
            "sla_type": sla_type_to_api(p.sla_type) if p.sla_type else None,
            "target_hours": p.target_hours,
            "product_category": p.product_category,
            "business_hours_only": bool(p.business_hours_only),
        }
        for p in policies
    ]


def _rules_as_dict(rules: Any) -> Dict[str, Any]:
    if rules is None:
        return {}
    if isinstance(rules, dict):
        return rules
    if isinstance(rules, str):
        try:
            parsed = json.loads(rules)
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


@router.get("/me/service-policies")
async def list_customer_org_service_policies(
    current_user: User = Depends(require_role([UserRole.CUSTOMER])),
    db: Session = Depends(get_db),
):
    """Active service policies for the customer's organization (read-only)."""
    if not current_user.organization_id:
        return []

    policies = (
        db.query(ServicePolicy)
        .filter(
            ServicePolicy.organization_id == current_user.organization_id,
            ServicePolicy.is_active == True,  # noqa: E712
        )
        .order_by(ServicePolicy.policy_type)
        .all()
    )

    return [
        {
            "policy_type": p.policy_type,
            "rules": _rules_as_dict(p.rules),
            "product_category": p.product_category,
        }
        for p in policies
    ]


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
