"""
Role-based access control and permissions
"""
from typing import List, Optional
from fastapi import HTTPException, status, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user_token
from app.core.data_isolation import check_organization_access, enforce_organization_isolation
from app.models.user import User, UserRole
from app.models.organization import Organization


def require_role(allowed_roles: List[UserRole]):
    """Dependency to require specific roles"""
    async def role_checker(
        token_data: dict = Depends(get_current_user_token),
        db: Session = Depends(get_db)
    ):
        user_id = token_data.get("sub")
        user = db.query(User).filter(User.id == int(user_id)).first()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {[r.value for r in allowed_roles]}"
            )
        
        return user
    
    return role_checker


def require_organization_access(organization_id: int):
    """Check if user has access to organization"""
    async def org_checker(
        user: User = Depends(require_role([UserRole.ORGANIZATION_ADMIN, UserRole.PLATFORM_ADMIN])),
        db: Session = Depends(get_db)
    ):
        # Platform admin has access to all
        if user.role == UserRole.PLATFORM_ADMIN:
            return user
        
        # Organization admin can only access their org
        if user.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this organization"
            )
        
        return user
    
    return org_checker


def get_current_user(
    token_data: dict = Depends(get_current_user_token),
    db: Session = Depends(get_db)
) -> User:
    """Get current authenticated user"""
    user_id = token_data.get("sub")
    user = db.query(User).filter(User.id == int(user_id)).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user


def check_location_access(
    user: User,
    country_id: Optional[int] = None,
    state_id: Optional[int] = None,
    city_id: Optional[int] = None
) -> bool:
    """Check if user has access to location based on their role"""
    # Platform admin has access everywhere
    if user.role == UserRole.PLATFORM_ADMIN:
        return True
    
    # Organization admin has access to their org's locations
    if user.role == UserRole.ORGANIZATION_ADMIN:
        return True  # Can access all locations in their org
    
    # Country admin has access to their country
    if user.role == UserRole.COUNTRY_ADMIN:
        return user.country_id == country_id if country_id else True
    
    # State admin has access to their state
    if user.role == UserRole.STATE_ADMIN:
        return user.state_id == state_id if state_id else True
    
    # City admin has access to their city
    if user.role == UserRole.CITY_ADMIN:
        return user.city_id == city_id if city_id else True
    
    # Engineers and customers have limited access
    return False


