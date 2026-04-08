"""
User endpoints
"""
import io
import secrets
import string
from fastapi import APIRouter, Depends, HTTPException, status, Body, File, UploadFile, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from typing import List, Optional

import pandas as pd

from app.core.database import get_db
from app.core.location_scope import apply_user_query_scope
from app.core.location_resolution import materialize_user_location_ids
from app.core.permissions import get_current_user, require_role
from app.core.config import frontend_base_url
from app.core.security import get_password_hash, get_pending_password_hash
from app.core.password_set_email import create_and_send_set_password_token
from app.core.email import send_credentials_email
from app.core.email_verification import create_email_verification_otp
from app.models.user import User, UserRole
from app.models.location import Country, State, City
from app.models.ticket import Ticket, TicketComment
from app.models.notification import Notification
from app.models.password_set_token import PasswordSetToken
from app.models.email_verification_otp import EmailVerificationOTP
from app.models.device import Device
from app.models.ticket_start_approval import TicketStartApproval
from app.models.escalation import Escalation
from app.models.inventory import InventoryTransaction
from app.models.warranty import WarrantyClaim
from app.models.subscription import Vendor
from app.models.ai_models import SentimentAnalysis, ChatSession
from app.schemas.user import UserCreate, UserResponse, UserUpdate

router = APIRouter()


def _detach_user_references(db: Session, user_id: int, actor_id: int) -> None:
    """Clear or reassign FKs so a user row can be deleted without integrity errors."""
    db.query(Notification).filter(Notification.user_id == user_id).delete(synchronize_session=False)
    db.query(PasswordSetToken).filter(PasswordSetToken.user_id == user_id).delete(synchronize_session=False)
    db.query(EmailVerificationOTP).filter(EmailVerificationOTP.user_id == user_id).delete(
        synchronize_session=False
    )

    for session in db.query(ChatSession).filter(ChatSession.user_id == user_id).all():
        db.delete(session)

    db.query(Ticket).filter(Ticket.customer_id == user_id).update(
        {Ticket.customer_id: None}, synchronize_session=False
    )
    db.query(Ticket).filter(Ticket.assigned_engineer_id == user_id).update(
        {Ticket.assigned_engineer_id: None}, synchronize_session=False
    )
    db.query(Ticket).filter(Ticket.assigned_by_id == user_id).update(
        {Ticket.assigned_by_id: None}, synchronize_session=False
    )
    db.query(Ticket).filter(Ticket.created_by_id == user_id).update(
        {Ticket.created_by_id: None}, synchronize_session=False
    )

    db.query(TicketComment).filter(TicketComment.user_id == user_id).update(
        {TicketComment.user_id: None}, synchronize_session=False
    )

    db.query(TicketStartApproval).filter(TicketStartApproval.requested_by_id == user_id).update(
        {TicketStartApproval.requested_by_id: actor_id}, synchronize_session=False
    )
    db.query(TicketStartApproval).filter(TicketStartApproval.approved_by_id == user_id).update(
        {TicketStartApproval.approved_by_id: None}, synchronize_session=False
    )

    db.query(Escalation).filter(Escalation.escalated_by_id == user_id).update(
        {Escalation.escalated_by_id: actor_id}, synchronize_session=False
    )
    db.query(Escalation).filter(Escalation.assigned_to_id == user_id).update(
        {Escalation.assigned_to_id: None}, synchronize_session=False
    )
    db.query(Escalation).filter(Escalation.resolved_by_id == user_id).update(
        {Escalation.resolved_by_id: None}, synchronize_session=False
    )

    db.query(InventoryTransaction).filter(InventoryTransaction.performed_by_id == user_id).update(
        {InventoryTransaction.performed_by_id: None}, synchronize_session=False
    )
    db.query(InventoryTransaction).filter(InventoryTransaction.requested_by_id == user_id).update(
        {InventoryTransaction.requested_by_id: None}, synchronize_session=False
    )
    db.query(InventoryTransaction).filter(InventoryTransaction.approved_by_id == user_id).update(
        {InventoryTransaction.approved_by_id: None}, synchronize_session=False
    )

    db.query(WarrantyClaim).filter(WarrantyClaim.approved_by_id == user_id).update(
        {WarrantyClaim.approved_by_id: None}, synchronize_session=False
    )

    db.query(Vendor).filter(Vendor.user_id == user_id).update({Vendor.user_id: None}, synchronize_session=False)

    db.query(SentimentAnalysis).filter(SentimentAnalysis.engineer_id == user_id).update(
        {SentimentAnalysis.engineer_id: None}, synchronize_session=False
    )


def _role_value(role) -> str:
    """Normalize role for comparisons (avoids MySQL/SQLAlchemy enum mismatches skipping filters)."""
    if role is None:
        return ""
    if isinstance(role, UserRole):
        return role.value
    return str(role)


def _generate_password(length: int = 10) -> str:
    """Generate a random alphanumeric password (readable)."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


@router.get("/available-roles")
def get_available_roles(
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
def create_user(
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

    mc, ms, mct = materialize_user_location_ids(
        db,
        country_id=user_data.country_id,
        country_code=user_data.country_code,
        state_id=user_data.state_id,
        state_name=user_data.state_name,
        state_code=user_data.state_code,
        city_id=user_data.city_id,
        city_name=user_data.city_name,
    )
    eff_country = mc or user_data.country_id or current_user.country_id
    eff_state = ms or user_data.state_id or current_user.state_id
    eff_city = mct or user_data.city_id or current_user.city_id

    required_city_roles = [UserRole.CITY_ADMIN, UserRole.SUPPORT_ENGINEER]
    required_state_roles = [UserRole.STATE_ADMIN]
    required_country_roles = [UserRole.COUNTRY_ADMIN]
    if user_data.role in required_city_roles and not eff_city:
        raise HTTPException(
            status_code=400,
            detail="City is required for this role. Select a city or send city_name with state and country.",
        )
    if user_data.role in required_state_roles and not eff_state:
        raise HTTPException(
            status_code=400,
            detail="State is required for this role. Select a state or send state_name/state_code with country.",
        )
    if user_data.role in required_country_roles and not eff_country:
        raise HTTPException(
            status_code=400,
            detail="Country is required for this role. Select a country or send country_code (e.g. IN).",
        )

    normalized_country_id, normalized_state_id, normalized_city_id = normalize_location(
        eff_country,
        eff_state,
        eff_city,
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
        send_credentials_email(
            user.email,
            user.full_name,
            str(user_data.password).strip(),
            email_verification_otp=otp_code,
            email_subject="Your eRepairing account — sign in details",
            body_intro="An administrator created your eRepairing account. Use the email and password below to sign in.",
            subtitle="Your account is ready. Sign in with the details below, then verify your email with the code.",
        )
    db.commit()
    db.refresh(user)

    if use_password_email:
        response = UserResponse.model_validate(user)
        return {"user": response, "password_set_via_email": True}
    return user


@router.get("/me", response_model=UserResponse)
def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user profile"""
    return current_user


@router.put("/me/location")
def update_my_location(
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
def list_users(
    role: UserRole = None,
    organization_id: Optional[str] = None,
    state_id: Optional[str] = None,
    city_id: Optional[str] = None,
    state_code: Optional[str] = None,
    state_name: Optional[str] = None,
    city_name: Optional[str] = None,
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
    def _parse_optional_int(value: Optional[str], field_name: str) -> Optional[int]:
        if value is None:
            return None
        s = str(value).strip().lower()
        if s in ("", "null", "none", "undefined"):
            return None
        try:
            return int(s)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"{field_name} must be an integer")

    def _parse_optional_text(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        s = str(value).strip()
        if not s or s.lower() in ("null", "none", "undefined"):
            return None
        return s

    organization_id_int = _parse_optional_int(organization_id, "organization_id")
    state_id_int = _parse_optional_int(state_id, "state_id")
    city_id_int = _parse_optional_int(city_id, "city_id")
    state_code_text = _parse_optional_text(state_code)
    state_name_text = _parse_optional_text(state_name)
    city_name_text = _parse_optional_text(city_name)

    query = apply_user_query_scope(
        db.query(User).options(joinedload(User.state), joinedload(User.city)),
        current_user,
    )

    if role:
        query = query.filter(User.role == role)
    if organization_id_int is not None:
        query = query.filter(User.organization_id == organization_id_int)
    if state_id_int is not None:
        query = query.filter(User.state_id == state_id_int)
    elif state_code_text:
        code = state_code_text.upper()
        query = query.join(State, User.state_id == State.id).filter(func.upper(State.code) == code)
    elif state_name_text:
        query = query.join(State, User.state_id == State.id).filter(func.lower(State.name) == state_name_text.lower())

    if city_id_int is not None:
        query = query.filter(User.city_id == city_id_int)
    elif city_name_text:
        query = query.join(City, User.city_id == City.id).filter(func.lower(City.name) == city_name_text.lower())
    
    users = query.all()
    return [
        {
            "id": u.id,
            "email": u.email,
            "phone": u.phone,
            "full_name": u.full_name,
            "role": u.role,
            "organization_id": u.organization_id,
            "country_id": u.country_id,
            "state_id": u.state_id,
            "city_id": u.city_id,
            "state_name": u.state.name if getattr(u, "state", None) else None,
            "city_name": u.city.name if getattr(u, "city", None) else None,
            "is_available": u.is_available,
            "engineer_skill_level": u.engineer_skill_level,
            "engineer_specialization": u.engineer_specialization,
            "is_active": u.is_active,
            "is_verified": u.is_verified,
            "created_at": u.created_at,
        }
        for u in users
    ]


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
    login_url = f"{frontend_base_url()}/login"
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
def bulk_customers_template(
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
def get_user(
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
def update_user(
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
    loc_keys = (
        "country_id",
        "country_code",
        "state_id",
        "state_name",
        "state_code",
        "city_id",
        "city_name",
    )
    if any(getattr(user_data, k, None) is not None for k in loc_keys):
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

        base_c = user.country_id
        base_s = user.state_id
        base_city = user.city_id
        if user_data.country_id is not None:
            base_c = user_data.country_id
        if user_data.state_id is not None:
            base_s = user_data.state_id
        if user_data.city_id is not None:
            base_city = user_data.city_id

        mc, ms, mct = materialize_user_location_ids(
            db,
            country_id=base_c,
            country_code=user_data.country_code,
            state_id=base_s,
            state_name=user_data.state_name,
            state_code=user_data.state_code,
            city_id=base_city,
            city_name=user_data.city_name,
        )
        eff_c = mc or base_c
        eff_s = ms or base_s
        eff_city = mct or base_city

        normalized_country_id, normalized_state_id, normalized_city_id = normalize_location(
            eff_c,
            eff_s,
            eff_city,
        )
        user.country_id = normalized_country_id
        user.state_id = normalized_state_id
        user.city_id = normalized_city_id
    
    db.commit()
    db.refresh(user)
    
    return user


@router.delete("/{user_id}", status_code=status.HTTP_200_OK)
def delete_user(
    user_id: int,
    current_user: User = Depends(require_role([UserRole.ORGANIZATION_ADMIN, UserRole.PLATFORM_ADMIN])),
    db: Session = Depends(get_db),
):
    """
    Permanently delete a user. Organization admins may only delete users in their organization
    (not themselves and not other organization admins). Customers with registered devices must
    remove/reassign devices first.
    """
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")

    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    if current_user.role == UserRole.ORGANIZATION_ADMIN:
        if target.organization_id != current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only delete users in your organization",
            )
        if target.role == UserRole.ORGANIZATION_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You cannot delete another organization administrator",
            )
    elif current_user.role == UserRole.PLATFORM_ADMIN:
        if target.role == UserRole.PLATFORM_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You cannot delete another platform administrator",
            )

    if db.query(Device).filter(Device.customer_id == user_id).first():
        raise HTTPException(
            status_code=400,
            detail="This user still has registered devices. Remove or reassign devices before deleting the user.",
        )

    try:
        _detach_user_references(db, user_id, actor_id=current_user.id)
        db.delete(target)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="User could not be deleted because related records still reference this account.",
        )

    return {"message": "User deleted", "id": user_id}


@router.get("/engineers", response_model=List[UserResponse])
def list_engineers(
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


