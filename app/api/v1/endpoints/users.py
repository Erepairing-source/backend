"""
User endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.core.permissions import get_current_user, require_role
from app.core.security import get_password_hash
from app.models.user import User, UserRole
from app.models.location import Country, State, City
from app.schemas.user import UserCreate, UserResponse, UserUpdate

router = APIRouter()


@router.get("/available-roles")
async def get_available_roles(
    current_user: User = Depends(require_role([
        UserRole.ORGANIZATION_ADMIN,
        UserRole.PLATFORM_ADMIN
    ])),
    db: Session = Depends(get_db)
):
    """Get available roles that the current user can create"""
    if current_user.role == UserRole.PLATFORM_ADMIN:
        # Platform admin can only create platform_admin and vendor roles
        available_roles = [UserRole.PLATFORM_ADMIN.value, UserRole.VENDOR.value]
    elif current_user.role == UserRole.ORGANIZATION_ADMIN:
        # Organization admin can create all roles except vendor and platform_admin
        available_roles = [
            role.value for role in UserRole 
            if role not in [UserRole.VENDOR, UserRole.PLATFORM_ADMIN]
        ]
    else:
        available_roles = []
    
    return {"available_roles": available_roles}


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    current_user: User = Depends(require_role([
        UserRole.ORGANIZATION_ADMIN,
        UserRole.PLATFORM_ADMIN
    ])),
    db: Session = Depends(get_db)
):
    """Create a new user with role-based permissions"""
    # Check if email exists
    existing = db.query(User).filter(User.email == user_data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Check if phone exists
    existing_phone = db.query(User).filter(User.phone == user_data.phone).first()
    if existing_phone:
        raise HTTPException(status_code=400, detail="Phone number already registered")
    
    # Role-based permission checks
    if current_user.role == UserRole.PLATFORM_ADMIN:
        # Platform admin can create all roles including vendor
        allowed_roles = [role for role in UserRole]
    elif current_user.role == UserRole.ORGANIZATION_ADMIN:
        # Organization admin can create all roles except vendor and platform_admin
        allowed_roles = [
            role for role in UserRole 
            if role not in [UserRole.VENDOR, UserRole.PLATFORM_ADMIN]
        ]
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to create users"
        )
    
    # Validate that the requested role is allowed
    if user_data.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You don't have permission to create users with role: {user_data.role.value}"
        )
    
    # For organization admin, ensure user is created in their organization
    if current_user.role == UserRole.ORGANIZATION_ADMIN:
        if user_data.organization_id and user_data.organization_id != current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only create users in your own organization"
            )
        user_data.organization_id = current_user.organization_id
    
    # Validate location mapping for role
    def normalize_location(country_id, state_id, city_id):
        if city_id:
            city = db.query(City).filter(City.id == city_id).first()
            if not city:
                raise HTTPException(status_code=404, detail="City not found")
            state = db.query(State).filter(State.id == city.state_id).first()
            if not state:
                raise HTTPException(status_code=404, detail="State not found for city")
            country = db.query(Country).filter(Country.id == state.country_id).first()
            if not country:
                raise HTTPException(status_code=404, detail="Country not found for city")
            if state_id and state_id != state.id:
                raise HTTPException(status_code=400, detail="state_id does not match city_id")
            if country_id and country_id != country.id:
                raise HTTPException(status_code=400, detail="country_id does not match city_id")
            return country.id, state.id, city.id
        if state_id:
            state = db.query(State).filter(State.id == state_id).first()
            if not state:
                raise HTTPException(status_code=404, detail="State not found")
            if country_id and country_id != state.country_id:
                raise HTTPException(status_code=400, detail="country_id does not match state_id")
            return state.country_id, state.id, None
        if country_id:
            country = db.query(Country).filter(Country.id == country_id).first()
            if not country:
                raise HTTPException(status_code=404, detail="Country not found")
            return country.id, None, None
        return None, None, None

    required_city_roles = [UserRole.CITY_ADMIN, UserRole.SUPPORT_ENGINEER]
    required_state_roles = [UserRole.STATE_ADMIN]
    required_country_roles = [UserRole.COUNTRY_ADMIN]
    if user_data.role in required_city_roles and not user_data.city_id:
        raise HTTPException(status_code=400, detail="city_id is required for this role")
    if user_data.role in required_state_roles and not user_data.state_id:
        raise HTTPException(status_code=400, detail="state_id is required for this role")
    if user_data.role in required_country_roles and not user_data.country_id:
        raise HTTPException(status_code=400, detail="country_id is required for this role")

    normalized_country_id, normalized_state_id, normalized_city_id = normalize_location(
        user_data.country_id or current_user.country_id,
        user_data.state_id or current_user.state_id,
        user_data.city_id or current_user.city_id
    )

    # Create user
    user = User(
        email=user_data.email,
        phone=user_data.phone,
        password_hash=get_password_hash(user_data.password),
        full_name=user_data.full_name,
        role=user_data.role,
        organization_id=user_data.organization_id or current_user.organization_id,
        country_id=normalized_country_id,
        state_id=normalized_state_id,
        city_id=normalized_city_id,
        engineer_skill_level=user_data.engineer_skill_level,
        engineer_specialization=",".join(user_data.engineer_specialization) if user_data.engineer_specialization else None,
        is_active=True,
        is_verified=False
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return user


@router.get("/me", response_model=UserResponse)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user profile"""
    return current_user


@router.put("/me/location")
async def update_my_location(
    payload: dict = Body(...),
    current_user: User = Depends(require_role([UserRole.SUPPORT_ENGINEER])),
    db: Session = Depends(get_db)
):
    """Update current engineer location"""
    lat = payload.get("latitude")
    lng = payload.get("longitude")
    current_user.current_location_lat = lat
    current_user.current_location_lng = lng
    db.commit()
    return {"message": "Location updated"}


@router.get("/", response_model=List[UserResponse])
async def list_users(
    role: UserRole = None,
    organization_id: int = None,
    current_user: User = Depends(require_role([
        UserRole.ORGANIZATION_ADMIN,
        UserRole.PLATFORM_ADMIN,
        UserRole.CITY_ADMIN,
        UserRole.STATE_ADMIN
    ])),
    db: Session = Depends(get_db)
):
    """List users based on permissions"""
    query = db.query(User)
    
    # Role-based filtering
    if current_user.role == UserRole.CITY_ADMIN:
        query = query.filter(User.city_id == current_user.city_id)
    elif current_user.role == UserRole.STATE_ADMIN:
        query = query.filter(User.state_id == current_user.state_id)
    elif current_user.role == UserRole.ORGANIZATION_ADMIN:
        query = query.filter(User.organization_id == current_user.organization_id)
    # Platform admin can see all
    
    if role:
        query = query.filter(User.role == role)
    if organization_id:
        query = query.filter(User.organization_id == organization_id)
    
    users = query.all()
    return users


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    current_user: User = Depends(require_role([
        UserRole.ORGANIZATION_ADMIN,
        UserRole.PLATFORM_ADMIN
    ])),
    db: Session = Depends(get_db)
):
    """Get user by ID"""
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Permission check
    if current_user.role == UserRole.ORGANIZATION_ADMIN:
        if user.organization_id != current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view users in your organization"
            )
    
    return user


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    current_user: User = Depends(require_role([
        UserRole.ORGANIZATION_ADMIN,
        UserRole.PLATFORM_ADMIN
    ])),
    db: Session = Depends(get_db)
):
    """Update user"""
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Permission check
    if current_user.role == UserRole.ORGANIZATION_ADMIN:
        if user.organization_id != current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only update users in your organization"
            )
        # Organization admin cannot change role to vendor or platform_admin
        if user_data.role and user_data.role in [UserRole.VENDOR, UserRole.PLATFORM_ADMIN]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You cannot change user role to vendor or platform_admin"
            )
    
    # Update fields
    if user_data.full_name is not None:
        user.full_name = user_data.full_name
    if user_data.email is not None:
        # Check if email already exists (excluding current user)
        existing = db.query(User).filter(
            User.email == user_data.email,
            User.id != user_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")
        user.email = user_data.email
    if user_data.phone is not None:
        # Check if phone already exists (excluding current user)
        existing = db.query(User).filter(
            User.phone == user_data.phone,
            User.id != user_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Phone number already registered")
        user.phone = user_data.phone
    if user_data.password is not None:
        user.password_hash = get_password_hash(user_data.password)
    if user_data.role is not None:
        user.role = user_data.role
    if user_data.is_active is not None:
        user.is_active = user_data.is_active
    if user_data.country_id is not None or user_data.state_id is not None or user_data.city_id is not None:
        def normalize_location(country_id, state_id, city_id):
            if city_id:
                city = db.query(City).filter(City.id == city_id).first()
                if not city:
                    raise HTTPException(status_code=404, detail="City not found")
                state = db.query(State).filter(State.id == city.state_id).first()
                if not state:
                    raise HTTPException(status_code=404, detail="State not found for city")
                country = db.query(Country).filter(Country.id == state.country_id).first()
                if not country:
                    raise HTTPException(status_code=404, detail="Country not found for city")
                if state_id and state_id != state.id:
                    raise HTTPException(status_code=400, detail="state_id does not match city_id")
                if country_id and country_id != country.id:
                    raise HTTPException(status_code=400, detail="country_id does not match city_id")
                return country.id, state.id, city.id
            if state_id:
                state = db.query(State).filter(State.id == state_id).first()
                if not state:
                    raise HTTPException(status_code=404, detail="State not found")
                if country_id and country_id != state.country_id:
                    raise HTTPException(status_code=400, detail="country_id does not match state_id")
                return state.country_id, state.id, None
            if country_id:
                country = db.query(Country).filter(Country.id == country_id).first()
                if not country:
                    raise HTTPException(status_code=404, detail="Country not found")
                return country.id, None, None
            return None, None, None

        normalized_country_id, normalized_state_id, normalized_city_id = normalize_location(
            user_data.country_id if user_data.country_id is not None else user.country_id,
            user_data.state_id if user_data.state_id is not None else user.state_id,
            user_data.city_id if user_data.city_id is not None else user.city_id
        )
        user.country_id = normalized_country_id
        user.state_id = normalized_state_id
        user.city_id = normalized_city_id
    
    db.commit()
    db.refresh(user)
    
    return user


@router.get("/engineers", response_model=List[UserResponse])
async def list_engineers(
    city_id: int = None,
    is_available: bool = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List available engineers"""
    query = db.query(User).filter(User.role == UserRole.SUPPORT_ENGINEER)
    
    if city_id:
        query = query.filter(User.city_id == city_id)
    if is_available is not None:
        query = query.filter(User.is_available == is_available)
    
    engineers = query.all()
    return engineers


