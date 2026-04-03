"""
Vendor endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from typing import List
from datetime import datetime, timedelta, timezone
from sqlalchemy import func

from app.core.database import get_db
from app.core.permissions import require_role, get_current_user
from app.models.user import User, UserRole
from app.models.subscription import Vendor, VendorOrganization, Subscription
from app.models.organization import Organization
from app.models.ticket import Ticket
from app.models.device import Device

router = APIRouter()


@router.get("/dashboard")
async def vendor_dashboard(
    current_user: User = Depends(require_role([UserRole.VENDOR])),
    db: Session = Depends(get_db)
):
    """Vendor dashboard with comprehensive stats and organizations"""
    try:
        # Get vendor
        vendor = db.query(Vendor).filter(Vendor.user_id == current_user.id).first()
        
        if not vendor:
            raise HTTPException(status_code=404, detail="Vendor profile not found")
        
        # Get all organizations signed up by this vendor
        try:
            vendor_orgs = db.query(VendorOrganization).filter(
                VendorOrganization.vendor_id == vendor.id
            ).options(joinedload(VendorOrganization.organization)).all()
        except Exception as e:
            print(f"Error loading vendor organizations: {str(e)}")
            vendor_orgs = []
        
        # Calculate statistics
        total_orgs = len(vendor_orgs)
        active_orgs = len([vo for vo in vendor_orgs if vo.is_active])
        total_commission = sum((vo.commission_earned or 0.0) for vo in vendor_orgs)
        
        # Get organization IDs
        org_ids = [vo.organization_id for vo in vendor_orgs if vo.organization_id]
        
        # Get tickets count for all vendor organizations
        total_tickets = db.query(Ticket).filter(Ticket.organization_id.in_(org_ids)).count() if org_ids else 0
        
        # Get devices count (use raw SQL to avoid model column issues - devices table doesn't have product_id/product_model_id)
        if org_ids:
            try:
                # Use parameterized query for safety
                placeholders = ','.join([':org_id_' + str(i) for i in range(len(org_ids))])
                params = {f'org_id_{i}': org_id for i, org_id in enumerate(org_ids)}
                result = db.execute(
                    text(f"SELECT COUNT(*) FROM devices WHERE organization_id IN ({placeholders})"),
                    params
                )
                total_devices = result.scalar() or 0
            except Exception as e:
                print(f"Error counting devices: {str(e)}")
                import traceback
                traceback.print_exc()
                total_devices = 0
        else:
            total_devices = 0
        
        # Calculate monthly commission (last 30 days)
        now = datetime.now(timezone.utc)
        thirty_days_ago = now - timedelta(days=30)
        
        monthly_commission = 0.0
        for vo in vendor_orgs:
            if vo.last_commission_date:
                last_date = vo.last_commission_date
                if last_date.tzinfo is None:
                    last_date = last_date.replace(tzinfo=timezone.utc)
                if last_date >= thirty_days_ago:
                    monthly_commission += (vo.commission_earned or 0.0)
        
        # Recent organizations (last 30 days)
        recent_orgs = []
        for vo in vendor_orgs:
            if vo.signup_date:
                signup_dt = vo.signup_date
                if signup_dt.tzinfo is None:
                    signup_dt = signup_dt.replace(tzinfo=timezone.utc)
                if signup_dt >= thirty_days_ago:
                    recent_orgs.append(vo)
        
        # Get detailed organization list
        organizations = []
        for vo in vendor_orgs[:10]:  # Limit to 10 most recent
            if not vo.organization:
                continue  # Skip if organization is None
                
            try:
                org = vo.organization
                subscription = db.query(Subscription).filter(
                    Subscription.organization_id == org.id
                ).options(joinedload(Subscription.plan)).first()
                
                # Get organization stats
                org_tickets = db.query(Ticket).filter(Ticket.organization_id == org.id).count()
                try:
                    # Use parameterized query for safety
                    result = db.execute(
                        text("SELECT COUNT(*) FROM devices WHERE organization_id = :org_id"),
                        {"org_id": org.id}
                    )
                    org_devices = result.scalar() or 0
                except Exception as e:
                    print(f"Error counting devices for org {org.id}: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    org_devices = 0
                
                organizations.append({
                    "organization_id": org.id,
                    "organization_name": org.name,
                    "organization_email": org.email,
                    "organization_type": org.org_type.value if org.org_type else None,
                    "signup_date": vo.signup_date.isoformat() if vo.signup_date else None,
                    "subscription_plan": subscription.plan.name if subscription and subscription.plan else None,
                    "subscription_status": subscription.status.value if subscription else None,
                    "commission_earned": float(vo.commission_earned or 0.0),
                    "commission_rate": float(vendor.commission_rate or 0.15),
                    "last_commission_date": vo.last_commission_date.isoformat() if vo.last_commission_date else None,
                    "is_active": vo.is_active,
                    "org_is_active": org.is_active,
                    "total_tickets": org_tickets,
                    "total_devices": org_devices
                })
            except Exception as e:
                import traceback
                print(f"Error processing organization {vo.organization_id}: {str(e)}")
                print(traceback.format_exc())
                continue
        
        return {
            "vendor": {
                "id": vendor.id,
                "name": vendor.name,
                "vendor_code": vendor.vendor_code,
                "email": vendor.email,
                "phone": vendor.phone,
                "commission_rate": float(vendor.commission_rate or 0.15),
                "is_active": vendor.is_active
            },
            "statistics": {
                "total_organizations": total_orgs,
                "active_organizations": active_orgs,
                "total_commission_earned": float(total_commission),
                "monthly_commission": float(monthly_commission),
                "total_tickets": total_tickets,
                "total_devices": total_devices,
                "recent_signups": len(recent_orgs)
            },
            "organizations": organizations
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"Error in vendor_dashboard: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load vendor dashboard: {str(e)}"
        )


@router.get("/organizations")
async def list_vendor_organizations(
    current_user: User = Depends(require_role([UserRole.VENDOR])),
    db: Session = Depends(get_db)
):
    """List all organizations signed up by this vendor with detailed information"""
    vendor = db.query(Vendor).filter(Vendor.user_id == current_user.id).first()
    
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor profile not found")
    
    vendor_orgs = db.query(VendorOrganization).filter(
        VendorOrganization.vendor_id == vendor.id
    ).options(joinedload(VendorOrganization.organization)).all()
    
    result = []
    for vo in vendor_orgs:
        org = vo.organization
        subscription = db.query(Subscription).filter(
            Subscription.organization_id == org.id
        ).options(joinedload(Subscription.plan)).first()
        
        # Get organization stats
        org_tickets = db.query(Ticket).filter(Ticket.organization_id == org.id).count()
        org_devices = db.query(Device).filter(Device.organization_id == org.id).count()
        
        result.append({
            "vendor_org_id": vo.id,
            "organization_id": org.id,
            "organization_name": org.name,
            "organization_email": org.email,
            "organization_phone": org.phone,
            "organization_type": org.org_type.value if org.org_type else None,
            "organization_address": org.address,
            "signup_date": vo.signup_date.isoformat() if vo.signup_date else None,
            "subscription": {
                "plan_name": subscription.plan.name if subscription and subscription.plan else None,
                "status": subscription.status.value if subscription else None,
                "billing_period": subscription.billing_period.value if subscription else None,
                "current_price": float(subscription.current_price) if subscription else None
            } if subscription else None,
            "commission": {
                "earned": float(vo.commission_earned or 0.0),
                "rate": float(vendor.commission_rate or 0.15),
                "last_payment_date": vo.last_commission_date.isoformat() if vo.last_commission_date else None
            },
            "statistics": {
                "total_tickets": org_tickets,
                "total_devices": org_devices
            },
            "is_active": vo.is_active,
            "org_is_active": org.is_active
        })
    
    return result


@router.get("/organizations/{organization_id}")
async def get_vendor_organization_details(
    organization_id: int,
    current_user: User = Depends(require_role([UserRole.VENDOR])),
    db: Session = Depends(get_db)
):
    """Get detailed information about a specific organization signed up by this vendor"""
    vendor = db.query(Vendor).filter(Vendor.user_id == current_user.id).first()
    
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor profile not found")
    
    # Check if this organization belongs to this vendor
    vendor_org = db.query(VendorOrganization).filter(
        VendorOrganization.vendor_id == vendor.id,
        VendorOrganization.organization_id == organization_id
    ).options(joinedload(VendorOrganization.organization)).first()
    
    if not vendor_org:
        raise HTTPException(status_code=404, detail="Organization not found or not associated with this vendor")
    
    org = vendor_org.organization
    subscription = db.query(Subscription).filter(
        Subscription.organization_id == org.id
    ).options(joinedload(Subscription.plan)).first()
    
    # Get detailed stats
    from app.models.location import Country, State, City
    
    return {
        "vendor_org": {
            "id": vendor_org.id,
            "signup_date": vendor_org.signup_date.isoformat() if vendor_org.signup_date else None,
            "commission_earned": float(vendor_org.commission_earned or 0.0),
            "last_commission_date": vendor_org.last_commission_date.isoformat() if vendor_org.last_commission_date else None,
            "is_active": vendor_org.is_active
        },
        "organization": {
            "id": org.id,
            "name": org.name,
            "email": org.email,
            "phone": org.phone,
            "address": org.address,
            "org_type": org.org_type.value if org.org_type else None,
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
            "plan_type": subscription.plan.plan_type.value if subscription and subscription.plan else None,
            "status": subscription.status.value if subscription else None,
            "billing_period": subscription.billing_period.value if subscription else None,
            "current_price": float(subscription.current_price) if subscription else None,
            "start_date": subscription.start_date.isoformat() if subscription and subscription.start_date else None,
            "end_date": subscription.end_date.isoformat() if subscription and subscription.end_date else None
        } if subscription else None,
        "commission": {
            "rate": float(vendor.commission_rate or 0.15),
            "earned": float(vendor_org.commission_earned or 0.0),
            "last_payment": vendor_org.last_commission_date.isoformat() if vendor_org.last_commission_date else None
        }
    }


@router.get("/commissions")
async def get_vendor_commissions(
    current_user: User = Depends(require_role([UserRole.VENDOR])),
    db: Session = Depends(get_db)
):
    """Get commission history and earnings for the vendor"""
    vendor = db.query(Vendor).filter(Vendor.user_id == current_user.id).first()
    
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor profile not found")
    
    vendor_orgs = db.query(VendorOrganization).filter(
        VendorOrganization.vendor_id == vendor.id
    ).options(joinedload(VendorOrganization.organization)).all()
    
    # Calculate commission breakdown
    total_commission = sum((vo.commission_earned or 0.0) for vo in vendor_orgs)
    
    # Monthly breakdown (last 12 months)
    monthly_breakdown = []
    for i in range(12):
        month_start = datetime.now().replace(day=1) - timedelta(days=30 * i)
        month_end = month_start + timedelta(days=30)
        
        month_commission = sum(
            (vo.commission_earned or 0.0) for vo in vendor_orgs
            if vo.last_commission_date and month_start <= vo.last_commission_date < month_end
        )
        
        monthly_breakdown.append({
            "month": month_start.strftime("%Y-%m"),
            "commission": float(month_commission),
            "organizations": len([
                vo for vo in vendor_orgs
                if vo.last_commission_date and month_start <= vo.last_commission_date < month_end
            ])
        })
    
    # Commission by organization
    org_commissions = []
    for vo in vendor_orgs:
        org = vo.organization
        subscription = db.query(Subscription).filter(
            Subscription.organization_id == org.id
        ).first()
        
        org_commissions.append({
            "organization_id": org.id,
            "organization_name": org.name,
            "commission_earned": float(vo.commission_earned or 0.0),
            "commission_rate": float(vendor.commission_rate or 0.15),
            "subscription_value": float(subscription.current_price) if subscription else 0.0,
            "last_payment_date": vo.last_commission_date.isoformat() if vo.last_commission_date else None,
            "signup_date": vo.signup_date.isoformat() if vo.signup_date else None
        })
    
    return {
        "vendor": {
            "id": vendor.id,
            "name": vendor.name,
            "vendor_code": vendor.vendor_code,
            "commission_rate": float(vendor.commission_rate or 0.15)
        },
        "summary": {
            "total_commission_earned": float(total_commission),
            "total_organizations": len(vendor_orgs),
            "average_commission_per_org": float(total_commission / len(vendor_orgs)) if vendor_orgs else 0.0
        },
        "monthly_breakdown": monthly_breakdown,
        "organization_commissions": org_commissions
    }


@router.get("/analytics")
async def get_vendor_analytics(
    current_user: User = Depends(require_role([UserRole.VENDOR])),
    db: Session = Depends(get_db)
):
    """Get comprehensive analytics for vendor"""
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import func
    
    vendor = db.query(Vendor).filter(Vendor.user_id == current_user.id).first()
    
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor profile not found")
    
    # Get vendor organizations
    vendor_orgs = db.query(VendorOrganization).filter(
        VendorOrganization.vendor_id == vendor.id
    ).options(joinedload(VendorOrganization.organization)).all()
    
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)
    sixty_days_ago = now - timedelta(days=60)
    
    # Calculate metrics
    total_orgs = len(vendor_orgs)
    active_orgs = len([vo for vo in vendor_orgs if vo.is_active])
    total_commission = sum(vo.commission_earned or 0.0 for vo in vendor_orgs)
    
    # Monthly commission
    monthly_commission = 0.0
    for vo in vendor_orgs:
        if vo.last_commission_date:
            last_date = vo.last_commission_date
            if last_date.tzinfo is None:
                last_date = last_date.replace(tzinfo=timezone.utc)
            if last_date >= thirty_days_ago:
                monthly_commission += (vo.commission_earned or 0.0)
    
    # Recent signups
    recent_signups = 0
    for vo in vendor_orgs:
        if vo.signup_date:
            signup_dt = vo.signup_date
            if signup_dt.tzinfo is None:
                signup_dt = signup_dt.replace(tzinfo=timezone.utc)
            if signup_dt >= thirty_days_ago:
                recent_signups += 1
    
    # Get organization IDs
    org_ids = [vo.organization_id for vo in vendor_orgs if vo.organization_id]
    
    # Get tickets and devices
    total_tickets = 0
    total_devices = 0
    if org_ids:
        total_tickets = db.query(Ticket).filter(Ticket.organization_id.in_(org_ids)).count()
        total_devices = db.query(Device).filter(Device.organization_id.in_(org_ids)).count()
    
    # Monthly signups (last 12 months)
    monthly_signups = []
    for i in range(12):
        month_start = now - timedelta(days=30 * (i + 1))
        month_end = now - timedelta(days=30 * i)
        count = len([
            vo for vo in vendor_orgs
            if vo.signup_date and month_start <= vo.signup_date.replace(tzinfo=timezone.utc if vo.signup_date.tzinfo is None else None) < month_end
        ])
        monthly_signups.append({
            "month": month_start.strftime("%Y-%m"),
            "count": count
        })
    monthly_signups.reverse()
    
    # Monthly commissions (last 12 months)
    monthly_commissions = []
    for i in range(12):
        month_start = now - timedelta(days=30 * (i + 1))
        month_end = now - timedelta(days=30 * i)
        commission = sum(
            vo.commission_earned or 0.0 for vo in vendor_orgs
            if vo.last_commission_date and month_start <= vo.last_commission_date.replace(tzinfo=timezone.utc if vo.last_commission_date.tzinfo is None else None) < month_end
        )
        monthly_commissions.append({
            "month": month_start.strftime("%Y-%m"),
            "commission": float(commission)
        })
    monthly_commissions.reverse()
    
    # Top organizations by commission
    top_orgs = sorted(
        [
            {
                "organization_id": vo.organization_id,
                "organization_name": vo.organization.name if vo.organization else "Unknown",
                "commission_earned": float(vo.commission_earned or 0.0),
                "signup_date": vo.signup_date.isoformat() if vo.signup_date else None
            }
            for vo in vendor_orgs
        ],
        key=lambda x: x["commission_earned"],
        reverse=True
    )[:5]
    
    return {
        "vendor": {
            "id": vendor.id,
            "name": vendor.name,
            "vendor_code": vendor.vendor_code,
            "commission_rate": float(vendor.commission_rate or 0.15)
        },
        "overview": {
            "total_organizations": total_orgs,
            "active_organizations": active_orgs,
            "total_commission_earned": float(total_commission),
            "monthly_commission": float(monthly_commission),
            "recent_signups_30d": recent_signups,
            "total_tickets": total_tickets,
            "total_devices": total_devices
        },
        "trends": {
            "monthly_signups": monthly_signups,
            "monthly_commissions": monthly_commissions
        },
        "top_organizations": top_orgs
    }


