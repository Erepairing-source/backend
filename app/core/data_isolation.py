"""
Data Isolation Middleware - Ensures organization data privacy
"""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional, List
from app.models.user import User, UserRole
from app.models.organization import Organization


def check_organization_access(
    db: Session,
    current_user: User,
    organization_id: Optional[int] = None,
    allow_platform_admin: bool = True
) -> bool:
    """
    Check if user has access to organization data
    
    Rules:
    - Platform Admin: Can access all organizations
    - Organization Admin: Can only access their own organization
    - City/State/Country Admin: Can access organizations in their jurisdiction
    - Engineers/Customers: Can only access their own organization
    """
    if not organization_id:
        return True
    
    # Platform Admin has access to everything
    if allow_platform_admin and current_user.role == UserRole.PLATFORM_ADMIN:
        return True
    
    # Organization Admin can only access their own organization
    if current_user.role == UserRole.ORGANIZATION_ADMIN:
        if current_user.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You can only access your own organization's data"
            )
        return True
    
    # City Admin can access organizations in their city
    if current_user.role == UserRole.CITY_ADMIN:
        if current_user.city_id:
            org = db.query(Organization).filter(Organization.id == organization_id).first()
            if org and org.city_id == current_user.city_id:
                return True
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You can only access organizations in your city"
        )
    
    # State Admin can access organizations in their state
    if current_user.role == UserRole.STATE_ADMIN:
        if current_user.state_id:
            org = db.query(Organization).filter(Organization.id == organization_id).first()
            if org and org.state_id == current_user.state_id:
                return True
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You can only access organizations in your state"
        )
    
    # Country Admin can access organizations in their country
    if current_user.role == UserRole.COUNTRY_ADMIN:
        if current_user.country_id:
            org = db.query(Organization).filter(Organization.id == organization_id).first()
            if org and org.country_id == current_user.country_id:
                return True
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You can only access organizations in your country"
        )
    
    # Engineers and Customers can only access their own organization
    if current_user.organization_id == organization_id:
        return True
    
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Access denied: You can only access your own organization's data"
    )


def filter_by_organization(
    query,
    current_user: User,
    organization_field: str = "organization_id",
    allow_platform_admin: bool = True
):
    """
    Filter query by organization based on user role
    
    Returns filtered query
    """
    # Platform Admin sees everything
    if allow_platform_admin and current_user.role == UserRole.PLATFORM_ADMIN:
        return query
    
    # Organization Admin sees only their organization
    if current_user.role == UserRole.ORGANIZATION_ADMIN:
        if current_user.organization_id:
            return query.filter(getattr(query.column_descriptions[0]['entity'], organization_field) == current_user.organization_id)
        return query.filter(False)  # No access if no organization
    
    # City Admin sees organizations in their city
    if current_user.role == UserRole.CITY_ADMIN:
        if current_user.city_id:
            # This requires a join - simplified for now
            return query.join(Organization).filter(Organization.city_id == current_user.city_id)
        return query.filter(False)
    
    # State Admin sees organizations in their state
    if current_user.role == UserRole.STATE_ADMIN:
        if current_user.state_id:
            return query.join(Organization).filter(Organization.state_id == current_user.state_id)
        return query.filter(False)
    
    # Country Admin sees organizations in their country
    if current_user.role == UserRole.COUNTRY_ADMIN:
        if current_user.country_id:
            return query.join(Organization).filter(Organization.country_id == current_user.country_id)
        return query.filter(False)
    
    # Engineers and Customers see only their organization
    if current_user.organization_id:
        return query.filter(getattr(query.column_descriptions[0]['entity'], organization_field) == current_user.organization_id)
    
    return query.filter(False)  # No access


def get_user_organization_id(current_user: User) -> Optional[int]:
    """Get the organization ID the user should have access to"""
    if current_user.role == UserRole.PLATFORM_ADMIN:
        return None  # Platform Admin can access all
    return current_user.organization_id


def enforce_organization_isolation(
    db: Session,
    current_user: User,
    organization_id: Optional[int],
    resource_name: str = "resource"
):
    """
    Enforce organization isolation - raise exception if access denied
    """
    if organization_id:
        check_organization_access(db, current_user, organization_id)
    elif current_user.role != UserRole.PLATFORM_ADMIN:
        # Non-platform admins must have organization_id
        if not current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: {resource_name} requires organization context"
            )



