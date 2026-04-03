"""
User endpoints
"""
import io
import secrets
import string
from fastapi import APIRouter, Depends, HTTPException, status, Body, File, UploadFile, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List

import pandas as pd

from app.core.database import get_db
from app.core.config import settings
from app.core.permissions import get_current_user, require_role
from app.core.security import get_password_hash, get_pending_password_hash
from app.core.password_set_email import create_and_send_set_password_token
from app.core.email import send_credentials_email, send_email_verification_otp
from app.core.email_verification import create_email_verification_otp
from app.models.user import User, UserRole
from app.models.location import Country, State, City
from app.schemas.user import UserCreate, UserResponse, UserUpdate

router = APIRouter()


def _generate_password(length: int = 10) -> str:
    """Generate a random alphanumeric password (readable)."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


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


@router.post("/", status_code=status.HTTP_201_CREATED)
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

    # Password: if provided use it; otherwise placeholder and send set-password email (for any role)
    use_password_email = not user_data.password or not str(user_data.password or "").strip()
    if use_password_email:
        password_hash = get_pending_password_hash()
    else:
        password_hash = get_password_hash(user_data.password)

    # Create user
    user = User(
        email=user_data.email,
        phone=user_data.phone,
        password_hash=password_hash,
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
    db.flush()
    if use_password_email:
        create_and_send_set_password_token(db, user)
    else:
        otp_code = create_email_verification_otp(db, user.id, ttl_minutes=15)
        send_email_verification_otp(
            user.email,
            otp_code,
            user.full_name,
            context="new user account",
        )
    db.commit()
    db.refresh(user)

    if use_password_email:
        response = UserResponse.model_validate(user)
        return {"user": response, "password_set_via_email": True}
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
        UserRole.STATE_ADMIN,
        UserRole.COUNTRY_ADMIN,
    ])),
    db: Session = Depends(get_db)
):
    """List users based on permissions and hierarchy (org → country → state → city)."""
    query = db.query(User)
    
    # Hierarchy-based filtering: city sees city; state sees state; country sees country; org sees org; platform sees all
    if current_user.role == UserRole.CITY_ADMIN:
        query = query.filter(User.city_id == current_user.city_id)
    elif current_user.role == UserRole.STATE_ADMIN:
        query = query.filter(User.state_id == current_user.state_id)
    elif current_user.role == UserRole.COUNTRY_ADMIN:
        query = query.filter(User.country_id == current_user.country_id)
    elif current_user.role == UserRole.ORGANIZATION_ADMIN:
        query = query.filter(User.organization_id == current_user.organization_id)
    # Platform admin: no filter (sees all)
    
    if role:
        query = query.filter(User.role == role)
    if organization_id:
        query = query.filter(User.organization_id == organization_id)
    
    users = query.all()
    return users


@router.post("/bulk-customers")
async def bulk_create_customers(
    file: UploadFile = File(...),
    send_email: bool = Form(True),
    current_user: User = Depends(require_role([UserRole.ORGANIZATION_ADMIN])),
    db: Session = Depends(get_db)
):
    """
    Org Admin: bulk create customers from Excel.
    Excel columns: full_name (or Full Name), email (or Email), phone (or Phone).
    If send_email=True, a random password is generated and sent to each customer's email.
    """
    if not file.filename or not (file.filename.endswith(".xlsx") or file.filename.endswith(".xls")):
        raise HTTPException(status_code=400, detail="Upload an Excel file (.xlsx or .xls)")
    org_id = current_user.organization_id
    if not org_id:
        raise HTTPException(status_code=403, detail="You are not associated with an organization")
    content = await file.read()
    try:
        df = pd.read_excel(io.BytesIO(content), engine="openpyxl")
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid Excel file. Use .xlsx format. Error: {str(e)}"
        )
    # Normalize column names: strip, lower, replace space with underscore
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    required = ["full_name", "email", "phone"]
    for col in required:
        if col not in df.columns:
            raise HTTPException(
                status_code=400,
                detail=f"Excel must have columns: full_name, email, phone. Found: {list(df.columns)}"
            )
    login_url = (getattr(settings, "FRONTEND_URL", "http://localhost:3000") or "http://localhost:3000").rstrip("/") + "/login"
    created = 0
    skipped = 0
    errors = []
    for idx, row in df.iterrows():
        row_num = idx + 2  # 1-based + header
        full_name = str(row.get("full_name", "")).strip() if pd.notna(row.get("full_name")) else ""
        email = str(row.get("email", "")).strip().lower() if pd.notna(row.get("email")) else ""
        phone = str(row.get("phone", "")).strip() if pd.notna(row.get("phone")) else ""
        if not full_name or not email or not phone:
            errors.append({"row": row_num, "email": email or "(blank)", "error": "full_name, email, and phone are required"})
            skipped += 1
            continue
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            errors.append({"row": row_num, "email": email, "error": "Email already registered"})
            skipped += 1
            continue
        existing_phone = db.query(User).filter(User.phone == phone).first()
        if existing_phone:
            errors.append({"row": row_num, "email": email, "error": "Phone already registered"})
            skipped += 1
            continue
        password = _generate_password(10)
        password_hash = get_password_hash(password)
        user = User(
            email=email,
            phone=phone,
            password_hash=password_hash,
            full_name=full_name,
            role=UserRole.CUSTOMER,
            organization_id=org_id,
            country_id=None,
            state_id=None,
            city_id=None,
            is_active=True,
            is_verified=False,
        )
        db.add(user)
        db.flush()
        if send_email:
            otp_code = create_email_verification_otp(db, user.id, ttl_minutes=15)
            send_credentials_email(
                email,
                full_name,
                password,
                login_url,
                email_verification_otp=otp_code,
            )
        created += 1
    db.commit()
    return {
        "message": f"Bulk upload complete. Created: {created}, Skipped: {skipped}",
        "total": len(df),
        "created": created,
        "skipped": skipped,
        "errors": errors[:50],
    }


@router.get("/bulk-customers-template")
async def bulk_customers_template(
    current_user: User = Depends(require_role([UserRole.ORGANIZATION_ADMIN])),
):
    """Download Excel template for bulk customer upload. Columns: full_name, email, phone."""
    df = pd.DataFrame(columns=["full_name", "email", "phone"])
    df.loc[0] = ["John Doe", "john@example.com", "+91 9876543210"]
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=bulk_customers_template.xlsx"},
    )


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


