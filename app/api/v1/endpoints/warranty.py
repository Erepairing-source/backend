"""
Warranty endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from app.core.database import get_db
from app.core.permissions import get_current_user
from app.models.user import User, UserRole
from app.models.warranty import Warranty, WarrantyStatus
from app.models.device import Device
from app.models.integration import Integration, IntegrationType
from app.services.oem_warranty import OEMWarrantyService

router = APIRouter()
oem_service = OEMWarrantyService()


@router.get("/check")
async def check_warranty(
    serial_number: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Check warranty status by serial number"""
    device = db.query(Device).filter(Device.serial_number == serial_number).first()
    
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    # Get active warranty
    warranty = db.query(Warranty).filter(
        Warranty.device_id == device.id,
        Warranty.status == WarrantyStatus.ACTIVE
    ).first()
    
    if not warranty:
        return {
            "serial_number": serial_number,
            "warranty_status": "not_found",
            "in_warranty": False
        }
    
    is_in_warranty = datetime.utcnow() <= warranty.end_date
    
    return {
        "serial_number": serial_number,
        "warranty_status": warranty.status.value,
        "warranty_type": warranty.warranty_type,
        "start_date": warranty.start_date.isoformat(),
        "end_date": warranty.end_date.isoformat(),
        "in_warranty": is_in_warranty,
        "covered_parts": warranty.covered_parts,
        "covered_services": warranty.covered_services
    }


@router.post("/register")
async def register_warranty(
    device_id: int,
    warranty_type: str,
    start_date: datetime,
    end_date: datetime,
    covered_parts: Optional[list] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Register a warranty"""
    device = db.query(Device).filter(Device.id == device_id).first()
    
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    warranty = Warranty(
        device_id=device_id,
        organization_id=device.organization_id or current_user.organization_id,
        warranty_type=warranty_type,
        start_date=start_date,
        end_date=end_date,
        covered_parts=covered_parts or [],
        status=WarrantyStatus.ACTIVE
    )
    
    db.add(warranty)
    db.commit()
    db.refresh(warranty)
    
    return {
        "id": warranty.id,
        "warranty_number": warranty.warranty_number,
        "status": warranty.status.value
    }


@router.post("/sync")
async def sync_oem_warranty(
    payload: dict = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Sync warranty from OEM system using configured integration"""
    serial_number = payload.get("serial_number")
    device_id = payload.get("device_id")

    device = None
    if device_id:
        device = db.query(Device).filter(Device.id == device_id).first()
    elif serial_number:
        device = db.query(Device).filter(Device.serial_number == serial_number).first()

    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    # Access control: customer can only sync their own device
    if current_user.role == UserRole.CUSTOMER and device.customer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    integration = db.query(Integration).filter(
        Integration.organization_id == device.organization_id,
        Integration.integration_type == IntegrationType.API,
        Integration.is_active == True
    ).order_by(Integration.created_at.desc()).first()

    if not integration:
        raise HTTPException(status_code=400, detail="OEM warranty integration not configured")

    result = await oem_service.fetch_warranty(integration, device.serial_number)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])

    try:
        start_date = datetime.fromisoformat(result["start_date"])
        end_date = datetime.fromisoformat(result["end_date"])
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid warranty dates from OEM")

    warranty = Warranty(
        device_id=device.id,
        organization_id=device.organization_id,
        warranty_type=result.get("warranty_type"),
        start_date=start_date,
        end_date=end_date,
        covered_parts=result.get("covered_parts", []),
        covered_services=result.get("covered_services", []),
        warranty_number=result.get("warranty_number"),
        status=WarrantyStatus.ACTIVE
    )
    db.add(warranty)
    db.commit()
    db.refresh(warranty)

    return {
        "message": "OEM warranty synced",
        "warranty_id": warranty.id,
        "warranty_type": warranty.warranty_type,
        "end_date": warranty.end_date.isoformat()
    }


@router.post("/sync-all")
async def sync_oem_warranty_all(
    payload: dict = Body(default={}),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Sync OEM warranty for all devices in org (for org admins)"""
    if current_user.role != UserRole.ORGANIZATION_ADMIN:
        raise HTTPException(status_code=403, detail="Access denied")

    limit = payload.get("limit", 100)
    integration = db.query(Integration).filter(
        Integration.organization_id == current_user.organization_id,
        Integration.integration_type == IntegrationType.API,
        Integration.is_active == True
    ).order_by(Integration.created_at.desc()).first()

    if not integration:
        raise HTTPException(status_code=400, detail="OEM warranty integration not configured")

    devices = db.query(Device).filter(
        Device.organization_id == current_user.organization_id
    ).limit(limit).all()

    synced = 0
    failed = 0
    for device in devices:
        try:
            result = await oem_service.fetch_warranty(integration, device.serial_number)
            if result.get("error"):
                failed += 1
                continue
            start_date = datetime.fromisoformat(result["start_date"])
            end_date = datetime.fromisoformat(result["end_date"])
            existing = db.query(Warranty).filter(
                Warranty.device_id == device.id,
                Warranty.status == WarrantyStatus.ACTIVE
            ).first()
            if existing:
                existing.warranty_type = result.get("warranty_type")
                existing.start_date = start_date
                existing.end_date = end_date
                existing.covered_parts = result.get("covered_parts", [])
                existing.covered_services = result.get("covered_services", [])
                existing.warranty_number = result.get("warranty_number")
            else:
                db.add(Warranty(
                    device_id=device.id,
                    organization_id=device.organization_id,
                    warranty_type=result.get("warranty_type"),
                    start_date=start_date,
                    end_date=end_date,
                    covered_parts=result.get("covered_parts", []),
                    covered_services=result.get("covered_services", []),
                    warranty_number=result.get("warranty_number"),
                    status=WarrantyStatus.ACTIVE
                ))
            synced += 1
        except Exception:
            failed += 1

    integration.last_sync_at = datetime.utcnow()
    config = integration.config or {}
    config["last_sync_stats"] = {
        "synced": synced,
        "failed": failed,
        "total": len(devices),
        "ran_at": integration.last_sync_at.isoformat()
    }
    integration.config = config
    db.commit()
    return {"message": "OEM warranty sync complete", "synced": synced, "failed": failed}




