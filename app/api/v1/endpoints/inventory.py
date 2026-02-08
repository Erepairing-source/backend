"""
Inventory endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.database import get_db
from app.core.permissions import get_current_user, require_role
from app.models.user import User, UserRole
from app.models.inventory import Inventory, Part, ReorderRequest
from app.models.location import City

router = APIRouter()


@router.get("/parts")
async def list_parts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all parts"""
    parts = db.query(Part).filter(Part.is_active == True).all()
    
    return [
        {
            "id": p.id,
            "sku": p.sku,
            "name": p.name,
            "description": p.description,
            "cost_price": p.cost_price,
            "selling_price": p.selling_price
        }
        for p in parts
    ]


@router.get("/stock")
async def get_inventory(
    city_id: Optional[int] = None,
    state_id: Optional[int] = None,
    part_id: Optional[int] = None,
    low_stock_only: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get inventory levels"""
    if not current_user.organization_id:
        raise HTTPException(status_code=400, detail="User must be associated with an organization")

    query = db.query(Inventory).filter(Inventory.organization_id == current_user.organization_id)

    if current_user.role in [UserRole.CITY_ADMIN, UserRole.SUPPORT_ENGINEER]:
        if not current_user.city_id:
            raise HTTPException(status_code=400, detail="User must be assigned to a city")
        if city_id and int(city_id) != current_user.city_id:
            raise HTTPException(status_code=403, detail="City filter not allowed")
        query = query.filter(Inventory.city_id == current_user.city_id)
    elif current_user.role == UserRole.STATE_ADMIN:
        if not current_user.state_id:
            raise HTTPException(status_code=400, detail="User must be assigned to a state")
        if state_id and int(state_id) != current_user.state_id:
            raise HTTPException(status_code=403, detail="State filter not allowed")
        if city_id:
            city = db.query(City).filter(City.id == city_id, City.state_id == current_user.state_id).first()
            if not city:
                raise HTTPException(status_code=403, detail="City not in your state")
            query = query.filter(Inventory.city_id == city_id)
        else:
            city_ids = [c.id for c in db.query(City).filter(City.state_id == current_user.state_id).all()]
            query = query.filter(Inventory.city_id.in_(city_ids))
    elif current_user.role == UserRole.COUNTRY_ADMIN:
        if current_user.country_id:
            query = query.filter(Inventory.country_id == current_user.country_id)
    else:
        query = query

    if current_user.role != UserRole.ORGANIZATION_ADMIN:
        query = query.filter(Inventory.city_id.isnot(None))
    
    if city_id:
        query = query.filter(Inventory.city_id == city_id)
    if state_id:
        query = query.filter(Inventory.state_id == state_id)
    if part_id:
        query = query.filter(Inventory.part_id == part_id)
    if low_stock_only:
        query = query.filter(Inventory.is_low_stock == True)
    
    inventory_items = query.all()
    
    return [
        {
            "id": inv.id,
            "part_id": inv.part_id,
            "part_name": inv.part.name,
            "sku": inv.part.sku,
            "current_stock": inv.current_stock,
            "min_threshold": inv.min_threshold,
            "is_low_stock": inv.is_low_stock,
            "city_id": inv.city_id,
            "state_id": inv.state_id
        }
        for inv in inventory_items
    ]


@router.get("/reorder-requests")
async def list_reorder_requests(
    status: Optional[str] = None,
    current_user: User = Depends(require_role([
        UserRole.CITY_ADMIN,
        UserRole.STATE_ADMIN,
        UserRole.ORGANIZATION_ADMIN
    ])),
    db: Session = Depends(get_db)
):
    """List reorder requests"""
    query = db.query(ReorderRequest).filter(
        ReorderRequest.organization_id == current_user.organization_id
    )
    if current_user.role == UserRole.CITY_ADMIN:
        if not current_user.city_id:
            raise HTTPException(status_code=400, detail="User must be assigned to a city")
        query = query.join(Inventory, Inventory.id == ReorderRequest.inventory_id).filter(
            Inventory.city_id == current_user.city_id
        )
    elif current_user.role == UserRole.STATE_ADMIN:
        if not current_user.state_id:
            raise HTTPException(status_code=400, detail="User must be assigned to a state")
        city_ids = [c.id for c in db.query(City).filter(City.state_id == current_user.state_id).all()]
        query = query.join(Inventory, Inventory.id == ReorderRequest.inventory_id).filter(
            Inventory.city_id.in_(city_ids)
        )
    
    if status:
        query = query.filter(ReorderRequest.status == status)
    
    requests = query.all()
    
    return [
        {
            "id": req.id,
            "part_id": req.part_id,
            "part_name": req.part.name,
            "requested_quantity": req.requested_quantity,
            "current_stock": req.current_stock,
            "status": req.status,
            "created_at": req.created_at.isoformat()
        }
        for req in requests
    ]


@router.post("/reorder-requests/{request_id}/approve")
async def approve_reorder(
    request_id: int,
    current_user: User = Depends(require_role([
        UserRole.STATE_ADMIN,
        UserRole.ORGANIZATION_ADMIN
    ])),
    db: Session = Depends(get_db)
):
    """Approve reorder request"""
    request = db.query(ReorderRequest).filter(ReorderRequest.id == request_id).first()
    
    if not request:
        raise HTTPException(status_code=404, detail="Reorder request not found")
    
    if current_user.role == UserRole.STATE_ADMIN:
        if not current_user.state_id:
            raise HTTPException(status_code=400, detail="User must be assigned to a state")
        inventory = db.query(Inventory).filter(Inventory.id == request.inventory_id).first()
        if not inventory or inventory.city_id is None:
            raise HTTPException(status_code=404, detail="Inventory not found for request")
        city = db.query(City).filter(City.id == inventory.city_id).first()
        if not city or city.state_id != current_user.state_id:
            raise HTTPException(status_code=403, detail="Request not in your state")

    request.status = "approved"
    request.approved_by_id = current_user.id
    from datetime import datetime
    request.approved_at = datetime.utcnow()
    
    db.commit()
    
    return {"message": "Reorder request approved"}




