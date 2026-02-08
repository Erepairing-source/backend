"""
Platform Admin endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.database import get_db
from app.core.permissions import require_role
from app.models.user import User, UserRole
from app.models.organization import Organization
from app.models.subscription import Plan, Subscription, Vendor, VendorOrganization
from app.models.device import Device
from app.models.ticket import Ticket

router = APIRouter()


@router.get("/plans/public")
async def list_plans_public(db: Session = Depends(get_db)):
    """Public endpoint to list all visible subscription plans (no auth required)"""
    plans = db.query(Plan).filter(Plan.is_visible == True).order_by(Plan.display_order).all()
    
    return [
        {
            "id": p.id,
            "name": p.name,
            "plan_type": p.plan_type.value,
            "monthly_price": float(p.monthly_price) if p.monthly_price else 0.0,
            "annual_price": float(p.annual_price) if p.annual_price else 0.0,
            "max_engineers": p.max_engineers,
            "features": p.features or {},
            "description": p.description or "",
            "is_active": p.is_active,
            "is_visible": p.is_visible,
            "display_order": p.display_order or 0
        }
        for p in plans
    ]


@router.get("/plans")
async def list_plans(
    current_user: User = Depends(require_role([UserRole.PLATFORM_ADMIN])),
    db: Session = Depends(get_db)
):
    """List all subscription plans (admin only)"""
    plans = db.query(Plan).order_by(Plan.display_order).all()
    
    return [
        {
            "id": p.id,
            "name": p.name,
            "plan_type": p.plan_type.value,
            "monthly_price": float(p.monthly_price) if p.monthly_price else 0.0,
            "annual_price": float(p.annual_price) if p.annual_price else 0.0,
            "max_engineers": p.max_engineers,
            "features": p.features or {},
            "description": p.description or "",
            "is_active": p.is_active,
            "is_visible": p.is_visible,
            "display_order": p.display_order or 0
        }
        for p in plans
    ]


@router.post("/plans")
async def create_plan(
    plan_data: dict = Body(...),
    current_user: User = Depends(require_role([UserRole.PLATFORM_ADMIN])),
    db: Session = Depends(get_db)
):
    """Create a new subscription plan"""
    from app.models.subscription import PlanType
    
    plan = Plan(
        name=plan_data.get("name"),
        plan_type=PlanType(plan_data.get("plan_type", "starter")),
        monthly_price=plan_data.get("monthly_price", 0),
        annual_price=plan_data.get("annual_price", 0),
        max_engineers=plan_data.get("max_engineers"),
        features=plan_data.get("features", {}),
        description=plan_data.get("description"),
        is_active=plan_data.get("is_active", True),
        is_visible=plan_data.get("is_visible", True),
        display_order=plan_data.get("display_order", 0)
    )
    
    db.add(plan)
    db.commit()
    db.refresh(plan)
    
    return {
        "id": plan.id,
        "name": plan.name,
        "plan_type": plan.plan_type.value,
        "monthly_price": float(plan.monthly_price),
        "annual_price": float(plan.annual_price),
        "max_engineers": plan.max_engineers,
        "features": plan.features or {},
        "description": plan.description,
        "is_active": plan.is_active,
        "is_visible": plan.is_visible
    }


@router.put("/plans/{plan_id}")
async def update_plan(
    plan_id: int,
    plan_data: dict = Body(...),
    current_user: User = Depends(require_role([UserRole.PLATFORM_ADMIN])),
    db: Session = Depends(get_db)
):
    """Update a subscription plan"""
    plan = db.query(Plan).filter(Plan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    from app.models.subscription import PlanType
    
    if "name" in plan_data and plan_data["name"] is not None:
        plan.name = plan_data["name"]
    if "plan_type" in plan_data and plan_data["plan_type"] is not None:
        plan.plan_type = PlanType(plan_data["plan_type"])
    if "monthly_price" in plan_data and plan_data["monthly_price"] is not None:
        plan.monthly_price = plan_data["monthly_price"]
    if "annual_price" in plan_data and plan_data["annual_price"] is not None:
        plan.annual_price = plan_data["annual_price"]
    if "max_engineers" in plan_data:
        plan.max_engineers = plan_data["max_engineers"]
    if "features" in plan_data and plan_data["features"] is not None:
        plan.features = plan_data["features"]
    if "description" in plan_data:
        plan.description = plan_data["description"]
    if "is_active" in plan_data and plan_data["is_active"] is not None:
        plan.is_active = plan_data["is_active"]
    if "is_visible" in plan_data and plan_data["is_visible"] is not None:
        plan.is_visible = plan_data["is_visible"]
    if "display_order" in plan_data and plan_data["display_order"] is not None:
        plan.display_order = plan_data["display_order"]
    
    db.commit()
    db.refresh(plan)
    
    return {
        "id": plan.id,
        "name": plan.name,
        "plan_type": plan.plan_type.value,
        "monthly_price": float(plan.monthly_price),
        "annual_price": float(plan.annual_price),
        "max_engineers": plan.max_engineers,
        "features": plan.features or {},
        "description": plan.description,
        "is_active": plan.is_active,
        "is_visible": plan.is_visible
    }


@router.delete("/plans/{plan_id}")
async def delete_plan(
    plan_id: int,
    current_user: User = Depends(require_role([UserRole.PLATFORM_ADMIN])),
    db: Session = Depends(get_db)
):
    """Delete a subscription plan"""
    plan = db.query(Plan).filter(Plan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    db.delete(plan)
    db.commit()
    
    return {"message": "Plan deleted successfully"}


@router.get("/organizations")
async def list_all_organizations(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(require_role([UserRole.PLATFORM_ADMIN])),
    db: Session = Depends(get_db)
):
    """List all organizations with subscription details"""
    from sqlalchemy.orm import joinedload
    
    orgs = db.query(Organization).offset(skip).limit(limit).all()
    
    result = []
    for org in orgs:
        try:
            subscription = db.query(Subscription).filter(
                Subscription.organization_id == org.id
            ).options(joinedload(Subscription.plan)).first()
            
            vendor_org = db.query(VendorOrganization).filter(
                VendorOrganization.organization_id == org.id
            ).options(joinedload(VendorOrganization.vendor)).first()
            
            subscription_data = None
            if subscription:
                try:
                    subscription_data = {
                        "plan_name": subscription.plan.name if subscription.plan else None,
                        "status": str(subscription.status) if subscription.status else None,  # status is a String, not enum
                        "end_date": subscription.end_date.isoformat() if subscription.end_date else None
                    }
                except Exception as e:
                    print(f"Error processing subscription for org {org.id}: {e}")
                    import traceback
                    print(traceback.format_exc())
                    subscription_data = {
                        "plan_name": None,
                        "status": str(subscription.status) if subscription.status else None,
                        "end_date": subscription.end_date.isoformat() if subscription.end_date else None
                    }
            
            vendor_data = None
            if vendor_org and vendor_org.vendor:
                vendor_data = {
                    "vendor_id": vendor_org.vendor_id,
                    "vendor_name": vendor_org.vendor.name,
                    "vendor_code": vendor_org.vendor.vendor_code,
                    "signup_date": vendor_org.signup_date.isoformat() if vendor_org.signup_date else None
                }
            
            result.append({
                "id": org.id,
                "name": org.name,
                "org_type": org.org_type.value if org.org_type else None,
                "email": org.email,
                "is_active": org.is_active,
                "subscription": subscription_data,
                "vendor": vendor_data,
                "created_at": org.created_at.isoformat() if org.created_at else None
            })
        except Exception as e:
            import traceback
            print(f"Error processing organization {org.id}: {str(e)}")
            print(traceback.format_exc())
            result.append({
                "id": org.id,
                "name": org.name,
                "org_type": org.org_type.value if org.org_type else None,
                "email": org.email,
                "is_active": org.is_active,
                "subscription": None,
                "vendor": None,
                "created_at": org.created_at.isoformat() if org.created_at else None
            })
    
    return result


@router.get("/organizations/{organization_id}/details")
async def get_organization_details(
    organization_id: int,
    current_user: User = Depends(require_role([UserRole.PLATFORM_ADMIN])),
    db: Session = Depends(get_db)
):
    """Get comprehensive organization details"""
    from sqlalchemy.orm import joinedload
    from app.models.location import Country, State, City
    from app.models.user import User as UserModel
    import traceback
    
    try:
        org = db.query(Organization).options(
            joinedload(Organization.country),
            joinedload(Organization.state),
            joinedload(Organization.city)
        ).filter(Organization.id == organization_id).first()
        
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error loading organization: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error loading organization: {str(e)}")
    
    subscription = db.query(Subscription).filter(
        Subscription.organization_id == org.id
    ).options(joinedload(Subscription.plan)).first()
    
    vendor_org = db.query(VendorOrganization).filter(
        VendorOrganization.organization_id == org.id
    ).options(joinedload(VendorOrganization.vendor)).first()
    
    # Get users
    users = db.query(UserModel).filter(UserModel.organization_id == org.id).all()
    users_by_role = {}
    for user in users:
        if not user.role:
            continue
        role = user.role.value if hasattr(user.role, 'value') else str(user.role)
        if role not in users_by_role:
            users_by_role[role] = []
        users_by_role[role].append({
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "phone": user.phone,
            "is_active": user.is_active
        })
    
    # Get statistics
    try:
        total_tickets = db.query(Ticket).filter(Ticket.organization_id == organization_id).count()
    except Exception as e:
        print(f"Error counting tickets: {e}")
        total_tickets = 0
    
    try:
        total_devices = db.query(Device).filter(Device.organization_id == organization_id).count()
    except Exception as e:
        print(f"Error counting devices: {e}")
        total_devices = 0
    
    result = {
        "organization": {
            "id": org.id,
            "name": org.name,
            "org_type": org.org_type.value if org.org_type and hasattr(org.org_type, 'value') else (str(org.org_type) if org.org_type else None),
            "email": org.email,
            "phone": org.phone,
            "address": org.address,
            "is_active": org.is_active,
            "created_at": org.created_at.isoformat() if org.created_at else None
        },
        "location": {
            "country": org.country.name if org.country else None,
            "state": org.state.name if org.state else None,
            "city": org.city.name if org.city else None
        },
        "subscription": {
            "plan_name": subscription.plan.name if subscription and subscription.plan else None,
            "plan_type": subscription.plan.plan_type.value if subscription and subscription.plan and subscription.plan.plan_type and hasattr(subscription.plan.plan_type, 'value') else (str(subscription.plan.plan_type) if subscription and subscription.plan and subscription.plan.plan_type else None),
            "status": str(subscription.status) if subscription and subscription.status else None,  # status is a String, not enum
            "billing_period": subscription.billing_period.value if subscription and subscription.billing_period and hasattr(subscription.billing_period, 'value') else (str(subscription.billing_period) if subscription and subscription.billing_period else None),
            "current_price": float(subscription.current_price) if subscription and subscription.current_price is not None else None,
            "start_date": subscription.start_date.isoformat() if subscription and subscription.start_date else None,
            "end_date": subscription.end_date.isoformat() if subscription and subscription.end_date else None
        } if subscription else None,
        "billing": {
            "payment_method": subscription.payment_method if subscription else None,
            "last_payment_date": subscription.last_payment_date.isoformat() if subscription and subscription.last_payment_date else None,
            "next_billing_date": subscription.next_billing_date.isoformat() if subscription and subscription.next_billing_date else None
        } if subscription else None,
        "users": {
            "total": len(users),
            "by_role": users_by_role,
            "admin": [{"id": u.id, "full_name": u.full_name, "email": u.email, "phone": u.phone, "is_active": u.is_active} for u in users if u.role == UserRole.ORGANIZATION_ADMIN]
        },
        "statistics": {
            "total_tickets": total_tickets,
            "total_devices": total_devices
        }
    }
    
    # Add vendor information
    try:
        if vendor_org and vendor_org.vendor:
            result["vendor"] = {
                "vendor_id": vendor_org.vendor.id,
                "vendor_name": vendor_org.vendor.name,
                "vendor_code": vendor_org.vendor.vendor_code,
                "signup_date": vendor_org.signup_date.isoformat() if vendor_org.signup_date else None,
                "commission_earned": float(vendor_org.commission_earned) if vendor_org.commission_earned is not None else 0.0,
                "last_commission_date": vendor_org.last_commission_date.isoformat() if vendor_org.last_commission_date else None,
                "is_active": vendor_org.is_active
            }
    except Exception as e:
        print(f"Error processing vendor information: {e}")
        print(traceback.format_exc())
        # Continue without vendor info if there's an error
    
    return result


@router.get("/organizations/{organization_id}/kpis")
async def get_organization_kpis(
    organization_id: int,
    current_user: User = Depends(require_role([UserRole.PLATFORM_ADMIN])),
    db: Session = Depends(get_db)
):
    """Get organization KPIs"""
    from app.models.ticket import Ticket
    from app.models.user import User as UserModel
    
    org = db.query(Organization).filter(Organization.id == organization_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    total_tickets = db.query(Ticket).filter(Ticket.organization_id == organization_id).count()
    total_devices = db.query(Device).filter(Device.organization_id == organization_id).count()
    total_users = db.query(UserModel).filter(UserModel.organization_id == organization_id).count()
    
    return {
        "organization_id": organization_id,
        "total_tickets": total_tickets,
        "total_devices": total_devices,
        "total_users": total_users
    }


@router.post("/vendors")
async def create_vendor(
    vendor_data: dict = Body(...),
    current_user: User = Depends(require_role([UserRole.PLATFORM_ADMIN])),
    db: Session = Depends(get_db)
):
    """Create a new vendor"""
    from app.core.security import get_password_hash
    
    # Validate required fields - vendor and user use same email/phone
    required_fields = [
        "vendor_name", "user_email", "user_phone",
        "user_full_name", "user_password"
    ]
    
    for field in required_fields:
        if field not in vendor_data or not vendor_data[field]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required field: {field}"
            )
    
    # Use same email and phone for both vendor and user
    vendor_email = vendor_data["user_email"]
    vendor_phone = vendor_data["user_phone"]
    
    # Check if vendor email exists
    existing_vendor = db.query(Vendor).filter(Vendor.email == vendor_email).first()
    if existing_vendor:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vendor with this email already exists"
        )
    
    # Check if user email exists
    existing_user = db.query(User).filter(User.email == vendor_email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )
    
    # Check if user phone exists
    existing_phone = db.query(User).filter(User.phone == vendor_phone).first()
    if existing_phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this phone number already exists"
        )
    
    # Auto-generate vendor code
    last_vendor = db.query(Vendor).order_by(Vendor.id.desc()).first()
    if last_vendor and last_vendor.vendor_code:
        try:
            last_num = int(last_vendor.vendor_code.split('-')[-1])
            next_num = last_num + 1
        except (ValueError, IndexError):
            next_num = 1
    else:
        next_num = 1
    
    vendor_code = f"VENDOR-{next_num:03d}"
    
    while db.query(Vendor).filter(Vendor.vendor_code == vendor_code).first():
        next_num += 1
        vendor_code = f"VENDOR-{next_num:03d}"
    
    # Create user first
    user = User(
        email=vendor_email,
        phone=vendor_phone,
        password_hash=get_password_hash(vendor_data["user_password"]),
        full_name=vendor_data["user_full_name"],
        role=UserRole.VENDOR,
        country_id=vendor_data.get("country_id"),
        state_id=vendor_data.get("state_id"),
        city_id=vendor_data.get("city_id"),
        is_active=True,
        is_verified=False
    )
    
    db.add(user)
    db.flush()
    
    # Create vendor with same email and phone as user
    vendor = Vendor(
        name=vendor_data["vendor_name"],
        email=vendor_email,
        phone=vendor_phone,
        vendor_code=vendor_code,
        commission_rate=vendor_data.get("commission_rate", 0.15),
        country_id=vendor_data.get("country_id"),
        state_id=vendor_data.get("state_id"),
        city_id=vendor_data.get("city_id"),
        user_id=user.id,
        is_active=vendor_data.get("is_active", True)
    )
    
    db.add(vendor)
    db.commit()
    db.refresh(vendor)
    db.refresh(user)
    
    return {
        "vendor": {
            "id": vendor.id,
            "name": vendor.name,
            "vendor_code": vendor.vendor_code,
            "email": vendor.email,
            "commission_rate": vendor.commission_rate
        },
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value
        }
    }


@router.get("/vendors")
async def list_vendors(
    current_user: User = Depends(require_role([UserRole.PLATFORM_ADMIN])),
    db: Session = Depends(get_db)
):
    """List all vendors with performance metrics"""
    from sqlalchemy import func
    from datetime import datetime, timedelta, timezone
    
    vendors = db.query(Vendor).all()
    
    result = []
    for vendor in vendors:
        try:
            # Get vendor organizations
            vendor_orgs = db.query(VendorOrganization).filter(
                VendorOrganization.vendor_id == vendor.id
            ).all()
            
            active_orgs = [vo for vo in vendor_orgs if vo.is_active]
            total_commission = sum(vo.commission_earned or 0.0 for vo in vendor_orgs)
            
            # Calculate monthly commission (last 30 days) - use timezone-aware datetime
            thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
            monthly_commission = 0.0
            for vo in vendor_orgs:
                if vo.last_commission_date:
                    last_date = vo.last_commission_date
                    if last_date.tzinfo is None:
                        last_date = last_date.replace(tzinfo=timezone.utc)
                    if last_date >= thirty_days_ago:
                        monthly_commission += (vo.commission_earned or 0.0)
            
            # Get organization IDs for stats
            org_ids = [vo.organization_id for vo in vendor_orgs if vo.organization_id]
            
            # Get tickets and devices count
            total_tickets = 0
            total_devices = 0
            if org_ids:
                try:
                    total_tickets = db.query(Ticket).filter(Ticket.organization_id.in_(org_ids)).count()
                except Exception as e:
                    print(f"Error counting tickets for vendor {vendor.id}: {e}")
                    total_tickets = 0
                
                try:
                    total_devices = db.query(Device).filter(Device.organization_id.in_(org_ids)).count()
                except Exception as e:
                    print(f"Error counting devices for vendor {vendor.id}: {e}")
                    total_devices = 0
            
            # Recent signups (last 30 days)
            recent_signups = 0
            for vo in vendor_orgs:
                if vo.signup_date:
                    signup_dt = vo.signup_date
                    if signup_dt.tzinfo is None:
                        signup_dt = signup_dt.replace(tzinfo=timezone.utc)
                    if signup_dt >= thirty_days_ago:
                        recent_signups += 1
            
            result.append({
                "id": vendor.id,
                "name": vendor.name,
                "vendor_code": vendor.vendor_code,
                "email": vendor.email,
                "phone": vendor.phone or "",
                "commission_rate": float(vendor.commission_rate) if vendor.commission_rate else 0.0,
                "organizations_count": len(vendor_orgs),
                "active_organizations_count": len(active_orgs),
                "total_commission_earned": float(total_commission),
                "monthly_commission": float(monthly_commission),
                "total_tickets": total_tickets,
                "total_devices": total_devices,
                "recent_signups": recent_signups,
                "is_active": vendor.is_active,
                "created_at": vendor.created_at.isoformat() if vendor.created_at else None,
                "location": {
                    "country": vendor.country.name if vendor.country else None,
                    "state": vendor.state.name if vendor.state else None,
                    "city": vendor.city.name if vendor.city else None,
                    "country_id": vendor.country_id,
                    "state_id": vendor.state_id,
                    "city_id": vendor.city_id
                }
            })
        except Exception as e:
            import traceback
            print(f"Error processing vendor {vendor.id}: {str(e)}")
            print(traceback.format_exc())
            result.append({
                "id": vendor.id,
                "name": vendor.name,
                "vendor_code": vendor.vendor_code,
                "email": vendor.email,
                "phone": vendor.phone or "",
                "commission_rate": float(vendor.commission_rate) if vendor.commission_rate else 0.0,
                "organizations_count": 0,
                "active_organizations_count": 0,
                "total_commission_earned": 0.0,
                "monthly_commission": 0.0,
                "total_tickets": 0,
                "total_devices": 0,
                "recent_signups": 0,
                "is_active": vendor.is_active,
                "created_at": vendor.created_at.isoformat() if vendor.created_at else None,
                "location": {
                    "country": vendor.country.name if vendor.country else None,
                    "state": vendor.state.name if vendor.state else None,
                    "city": vendor.city.name if vendor.city else None,
                    "country_id": vendor.country_id,
                    "state_id": vendor.state_id,
                    "city_id": vendor.city_id
                }
            })
    
    return result


@router.get("/vendors/{vendor_id}/details")
async def get_vendor_details(
    vendor_id: int,
    current_user: User = Depends(require_role([UserRole.PLATFORM_ADMIN])),
    db: Session = Depends(get_db)
):
    """Get detailed vendor information including organizations and commissions"""
    from sqlalchemy.orm import joinedload
    from datetime import datetime, timedelta, timezone
    
    print(f"Fetching vendor details for vendor_id: {vendor_id} (type: {type(vendor_id)})")
    
    vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    print(f"Vendor query result: {vendor is not None}")
    
    if not vendor:
        print(f"Vendor with ID {vendor_id} not found in database")
        # Check if any vendors exist
        all_vendors = db.query(Vendor).all()
        print(f"Total vendors in database: {len(all_vendors)}")
        if all_vendors:
            print(f"Available vendor IDs: {[v.id for v in all_vendors]}")
        raise HTTPException(status_code=404, detail=f"Vendor with ID {vendor_id} not found")
    
    # Get vendor organizations
    vendor_orgs = db.query(VendorOrganization).filter(
        VendorOrganization.vendor_id == vendor.id
    ).options(
        joinedload(VendorOrganization.organization)
    ).all()
    
    # Get organization details with subscriptions
    organizations = []
    org_ids = []
    total_commission = 0.0
    active_orgs_count = 0
    
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    monthly_commission = 0.0
    recent_signups = 0
    
    for vo in vendor_orgs:
        org_ids.append(vo.organization_id)
        total_commission += (vo.commission_earned or 0.0)
        if vo.is_active:
            active_orgs_count += 1
        
        # Calculate monthly commission
        if vo.last_commission_date:
            last_date = vo.last_commission_date
            if last_date.tzinfo is None:
                last_date = last_date.replace(tzinfo=timezone.utc)
            if last_date >= thirty_days_ago:
                monthly_commission += (vo.commission_earned or 0.0)
        
        # Count recent signups
        if vo.signup_date:
            signup_dt = vo.signup_date
            if signup_dt.tzinfo is None:
                signup_dt = signup_dt.replace(tzinfo=timezone.utc)
            if signup_dt >= thirty_days_ago:
                recent_signups += 1
        
        org = vo.organization
        if not org:
            continue  # Skip if organization is missing
        
        subscription = None
        try:
            subscription = db.query(Subscription).filter(
                Subscription.organization_id == org.id
            ).options(joinedload(Subscription.plan)).first()
        except Exception as e:
            print(f"Error loading subscription for org {org.id}: {e}")
        
        # Get stats for this organization
        org_tickets = 0
        org_devices = 0
        try:
            org_tickets = db.query(Ticket).filter(Ticket.organization_id == org.id).count()
        except Exception as e:
            print(f"Error counting tickets for org {org.id}: {e}")
        
        try:
            org_devices = db.query(Device).filter(Device.organization_id == org.id).count()
        except Exception as e:
            print(f"Error counting devices for org {org.id}: {e}")
        
        subscription_data = None
        if subscription:
            try:
                subscription_data = {
                    "plan_name": subscription.plan.name if subscription.plan else None,
                    "status": subscription.status if subscription.status else None,
                    "billing_period": subscription.billing_period.value if subscription.billing_period else None,
                    "current_price": float(subscription.current_price) if subscription.current_price else None
                }
            except Exception as e:
                print(f"Error processing subscription data for org {org.id}: {e}")
                subscription_data = {
                    "plan_name": None,
                    "status": subscription.status if subscription else None,
                    "billing_period": None,
                    "current_price": None
                }
        
        organizations.append({
            "organization_id": org.id,
            "organization_name": org.name,
            "organization_email": org.email,
            "organization_phone": org.phone,
            "organization_type": org.org_type.value if org.org_type else None,
            "signup_date": vo.signup_date.isoformat() if vo.signup_date else None,
            "commission_earned": float(vo.commission_earned or 0.0),
            "last_commission_date": vo.last_commission_date.isoformat() if vo.last_commission_date else None,
            "is_active": vo.is_active,
            "subscription": subscription_data,
            "statistics": {
                "total_tickets": org_tickets,
                "total_devices": org_devices
            }
        })
    
    # Get total tickets and devices
    total_tickets = 0
    total_devices = 0
    if org_ids:
        total_tickets = db.query(Ticket).filter(Ticket.organization_id.in_(org_ids)).count()
        total_devices = db.query(Device).filter(Device.organization_id.in_(org_ids)).count()
    
    return {
        "vendor": {
            "id": vendor.id,
            "name": vendor.name,
            "vendor_code": vendor.vendor_code,
            "email": vendor.email,
            "phone": vendor.phone or "",
            "commission_rate": float(vendor.commission_rate) if vendor.commission_rate else 0.0,
            "is_active": vendor.is_active,
            "created_at": vendor.created_at.isoformat() if vendor.created_at else None
        },
        "location": {
            "country": vendor.country.name if vendor.country else None,
            "state": vendor.state.name if vendor.state else None,
            "city": vendor.city.name if vendor.city else None
        },
        "statistics": {
            "organizations_count": len(vendor_orgs),
            "active_organizations_count": active_orgs_count,
            "total_commission_earned": float(total_commission),
            "monthly_commission": float(monthly_commission),
            "total_tickets": total_tickets,
            "total_devices": total_devices,
            "recent_signups": recent_signups
        },
        "organizations": organizations
    }


@router.get("/analytics")
async def get_platform_analytics(
    period: str = "30d",  # 7d, 30d, 90d, 1y, all
    current_user: User = Depends(require_role([UserRole.PLATFORM_ADMIN])),
    db: Session = Depends(get_db)
):
    """Get platform-wide analytics and insights with advanced metrics"""
    from sqlalchemy import func, extract, case
    from datetime import datetime, timedelta, timezone
    from app.models.user import User as UserModel
    
    # Time ranges based on period
    now = datetime.now(timezone.utc)
    
    period_days = {
        "7d": 7,
        "30d": 30,
        "90d": 90,
        "1y": 365,
        "all": None
    }
    days = period_days.get(period, 30)
    
    if days:
        period_start = now - timedelta(days=days)
    else:
        period_start = datetime(2020, 1, 1, tzinfo=timezone.utc)
    
    thirty_days_ago = now - timedelta(days=30)
    sixty_days_ago = now - timedelta(days=60)
    one_year_ago = now - timedelta(days=365)
    previous_period_start = period_start - timedelta(days=days) if days else None
    
    # Basic counts
    total_organizations = db.query(Organization).count()
    active_organizations = db.query(Organization).filter(Organization.is_active == True).count()
    total_users = db.query(UserModel).count()
    total_tickets = db.query(Ticket).count()
    total_devices = db.query(Device).count()
    total_vendors = db.query(Vendor).count()
    active_vendors = db.query(Vendor).filter(Vendor.is_active == True).count()
    
    # Subscriptions
    total_subscriptions = db.query(Subscription).count()
    active_subscriptions = db.query(Subscription).filter(Subscription.status == "active").count()
    
    # Revenue calculations
    total_revenue = db.query(func.sum(Subscription.current_price)).filter(
        Subscription.status == "active"
    ).scalar() or 0.0
    
    monthly_revenue = db.query(func.sum(Subscription.current_price)).filter(
        Subscription.status == "active",
        Subscription.created_at >= thirty_days_ago
    ).scalar() or 0.0
    
    # Organization growth (last 30 days)
    new_organizations_30d = db.query(Organization).filter(
        Organization.created_at >= thirty_days_ago
    ).count()
    
    # User growth (last 30 days)
    new_users_30d = db.query(UserModel).filter(
        UserModel.created_at >= thirty_days_ago
    ).count()
    
    # Ticket statistics
    open_tickets = db.query(Ticket).filter(Ticket.status.in_(["created", "assigned", "in_progress"])).count()
    resolved_tickets = db.query(Ticket).filter(Ticket.status == "resolved").count()
    closed_tickets = db.query(Ticket).filter(Ticket.status == "closed").count()
    
    # Organization types distribution
    org_types = db.query(
        Organization.org_type,
        func.count(Organization.id).label('count')
    ).group_by(Organization.org_type).all()
    
    org_type_distribution = {
        org_type.value if hasattr(org_type, 'value') else str(org_type): count
        for org_type, count in org_types
    }
    
    # Subscription status distribution
    subscription_statuses = db.query(
        Subscription.status,
        func.count(Subscription.id).label('count')
    ).group_by(Subscription.status).all()
    
    subscription_status_distribution = {
        status: count for status, count in subscription_statuses
    }
    
    # Monthly signups (last 12 months)
    monthly_signups = []
    for i in range(12):
        month_start = now - timedelta(days=30 * (i + 1))
        month_end = now - timedelta(days=30 * i)
        count = db.query(Organization).filter(
            Organization.created_at >= month_start,
            Organization.created_at < month_end
        ).count()
        monthly_signups.append({
            "month": month_start.strftime("%Y-%m"),
            "count": count
        })
    monthly_signups.reverse()
    
    # Vendor commissions
    total_commissions = db.query(func.sum(VendorOrganization.commission_earned)).scalar() or 0.0
    monthly_commissions = db.query(func.sum(VendorOrganization.commission_earned)).filter(
        VendorOrganization.last_commission_date >= thirty_days_ago
    ).scalar() or 0.0
    
    # Top vendors by commission
    top_vendors = db.query(
        Vendor.name,
        Vendor.vendor_code,
        func.sum(VendorOrganization.commission_earned).label('total_commission'),
        func.count(VendorOrganization.id).label('org_count')
    ).join(
        VendorOrganization, Vendor.id == VendorOrganization.vendor_id
    ).group_by(
        Vendor.id, Vendor.name, Vendor.vendor_code
    ).order_by(
        func.sum(VendorOrganization.commission_earned).desc()
    ).limit(5).all()
    
    top_vendors_list = [
        {
            "name": name,
            "vendor_code": code,
            "total_commission": float(commission),
            "organizations_count": org_count
        }
        for name, code, commission, org_count in top_vendors
    ]
    
    # Advanced Metrics
    # MRR (Monthly Recurring Revenue)
    mrr = db.query(func.sum(Subscription.current_price)).filter(
        Subscription.status == "active",
        Subscription.billing_period == "monthly"
    ).scalar() or 0.0
    
    # ARR (Annual Recurring Revenue) - annual subscriptions * 12
    arr = db.query(func.sum(Subscription.current_price * 12)).filter(
        Subscription.status == "active",
        Subscription.billing_period == "annual"
    ).scalar() or 0.0
    
    # Churn rate calculation (cancelled subscriptions in last 30 days / total active at start)
    cancelled_30d = db.query(Subscription).filter(
        Subscription.status == "cancelled",
        Subscription.updated_at >= thirty_days_ago
    ).count()
    churn_rate = (cancelled_30d / active_subscriptions * 100) if active_subscriptions > 0 else 0.0
    
    # Average revenue per organization
    avg_revenue_per_org = (total_revenue / active_organizations) if active_organizations > 0 else 0.0
    
    # Ticket resolution rate
    resolution_rate = (resolved_tickets / total_tickets * 100) if total_tickets > 0 else 0.0
    
    # Daily trends (last 30 days)
    daily_signups = []
    daily_revenue = []
    for i in range(30):
        day_start = now - timedelta(days=30-i)
        day_end = now - timedelta(days=29-i)
        signups = db.query(Organization).filter(
            Organization.created_at >= day_start,
            Organization.created_at < day_end
        ).count()
        revenue = db.query(func.sum(Subscription.current_price)).filter(
            Subscription.status == "active",
            Subscription.created_at >= day_start,
            Subscription.created_at < day_end
        ).scalar() or 0.0
        daily_signups.append({
            "date": day_start.strftime("%Y-%m-%d"),
            "count": signups
        })
        daily_revenue.append({
            "date": day_start.strftime("%Y-%m-%d"),
            "revenue": float(revenue)
        })
    
    # Revenue by plan type
    revenue_by_plan = db.query(
        Plan.name,
        Plan.plan_type,
        func.sum(Subscription.current_price).label('revenue'),
        func.count(Subscription.id).label('count')
    ).join(
        Subscription, Plan.id == Subscription.plan_id
    ).filter(
        Subscription.status == "active"
    ).group_by(
        Plan.id, Plan.name, Plan.plan_type
    ).all()
    
    revenue_by_plan_list = [
        {
            "plan_name": name,
            "plan_type": plan_type.value if hasattr(plan_type, 'value') else str(plan_type),
            "revenue": float(revenue),
            "subscriptions": count
        }
        for name, plan_type, revenue, count in revenue_by_plan
    ]
    
    # Ticket trends (last 30 days)
    daily_tickets = []
    for i in range(30):
        day_start = now - timedelta(days=30-i)
        day_end = now - timedelta(days=29-i)
        created = db.query(Ticket).filter(
            Ticket.created_at >= day_start,
            Ticket.created_at < day_end
        ).count()
        resolved = db.query(Ticket).filter(
            Ticket.status == "resolved",
            Ticket.updated_at >= day_start,
            Ticket.updated_at < day_end
        ).count()
        daily_tickets.append({
            "date": day_start.strftime("%Y-%m-%d"),
            "created": created,
            "resolved": resolved
        })
    
    # User engagement (active users in last 7 days)
    seven_days_ago = now - timedelta(days=7)
    active_users_7d = db.query(UserModel).filter(
        UserModel.last_login >= seven_days_ago
    ).count()
    user_engagement_rate = (active_users_7d / total_users * 100) if total_users > 0 else 0.0
    
    return {
        "overview": {
            "total_organizations": total_organizations,
            "active_organizations": active_organizations,
            "total_users": total_users,
            "total_tickets": total_tickets,
            "total_devices": total_devices,
            "total_vendors": total_vendors,
            "active_vendors": active_vendors,
            "total_subscriptions": total_subscriptions,
            "active_subscriptions": active_subscriptions
        },
        "revenue": {
            "total_revenue": float(total_revenue),
            "monthly_revenue": float(monthly_revenue),
            "total_commissions_paid": float(total_commissions),
            "monthly_commissions_paid": float(monthly_commissions)
        },
        "growth": {
            "new_organizations_30d": new_organizations_30d,
            "new_users_30d": new_users_30d,
            "monthly_signups": monthly_signups
        },
        "tickets": {
            "total": total_tickets,
            "open": open_tickets,
            "resolved": resolved_tickets,
            "closed": closed_tickets
        },
        "distributions": {
            "organization_types": org_type_distribution,
            "subscription_statuses": subscription_status_distribution
        },
        "top_vendors": top_vendors_list,
        "advanced_metrics": {
            "mrr": float(mrr),
            "arr": float(arr),
            "churn_rate": float(churn_rate),
            "avg_revenue_per_org": float(avg_revenue_per_org),
            "resolution_rate": float(resolution_rate),
            "user_engagement_rate": float(user_engagement_rate),
            "active_users_7d": active_users_7d
        },
        "daily_trends": {
            "signups": daily_signups,
            "revenue": daily_revenue,
            "tickets": daily_tickets
        },
        "revenue_by_plan": revenue_by_plan_list
    }


@router.get("/settings")
async def get_platform_settings(
    category: str = None,
    current_user: User = Depends(require_role([UserRole.PLATFORM_ADMIN])),
    db: Session = Depends(get_db)
):
    """Get platform settings"""
    from app.models.platform_settings import PlatformSettings
    
    query = db.query(PlatformSettings)
    if category:
        query = query.filter(PlatformSettings.category == category)
    
    settings = query.all()
    
    # Return empty dict if no settings found (frontend will handle initialization)
    if not settings:
        return {}
    
    # Group by category
    result = {}
    for setting in settings:
        if setting.category not in result:
            result[setting.category] = {}
        
        # Parse value based on type
        value = setting.setting_value
        if setting.setting_type == "boolean":
            value = value.lower() in ("true", "1", "yes")
        elif setting.setting_type == "number":
            try:
                value = float(value) if "." in value else int(value)
            except (ValueError, TypeError):
                value = 0
        elif setting.setting_type == "json":
            try:
                import json
                value = json.loads(value) if value else {}
            except (ValueError, TypeError):
                value = {}
        
        result[setting.category][setting.setting_key] = {
            "value": value,
            "type": setting.setting_type,
            "description": setting.description,
            "is_public": setting.is_public
        }
    
    return result


@router.put("/settings")
async def update_platform_settings(
    settings_data: dict = Body(...),
    current_user: User = Depends(require_role([UserRole.PLATFORM_ADMIN])),
    db: Session = Depends(get_db)
):
    """Update platform settings"""
    from app.models.platform_settings import PlatformSettings
    import json
    
    updated_settings = []
    
    for category, settings in settings_data.items():
        for key, data in settings.items():
            setting = db.query(PlatformSettings).filter(
                PlatformSettings.setting_key == key
            ).first()
            
            # Convert value to string based on type
            value = data.get("value")
            setting_type = data.get("type", "string")
            
            if setting_type == "json":
                value_str = json.dumps(value) if value else "{}"
            elif setting_type == "boolean":
                value_str = "true" if value else "false"
            else:
                value_str = str(value) if value is not None else ""
            
            if setting:
                # Update existing
                setting.setting_value = value_str
                setting.setting_type = setting_type
                if "description" in data:
                    setting.description = data["description"]
            else:
                # Create new
                setting = PlatformSettings(
                    setting_key=key,
                    setting_value=value_str,
                    setting_type=setting_type,
                    category=category,
                    description=data.get("description"),
                    is_public=data.get("is_public", False)
                )
                db.add(setting)
            
            updated_settings.append(key)
    
    db.commit()
    
    return {
        "message": "Settings updated successfully",
        "updated_settings": updated_settings
    }


@router.post("/settings/initialize")
async def initialize_default_settings(
    current_user: User = Depends(require_role([UserRole.PLATFORM_ADMIN])),
    db: Session = Depends(get_db)
):
    """Initialize default platform settings"""
    from app.models.platform_settings import PlatformSettings
    import json
    
    default_settings = [
        # General Settings
        {"key": "platform_name", "value": "eRepairing Platform", "type": "string", "category": "general", "description": "Platform name"},
        {"key": "platform_email", "value": "admin@erepairing.com", "type": "string", "category": "general", "description": "Platform contact email"},
        {"key": "platform_phone", "value": "+911234567890", "type": "string", "category": "general", "description": "Platform contact phone"},
        {"key": "timezone", "value": "Asia/Kolkata", "type": "string", "category": "general", "description": "Platform timezone"},
        {"key": "currency", "value": "INR", "type": "string", "category": "general", "description": "Default currency"},
        {"key": "language", "value": "en", "type": "string", "category": "general", "description": "Default language"},
        {"key": "maintenance_mode", "value": "false", "type": "boolean", "category": "general", "description": "Enable maintenance mode"},
        
        # Billing Settings
        {"key": "default_commission_rate", "value": "0.15", "type": "number", "category": "billing", "description": "Default vendor commission rate (0-1)"},
        {"key": "tax_rate", "value": "0.18", "type": "number", "category": "billing", "description": "Default tax rate (GST)"},
        {"key": "payment_gateway", "value": "razorpay", "type": "string", "category": "billing", "description": "Payment gateway provider"},
        {"key": "auto_renew_subscriptions", "value": "true", "type": "boolean", "category": "billing", "description": "Auto-renew subscriptions"},
        {"key": "trial_period_days", "value": "14", "type": "number", "category": "billing", "description": "Trial period in days"},
        
        # Security Settings
        {"key": "password_min_length", "value": "8", "type": "number", "category": "security", "description": "Minimum password length"},
        {"key": "password_require_uppercase", "value": "true", "type": "boolean", "category": "security", "description": "Require uppercase in password"},
        {"key": "password_require_lowercase", "value": "true", "type": "boolean", "category": "security", "description": "Require lowercase in password"},
        {"key": "password_require_numbers", "value": "true", "type": "boolean", "category": "security", "description": "Require numbers in password"},
        {"key": "password_require_special", "value": "true", "type": "boolean", "category": "security", "description": "Require special characters in password"},
        {"key": "session_timeout_minutes", "value": "60", "type": "number", "category": "security", "description": "Session timeout in minutes"},
        {"key": "max_login_attempts", "value": "5", "type": "number", "category": "security", "description": "Maximum login attempts before lockout"},
        {"key": "enable_2fa", "value": "false", "type": "boolean", "category": "security", "description": "Enable two-factor authentication"},
        
        # Notification Settings
        {"key": "email_enabled", "value": "true", "type": "boolean", "category": "notifications", "description": "Enable email notifications"},
        {"key": "sms_enabled", "value": "false", "type": "boolean", "category": "notifications", "description": "Enable SMS notifications"},
        {"key": "push_enabled", "value": "true", "type": "boolean", "category": "notifications", "description": "Enable push notifications"},
        {"key": "notify_new_signup", "value": "true", "type": "boolean", "category": "notifications", "description": "Notify on new organization signup"},
        {"key": "notify_ticket_created", "value": "true", "type": "boolean", "category": "notifications", "description": "Notify on ticket creation"},
        {"key": "notify_ticket_resolved", "value": "true", "type": "boolean", "category": "notifications", "description": "Notify on ticket resolution"},
        
        # Feature Flags
        {"key": "ai_triage_enabled", "value": "true", "type": "boolean", "category": "features", "description": "Enable AI ticket triage"},
        {"key": "ai_forecasting_enabled", "value": "true", "type": "boolean", "category": "features", "description": "Enable AI demand forecasting"},
        {"key": "ai_chatbot_enabled", "value": "true", "type": "boolean", "category": "features", "description": "Enable AI chatbot"},
        {"key": "warranty_tracking_enabled", "value": "true", "type": "boolean", "category": "features", "description": "Enable warranty tracking"},
        {"key": "inventory_management_enabled", "value": "true", "type": "boolean", "category": "features", "description": "Enable inventory management"},
        {"key": "vendor_portal_enabled", "value": "true", "type": "boolean", "category": "features", "description": "Enable vendor portal"},
        
        # Integration Settings
        {"key": "webhook_url", "value": "", "type": "string", "category": "integrations", "description": "Webhook URL for events"},
        {"key": "api_rate_limit", "value": "1000", "type": "number", "category": "integrations", "description": "API rate limit per hour"},
        {"key": "enable_api_logging", "value": "true", "type": "boolean", "category": "integrations", "description": "Enable API request logging"},
    ]
    
    created = 0
    for setting_data in default_settings:
        existing = db.query(PlatformSettings).filter(
            PlatformSettings.setting_key == setting_data["key"]
        ).first()
        
        if not existing:
            setting = PlatformSettings(
                setting_key=setting_data["key"],
                setting_value=setting_data["value"],
                setting_type=setting_data["type"],
                category=setting_data["category"],
                description=setting_data.get("description"),
                is_public=False
            )
            db.add(setting)
            created += 1
    
    db.commit()
    
    return {
        "message": f"Initialized {created} default settings",
        "created": created
    }
