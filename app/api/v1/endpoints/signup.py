"""
Public signup endpoint for organizations
"""
from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone

from app.core.database import get_db
from app.core.security import get_password_hash, create_access_token
from app.core.config import settings
from app.models.organization import Organization, OrganizationType
from app.models.user import User, UserRole
from app.models.subscription import Plan, Subscription, BillingPeriod, Vendor, VendorOrganization

router = APIRouter()


@router.post("/", status_code=status.HTTP_201_CREATED)
async def signup_organization(
    signup_data: dict = Body(...),
    db: Session = Depends(get_db)
):
    """
    Public endpoint for organization signup
    Creates organization, admin user, and subscription
    Optionally links to vendor if vendor_code or vendor_id is provided
    """
    # Validate required fields
    required_fields = [
        "org_name", "org_type", "org_email", "org_phone", "country_id", 
        "state_id", "city_id", "admin_name", "admin_email", "admin_phone", 
        "admin_password", "plan_id", "billing_period"
    ]
    
    for field in required_fields:
        if field not in signup_data or not signup_data[field]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required field: {field}"
            )
    
    # Check if organization email already exists
    existing_org = db.query(Organization).filter(
        Organization.email == signup_data["org_email"]
    ).first()
    if existing_org:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization with this email already exists"
        )
    
    # Check if admin email already exists
    existing_user = db.query(User).filter(
        User.email == signup_data["admin_email"]
    ).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )
    
    # Check if admin phone already exists
    existing_phone = db.query(User).filter(
        User.phone == signup_data["admin_phone"]
    ).first()
    if existing_phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this phone number already exists"
        )
    
    # Validate plan exists and is active
    plan = db.query(Plan).filter(
        Plan.id == signup_data["plan_id"],
        Plan.is_active == True
    ).first()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or inactive plan selected"
        )
    
    # Create organization
    organization = Organization(
        name=signup_data["org_name"],
        org_type=OrganizationType(signup_data["org_type"]),
        email=signup_data["org_email"],
        phone=signup_data["org_phone"],
        address=signup_data.get("org_address", ""),
        country_id=signup_data["country_id"],
        state_id=signup_data["state_id"],
        city_id=signup_data["city_id"],
        is_active=True
    )
    
    db.add(organization)
    db.flush()  # Get organization ID without committing
    
    # Create subscription
    billing_period_str = signup_data["billing_period"].lower()
    try:
        billing_period = BillingPeriod(billing_period_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid billing period: {signup_data['billing_period']}. Must be 'monthly' or 'annual'"
        )
    
    # Get price based on billing period - explicitly convert to float
    # Refresh plan from database to ensure we have latest prices
    db.refresh(plan)
    
    if billing_period == BillingPeriod.MONTHLY:
        raw_price = plan.monthly_price
        if raw_price is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Plan {plan.name} (ID: {plan.id}) does not have a monthly price set. Monthly price: {plan.monthly_price}"
            )
    elif billing_period == BillingPeriod.ANNUAL:
        raw_price = plan.annual_price
        if raw_price is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Plan {plan.name} (ID: {plan.id}) does not have an annual price set. Annual price: {plan.annual_price}"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported billing period: {billing_period}"
        )
    
    # Validate and convert price
    if raw_price is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Plan {plan.name} does not have a valid price for {billing_period.value} billing period"
        )
    
    try:
        price = float(raw_price)
    except (ValueError, TypeError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid price value for plan {plan.name}: {raw_price} (error: {str(e)})"
        )
    
    if price <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Price must be greater than 0 for plan {plan.name}. Got: {price}"
        )
    
    # Final validation - ensure price is definitely set
    if price is None or price <= 0:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Price calculation failed for plan {plan.name}. Price: {price}, Billing: {billing_period.value}"
        )
    
    # Calculate end date
    start_date = datetime.now(timezone.utc)
    if billing_period == BillingPeriod.MONTHLY:
        end_date = start_date + timedelta(days=30)
    else:
        end_date = start_date + timedelta(days=365)
    
    # Create subscription with explicit price validation
    # Ensure price is definitely a float and not None
    try:
        subscription_price = float(price)
    except (ValueError, TypeError) as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cannot convert price to float: {price} (type: {type(price)}, error: {str(e)})"
        )
    
    # Final safety check - price must be a positive number
    if subscription_price is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Price is None after conversion. Original price: {price}, Billing: {billing_period.value}"
        )
    
    if not isinstance(subscription_price, (int, float)):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Price is not a number: {subscription_price} (type: {type(subscription_price)})"
        )
    
    if subscription_price <= 0:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Price must be positive: {subscription_price}"
        )
    
    # Create subscription - price is guaranteed to be a valid float at this point
    # Final validation with explicit error messages
    if subscription_price is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"CRITICAL ERROR: subscription_price is None! price={price}, raw_price={raw_price}, billing={billing_period.value}, plan_id={plan.id}"
        )
    
    if not isinstance(subscription_price, (int, float)):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"CRITICAL ERROR: subscription_price is not a number! Value: {subscription_price}, Type: {type(subscription_price)}"
        )
    
    if subscription_price <= 0:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"CRITICAL ERROR: subscription_price is not positive! Value: {subscription_price}"
        )
    
    # Create subscription with explicit price (ensure it's a float, not None)
    final_price = float(subscription_price)  # One more conversion to be absolutely sure
    
    # Ensure final_price is definitely a number
    if final_price is None or not isinstance(final_price, (int, float)) or final_price <= 0:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Invalid final_price: {final_price} (type: {type(final_price)})"
        )
    
    # Create subscription with ALL fields including current_price
    subscription = Subscription(
        organization_id=organization.id,
        plan_id=plan.id,
        billing_period=billing_period,
        current_price=final_price,  # MUST be set here
        currency="INR",
        status="active",
        start_date=start_date,
        end_date=end_date
    )
    
    # Double-check it's set (shouldn't be needed but just in case)
    if not hasattr(subscription, 'current_price') or subscription.current_price is None:
        # Force set it using setattr
        setattr(subscription, 'current_price', final_price)
    
    # Final verification
    if subscription.current_price is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"CRITICAL: current_price is None! final_price={final_price}, type={type(final_price)}, subscription.current_price={subscription.current_price}"
        )
    
    # Ensure it's a float - convert explicitly
    subscription.current_price = float(subscription.current_price)
    
    # One final check before adding to session
    if subscription.current_price is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"FINAL CHECK FAILED: current_price is None right before db.add()! final_price={final_price}"
        )
    
    # Add to session and flush
    db.add(subscription)
    
    # Verify price is still set after adding to session
    if subscription.current_price is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Price became None after db.add()! This should not happen."
        )
    
    try:
        db.flush()
    except Exception as e:
        # If flush fails, check the subscription object state
        error_msg = str(e)
        if "current_price" in error_msg.lower() or "cannot be null" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Database error: {error_msg}. Subscription current_price={subscription.current_price}, final_price={final_price}, type={type(subscription.current_price)}"
            )
        raise
    
    # Link subscription to organization
    organization.subscription_id = subscription.id
    
    # Create admin user
    admin_user = User(
        email=signup_data["admin_email"],
        phone=signup_data["admin_phone"],
        password_hash=get_password_hash(signup_data["admin_password"]),
        full_name=signup_data["admin_name"],
        role=UserRole.ORGANIZATION_ADMIN,
        organization_id=organization.id,
        country_id=signup_data["country_id"],
        state_id=signup_data["state_id"],
        city_id=signup_data["city_id"],
        is_active=True,
        is_verified=False  # Will need email verification
    )
    
    db.add(admin_user)
    
    # Flush to get IDs before vendor linking
    db.flush()
    
    # Link to vendor if provided (vendor_id or vendor_code)
    vendor = None
    vendor_linked = False
    commission_amount = 0.0  # Initialize for use in response
    
    if signup_data.get("vendor_id"):
        try:
            vendor = db.query(Vendor).filter(Vendor.id == int(signup_data["vendor_id"])).first()
        except (ValueError, TypeError) as e:
            print(f"Warning: Invalid vendor_id: {e}")
            pass  # Invalid vendor_id, skip vendor linking
    
    if not vendor and signup_data.get("vendor_code"):
        try:
            vendor_code = str(signup_data["vendor_code"]).strip().upper()
            vendor = db.query(Vendor).filter(Vendor.vendor_code == vendor_code).first()
            if not vendor:
                print(f"Warning: Vendor with code '{vendor_code}' not found")
        except Exception as e:
            print(f"Warning: Error finding vendor by code: {e}")
            pass  # Error finding vendor, skip vendor linking
    
    if vendor:
        try:
            # Validate vendor commission rate
            commission_rate = float(vendor.commission_rate) if vendor.commission_rate is not None else 0.15
            
            # Calculate commission based on subscription price and vendor commission rate
            commission_amount = float(final_price) * commission_rate
            
            # Check if organization is already linked to a vendor (shouldn't happen for new org, but check anyway)
            existing_vendor_org = db.query(VendorOrganization).filter(
                VendorOrganization.organization_id == organization.id
            ).first()
            
            if not existing_vendor_org:
                # Create VendorOrganization link
                vendor_org = VendorOrganization(
                    vendor_id=vendor.id,
                    organization_id=organization.id,
                    commission_earned=commission_amount,
                    last_commission_date=datetime.now(timezone.utc),
                    is_active=True
                )
                db.add(vendor_org)
                vendor_linked = True
                print(f"Successfully linked organization {organization.id} to vendor {vendor.id} (code: {vendor.vendor_code})")
            else:
                print(f"Warning: Organization {organization.id} already linked to vendor")
        except Exception as e:
            # Log error but don't fail signup if vendor linking fails
            import traceback
            print(f"Warning: Failed to link vendor: {str(e)}")
            print(traceback.format_exc())
            # Continue with signup even if vendor linking fails
    
    db.commit()
    db.refresh(organization)
    db.refresh(admin_user)
    db.refresh(subscription)
    
    # Generate access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": str(admin_user.id),
            "email": admin_user.email,
            "role": admin_user.role.value,
            "organization_id": admin_user.organization_id
        },
        expires_delta=access_token_expires
    )
    
    response_data = {
        "message": "Organization registered successfully",
        "organization": {
            "id": organization.id,
            "name": organization.name,
            "email": organization.email
        },
        "user": {
            "id": admin_user.id,
            "email": admin_user.email,
            "full_name": admin_user.full_name,
            "role": admin_user.role.value
        },
        "subscription": {
            "id": subscription.id,
            "plan_name": plan.name,
            "status": subscription.status,
            "end_date": subscription.end_date.isoformat()
        },
        "access_token": access_token,
        "token_type": "bearer"
    }
    
    # Add vendor info if linked
    if vendor_linked and vendor:
        response_data["vendor"] = {
            "vendor_code": vendor.vendor_code,
            "vendor_name": vendor.name,
            "commission_earned": commission_amount
        }
    
    return response_data

