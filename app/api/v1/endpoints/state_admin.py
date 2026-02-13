"""
State Admin endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from typing import Optional, List

from app.core.database import get_db
from app.core.permissions import require_role
from sqlalchemy import func
from datetime import datetime, timedelta, timezone

from app.models.user import User, UserRole
from app.models.ticket import Ticket, TicketStatus, TicketComment
from app.models.location import City, State, Country
from app.data.india_locations import INDIA_CITIES_BY_STATE


def _india_cities_for_state(state_name: str) -> List[str]:
    """Return list of city names for an Indian state from app.data.india_locations. Empty if not found."""
    if not state_name:
        return []
    key = state_name.strip()
    if key in INDIA_CITIES_BY_STATE:
        return list(INDIA_CITIES_BY_STATE[key])
    key_lower = key.lower()
    for k, cities in INDIA_CITIES_BY_STATE.items():
        if k.strip().lower() == key_lower:
            return list(cities)
    return []
from app.models.device import Device
from app.models.inventory import Inventory, InventoryTransaction, Part
from app.models.notification import Notification, NotificationType, NotificationChannel, NotificationStatus
from app.models.sla_policy import SLAPolicy, ServicePolicy, SLAType
from app.services.ai.demand_forecasting import DemandForecastingService

router = APIRouter()
forecast_service = DemandForecastingService()


def pick_available_engineer_state(db: Session, state_id: int, city_id: Optional[int], organization_id: Optional[int]):
    query = db.query(User).filter(
        User.state_id == state_id,
        User.role == UserRole.SUPPORT_ENGINEER,
        User.is_available == True
    )
    if city_id:
        query = query.filter(User.city_id == city_id)
    if organization_id:
        query = query.filter(User.organization_id == organization_id)
    engineers = query.all()
    if not engineers:
        return None

    engineer_ids = [e.id for e in engineers]
    counts = dict(
        db.query(Ticket.assigned_engineer_id, func.count(Ticket.id))
        .filter(
            Ticket.assigned_engineer_id.in_(engineer_ids),
            Ticket.status.in_([TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS])
        )
        .group_by(Ticket.assigned_engineer_id)
        .all()
    )
    return min(engineers, key=lambda e: counts.get(e.id, 0))


@router.get("/dashboard")
async def get_state_dashboard(
    time_range: str = "30d",
    current_user: User = Depends(require_role([UserRole.STATE_ADMIN])),
    db: Session = Depends(get_db)
):
    """Get state-wide dashboard statistics"""
    if not current_user.state_id:
        raise HTTPException(status_code=400, detail="User must be assigned to a state")
    
    # Get all cities in this state only — tickets are scoped to this state's cities
    cities = db.query(City).filter(City.state_id == current_user.state_id).all()
    city_ids = [city.id for city in cities]

    # Calculate statistics (tickets in this state's cities only; also scoped to org when assigned)
    base_tickets = db.query(Ticket).filter(Ticket.city_id.in_(city_ids))
    if current_user.organization_id:
        base_tickets = base_tickets.filter(Ticket.organization_id == current_user.organization_id)
    total_tickets = base_tickets.count()
    
    resolved_tickets = db.query(Ticket).filter(
        Ticket.city_id.in_(city_ids),
        Ticket.status == TicketStatus.RESOLVED
    )
    if current_user.organization_id:
        resolved_tickets = resolved_tickets.filter(Ticket.organization_id == current_user.organization_id)
    resolved_tickets = resolved_tickets.count()
    sla_compliance = (resolved_tickets / total_tickets * 100) if total_tickets > 0 else 0
    
    # Calculate MTTR (Mean Time To Resolution) from actual ticket data
    resolved_with_times_q = db.query(Ticket).filter(
        Ticket.city_id.in_(city_ids),
        Ticket.status == TicketStatus.RESOLVED,
        Ticket.created_at.isnot(None),
        Ticket.resolved_at.isnot(None)
    )
    if current_user.organization_id:
        resolved_with_times_q = resolved_with_times_q.filter(Ticket.organization_id == current_user.organization_id)
    resolved_with_times = resolved_with_times_q.all()
    
    if resolved_with_times:
        total_time = sum((t.resolved_at - t.created_at).total_seconds() / 3600 for t in resolved_with_times)
        mttr = max(total_time / len(resolved_with_times), 0.0)
    else:
        mttr = 0.0
    
    # Count repeat visits (tickets with same device)
    repeat_q = db.query(
        Ticket.device_id,
        func.count(Ticket.id).label('ticket_count')
    ).filter(
        Ticket.city_id.in_(city_ids),
        Ticket.device_id.isnot(None)
    )
    if current_user.organization_id:
        repeat_q = repeat_q.filter(Ticket.organization_id == current_user.organization_id)
    device_ticket_counts = repeat_q.group_by(Ticket.device_id).having(func.count(Ticket.id) > 1).count()
    repeat_visits = device_ticket_counts
    
    # Count stockout incidents from inventory transactions
    try:
        stockout_incidents = db.query(InventoryTransaction).filter(
            InventoryTransaction.transaction_type == "stockout"
        ).count()
    except Exception:
        stockout_incidents = 0

    # For Indian states, show full city (district) count so StatCard matches full list
    state_record = db.query(State).filter(State.id == current_user.state_id).first()
    total_cities_display = len(cities)
    if state_record:
        country = db.query(Country).filter(Country.id == state_record.country_id).first()
        if country:
            code = (country.code or "").strip().upper()
            name = (country.name or "").strip().lower()
            if code in ("IN", "IND") or name == "india" or "india" in name:
                full_districts = _india_cities_for_state(state_record.name)
                if full_districts:
                    total_cities_display = len(full_districts)
    
    return {
        "totalCities": total_cities_display,
        "totalTickets": total_tickets,
        "slaCompliance": round(sla_compliance, 2),
        "mttr": mttr,
        "repeatVisits": repeat_visits,
        "stockoutIncidents": stockout_incidents
    }


def _city_metrics_row(city, db: Session, current_user: User) -> dict:
    """Build one city row with SLA/MTTR/repeatVisits from DB."""
    city_tickets_q = db.query(Ticket).filter(Ticket.city_id == city.id)
    if current_user.organization_id:
        city_tickets_q = city_tickets_q.filter(Ticket.organization_id == current_user.organization_id)
    city_tickets = city_tickets_q.all()
    resolved = [t for t in city_tickets if t.status == TicketStatus.RESOLVED]
    sla_compliance = (len(resolved) / len(city_tickets) * 100) if city_tickets else 0
    resolved_with_times = [t for t in resolved if t.created_at and t.resolved_at]
    if resolved_with_times:
        total_time = sum((t.resolved_at - t.created_at).total_seconds() / 3600 for t in resolved_with_times)
        mttr = max(total_time / len(resolved_with_times), 0.0)
    else:
        mttr = 0.0
    device_counts_q = db.query(
        Ticket.device_id,
        func.count(Ticket.id).label('count')
    ).filter(
        Ticket.city_id == city.id,
        Ticket.device_id.isnot(None)
    )
    if current_user.organization_id:
        device_counts_q = device_counts_q.filter(Ticket.organization_id == current_user.organization_id)
    device_counts = device_counts_q.group_by(Ticket.device_id).having(func.count(Ticket.id) > 1).count()
    if sla_compliance >= 90:
        status = "healthy"
    elif sla_compliance >= 70:
        status = "warning"
    else:
        status = "critical"
    return {
        "id": city.id,
        "name": city.name,
        "slaCompliance": round(sla_compliance, 2),
        "mttr": round(mttr, 2),
        "repeatVisits": device_counts,
        "stockoutIncidents": 0,
        "status": status,
        "hq_latitude": getattr(city, "hq_latitude", None),
        "hq_longitude": getattr(city, "hq_longitude", None),
    }


@router.get("/cities")
async def get_state_cities(
    current_user: User = Depends(require_role([UserRole.STATE_ADMIN])),
    db: Session = Depends(get_db)
):
    """Get all cities in the state with performance metrics. For India, returns all districts (zeros if not in DB)."""
    if not current_user.state_id:
        raise HTTPException(status_code=400, detail="User must be assigned to a state")
    
    cities = db.query(City).filter(City.state_id == current_user.state_id).all()
    state_record = db.query(State).filter(State.id == current_user.state_id).first()
    result = []

    # For Indian states, return all districts so the list is complete
    is_india = False
    full_districts = []
    if state_record:
        country = db.query(Country).filter(Country.id == state_record.country_id).first()
        if country:
            code = (country.code or "").strip().upper()
            name = (country.name or "").strip().lower()
            if code in ("IN", "IND") or name == "india" or "india" in name:
                is_india = True
                full_districts = _india_cities_for_state(state_record.name)

    if is_india and full_districts:
        db_city_by_name = {c.name.strip().lower(): c for c in cities}
        added_city_ids = set()  # DB cities we already added (when a district name matched)
        for dist_name in full_districts:
            if not dist_name or not isinstance(dist_name, str):
                continue
            dist_name = dist_name.strip()
            name_lower = dist_name.lower()
            if name_lower in db_city_by_name:
                city = db_city_by_name[name_lower]
                added_city_ids.add(city.id)
                result.append(_city_metrics_row(city, db, current_user))
            else:
                result.append({
                    "id": None,
                    "name": dist_name,
                    "slaCompliance": 0,
                    "mttr": 0,
                    "repeatVisits": 0,
                    "stockoutIncidents": 0,
                    "status": "critical",
                    "hq_latitude": None,
                    "hq_longitude": None,
                })
        # Include any DB city that didn't match a district name (e.g. "Bangalore" vs "Bengaluru Urban")
        # so their ticket counts show in the table and total matches the dashboard.
        for city in cities:
            if city.id not in added_city_ids:
                result.append(_city_metrics_row(city, db, current_user))
        return result

    # Non-India: only cities present in DB
    for city in cities:
        result.append(_city_metrics_row(city, db, current_user))
    return result


@router.get("/resource-balancing")
async def get_resource_balancing(
    current_user: User = Depends(require_role([UserRole.STATE_ADMIN])),
    db: Session = Depends(get_db)
):
    """Get resource balancing data across cities"""
    if not current_user.state_id:
        raise HTTPException(status_code=400, detail="User must be assigned to a state")
    
    # Get engineers by city
    cities = db.query(City).filter(City.state_id == current_user.state_id).all()
    
    result = []
    for city in cities:
        engineers = db.query(User).filter(
            User.city_id == city.id,
            User.role == UserRole.SUPPORT_ENGINEER
        ).all()
        
        active_tickets = db.query(Ticket).filter(
            Ticket.city_id == city.id,
            Ticket.status.in_(["assigned", "in_progress"])
        ).count()
        
        result.append({
            "cityId": city.id,
            "cityName": city.name,
            "engineers": len(engineers),
            "availableEngineers": len([e for e in engineers if e.is_available]),
            "activeTickets": active_tickets,
            "workload": active_tickets / len(engineers) if engineers else 0
        })
    
    return result


@router.post("/inventory/transfer")
async def transfer_inventory(
    transfer_data: dict = Body(...),
    current_user: User = Depends(require_role([UserRole.STATE_ADMIN])),
    db: Session = Depends(get_db)
):
    """Transfer inventory between cities in the state from database"""
    if not current_user.state_id:
        raise HTTPException(status_code=400, detail="User must be assigned to a state")
    
    from_city_id = transfer_data.get("from_city_id")
    to_city_id = transfer_data.get("to_city_id")
    part_id = transfer_data.get("part_id")
    quantity = transfer_data.get("quantity")
    notes = transfer_data.get("notes", "")
    
    if not all([from_city_id, to_city_id, part_id, quantity]):
        raise HTTPException(status_code=400, detail="Missing required fields: from_city_id, to_city_id, part_id, quantity")
    
    if from_city_id == to_city_id:
        raise HTTPException(status_code=400, detail="Source and destination cities must be different")
    
    # Verify both cities are in the same state from database
    from_city = db.query(City).filter(City.id == from_city_id).first()
    to_city = db.query(City).filter(City.id == to_city_id).first()
    
    if not from_city or not to_city:
        raise HTTPException(status_code=404, detail="City not found")
    
    if from_city.state_id != current_user.state_id or to_city.state_id != current_user.state_id:
        raise HTTPException(status_code=403, detail="Both cities must be in your state")
    
    # Get source inventory from database
    from_inventory = db.query(Inventory).filter(
        Inventory.part_id == part_id,
        Inventory.city_id == from_city_id,
        Inventory.organization_id == current_user.organization_id
    ).first()
    
    if not from_inventory:
        raise HTTPException(status_code=404, detail="Source inventory not found")
    
    if from_inventory.current_stock < quantity:
        raise HTTPException(status_code=400, detail=f"Insufficient stock. Available: {from_inventory.current_stock}")
    
    # Get or create destination inventory from database
    to_inventory = db.query(Inventory).filter(
        Inventory.part_id == part_id,
        Inventory.city_id == to_city_id,
        Inventory.organization_id == current_user.organization_id
    ).first()
    
    state = db.query(State).filter(State.id == current_user.state_id).first()
    country_id = state.country_id if state else None

    if not to_inventory:
        # Create new inventory entry for destination city
        part = db.query(Part).filter(Part.id == part_id).first()
        if not part:
            raise HTTPException(status_code=404, detail="Part not found")
        
        to_inventory = Inventory(
            part_id=part_id,
            organization_id=current_user.organization_id,
            country_id=country_id,
            city_id=to_city_id,
            state_id=current_user.state_id,
            current_stock=0,
            min_threshold=from_inventory.min_threshold,
            max_threshold=from_inventory.max_threshold
        )
        db.add(to_inventory)
        db.flush()
    
    # Deduct from source
    from_previous_stock = from_inventory.current_stock
    from_inventory.current_stock -= quantity
    from_inventory.is_low_stock = from_inventory.current_stock <= from_inventory.min_threshold
    
    # Add to destination
    to_previous_stock = to_inventory.current_stock
    to_inventory.current_stock += quantity
    to_inventory.is_low_stock = to_inventory.current_stock <= to_inventory.min_threshold
    
    # Create transaction logs from database
    from_transaction = InventoryTransaction(
        part_id=part_id,
        inventory_id=from_inventory.id,
        transaction_type="out",
        quantity=quantity,
        previous_stock=from_previous_stock,
        new_stock=from_inventory.current_stock,
        performed_by_id=current_user.id,
        notes=f"Transferred to city {to_city.name}. {notes}"
    )
    
    to_transaction = InventoryTransaction(
        part_id=part_id,
        inventory_id=to_inventory.id,
        transaction_type="in",
        quantity=quantity,
        previous_stock=to_previous_stock,
        new_stock=to_inventory.current_stock,
        performed_by_id=current_user.id,
        notes=f"Transferred from city {from_city.name}. {notes}"
    )
    
    db.add(from_transaction)
    db.add(to_transaction)
    db.commit()
    
    return {
        "message": "Inventory transferred successfully",
        "from_city": from_city.name,
        "to_city": to_city.name,
        "part_id": part_id,
        "quantity": quantity,
        "from_stock_after": from_inventory.current_stock,
        "to_stock_after": to_inventory.current_stock
    }


@router.get("/inventory/parts")
async def get_state_inventory_parts(
    current_user: User = Depends(require_role([UserRole.STATE_ADMIN])),
    db: Session = Depends(get_db)
):
    """Get inventory parts grouped by city for the state"""
    if not current_user.state_id:
        raise HTTPException(status_code=400, detail="User must be assigned to a state")

    cities = db.query(City).filter(City.state_id == current_user.state_id).all()
    city_ids = [c.id for c in cities]

    inventory_items = db.query(Inventory).filter(
        Inventory.city_id.in_(city_ids),
        Inventory.organization_id == current_user.organization_id
    ).all()

    parts_map = {}
    city_lookup = {c.id: c.name for c in cities}
    for inv in inventory_items:
        key = inv.part_id
        if key not in parts_map:
            parts_map[key] = {
                "part_id": inv.part_id,
                "part_name": inv.part.name,
                "sku": inv.part.sku,
                "cities": []
            }
        parts_map[key]["cities"].append({
            "city_id": inv.city_id,
            "city_name": city_lookup.get(inv.city_id, "Unknown"),
            "current_stock": inv.current_stock
        })

    return list(parts_map.values())


@router.get("/engineers/reallocations")
async def list_engineers_for_reallocation(
    current_user: User = Depends(require_role([UserRole.STATE_ADMIN])),
    db: Session = Depends(get_db)
):
    """List engineers in the state for reallocation (current city, workload)"""
    if not current_user.state_id:
        raise HTTPException(status_code=400, detail="User must be assigned to a state")
    engineers = db.query(User).filter(
        User.state_id == current_user.state_id,
        User.role == UserRole.SUPPORT_ENGINEER,
        User.organization_id == current_user.organization_id,
        User.is_active == True
    ).all()
    result = []
    for e in engineers:
        city_name = None
        if e.city_id:
            city = db.query(City).filter(City.id == e.city_id).first()
            city_name = city.name if city else None
        assigned = db.query(Ticket).filter(
            Ticket.assigned_engineer_id == e.id,
            Ticket.status.in_([TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS])
        ).count()
        result.append({
            "id": e.id,
            "full_name": e.full_name,
            "email": e.email,
            "city_id": e.city_id,
            "city_name": city_name,
            "assigned_tickets": assigned,
            "is_available": e.is_available,
        })
    return result


@router.post("/engineers/reallocate")
async def reallocate_engineer(
    reallocate_data: dict = Body(...),
    current_user: User = Depends(require_role([UserRole.STATE_ADMIN])),
    db: Session = Depends(get_db)
):
    """Reallocate engineer from one city to another in the state from database"""
    if not current_user.state_id:
        raise HTTPException(status_code=400, detail="User must be assigned to a state")
    
    engineer_id = reallocate_data.get("engineer_id")
    to_city_id = reallocate_data.get("to_city_id")
    reason = reallocate_data.get("reason", "")
    
    if not engineer_id or not to_city_id:
        raise HTTPException(status_code=400, detail="Missing required fields: engineer_id, to_city_id")
    
    # Get engineer from database
    engineer = db.query(User).filter(
        User.id == engineer_id,
        User.role == UserRole.SUPPORT_ENGINEER,
        User.organization_id == current_user.organization_id
    ).first()
    
    if not engineer:
        raise HTTPException(status_code=404, detail="Engineer not found")
    
    # Verify engineer is in the same state
    if engineer.state_id != current_user.state_id:
        raise HTTPException(status_code=403, detail="Engineer must be in your state")
    
    # Verify destination city is in the same state
    to_city = db.query(City).filter(City.id == to_city_id).first()
    if not to_city:
        raise HTTPException(status_code=404, detail="Destination city not found")
    
    if to_city.state_id != current_user.state_id:
        raise HTTPException(status_code=403, detail="Destination city must be in your state")
    
    # Reallocate engineer
    from_city_id = engineer.city_id
    engineer.city_id = to_city_id
    
    db.commit()
    
    return {
        "message": "Engineer reallocated successfully",
        "engineer_id": engineer_id,
        "engineer_name": engineer.full_name,
        "from_city_id": from_city_id,
        "to_city_id": to_city_id,
        "reason": reason
    }


@router.get("/cities/{city_id}/overview")
async def get_city_overview(
    city_id: int,
    current_user: User = Depends(require_role([UserRole.STATE_ADMIN])),
    db: Session = Depends(get_db)
):
    """Get overview for a single city"""
    if not current_user.state_id:
        raise HTTPException(status_code=400, detail="User must be assigned to a state")

    city = db.query(City).filter(City.id == city_id, City.state_id == current_user.state_id).first()
    if not city:
        raise HTTPException(status_code=404, detail="City not found")

    tickets = db.query(Ticket).filter(Ticket.city_id == city_id).all()
    total_tickets = len(tickets)
    resolved = [t for t in tickets if t.status == TicketStatus.RESOLVED]
    open_tickets = len([t for t in tickets if t.status in [TicketStatus.CREATED, TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS]])
    sla_compliance = (len(resolved) / total_tickets * 100) if total_tickets else 0

    return {
        "city": {"id": city.id, "name": city.name},
        "stats": {
            "total_tickets": total_tickets,
            "open_tickets": open_tickets,
            "resolved_tickets": len(resolved),
            "sla_compliance": round(sla_compliance, 2)
        }
    }


@router.get("/cities/{city_id}/tickets")
async def get_city_tickets(
    city_id: int,
    current_user: User = Depends(require_role([UserRole.STATE_ADMIN])),
    db: Session = Depends(get_db)
):
    """List tickets for a city"""
    if not current_user.state_id:
        raise HTTPException(status_code=400, detail="User must be assigned to a state")

    city = db.query(City).filter(City.id == city_id, City.state_id == current_user.state_id).first()
    if not city:
        raise HTTPException(status_code=404, detail="City not found")

    tickets = db.query(Ticket).filter(Ticket.city_id == city_id).order_by(Ticket.created_at.desc()).all()
    return [
        {
            "id": t.id,
            "ticket_number": t.ticket_number,
            "status": t.status.value,
            "priority": t.priority.value,
            "issue_category": t.issue_category,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "assigned_engineer_id": t.assigned_engineer_id
        }
        for t in tickets
    ]


@router.get("/cities/{city_id}/engineers")
async def get_city_engineers(
    city_id: int,
    current_user: User = Depends(require_role([UserRole.STATE_ADMIN])),
    db: Session = Depends(get_db)
):
    """List engineers for a city"""
    if not current_user.state_id:
        raise HTTPException(status_code=400, detail="User must be assigned to a state")

    city = db.query(City).filter(City.id == city_id, City.state_id == current_user.state_id).first()
    if not city:
        raise HTTPException(status_code=404, detail="City not found")

    engineers = db.query(User).filter(
        User.city_id == city_id,
        User.role == UserRole.SUPPORT_ENGINEER,
        User.organization_id == current_user.organization_id
    ).all()

    result = []
    for engineer in engineers:
        assigned_tickets = db.query(Ticket).filter(
            Ticket.assigned_engineer_id == engineer.id,
            Ticket.status.in_([TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS])
        ).count()
        result.append({
            "id": engineer.id,
            "name": engineer.full_name,
            "email": engineer.email,
            "phone": engineer.phone,
            "is_available": engineer.is_available,
            "skill_level": engineer.engineer_skill_level,
            "assigned_tickets": assigned_tickets
        })
    return result


@router.get("/cities/{city_id}/inventory")
async def get_city_inventory(
    city_id: int,
    current_user: User = Depends(require_role([UserRole.STATE_ADMIN])),
    db: Session = Depends(get_db)
):
    """List inventory for a city"""
    if not current_user.state_id:
        raise HTTPException(status_code=400, detail="User must be assigned to a state")

    city = db.query(City).filter(City.id == city_id, City.state_id == current_user.state_id).first()
    if not city:
        raise HTTPException(status_code=404, detail="City not found")

    inventory_items = db.query(Inventory).filter(
        Inventory.city_id == city_id,
        Inventory.organization_id == current_user.organization_id
    ).all()

    return [
        {
            "id": inv.id,
            "part_id": inv.part_id,
            "part_name": inv.part.name,
            "sku": inv.part.sku,
            "current_stock": inv.current_stock,
            "min_threshold": inv.min_threshold,
            "is_low_stock": inv.is_low_stock
        }
        for inv in inventory_items
    ]


@router.post("/cities/{city_id}/hq")
async def update_city_hq_state(
    city_id: int,
    payload: dict = Body(...),
    current_user: User = Depends(require_role([UserRole.STATE_ADMIN])),
    db: Session = Depends(get_db)
):
    """Update HQ coordinates for a city in this state"""
    if not current_user.state_id:
        raise HTTPException(status_code=400, detail="User must be assigned to a state")
    city = db.query(City).filter(City.id == city_id, City.state_id == current_user.state_id).first()
    if not city:
        raise HTTPException(status_code=404, detail="City not found")

    city.hq_latitude = payload.get("hq_latitude")
    city.hq_longitude = payload.get("hq_longitude")
    db.commit()
    return {"message": "City HQ updated"}


@router.get("/cities/{city_id}/complaints")
async def get_city_complaints(
    city_id: int,
    current_user: User = Depends(require_role([UserRole.STATE_ADMIN])),
    db: Session = Depends(get_db)
):
    """List negative feedback for a city"""
    if not current_user.state_id:
        raise HTTPException(status_code=400, detail="User must be assigned to a state")

    city = db.query(City).filter(City.id == city_id, City.state_id == current_user.state_id).first()
    if not city:
        raise HTTPException(status_code=404, detail="City not found")

    tickets = db.query(Ticket).filter(
        Ticket.city_id == city_id,
        Ticket.customer_rating <= 2
    ).order_by(Ticket.updated_at.desc()).all()

    return [
        {
            "id": t.id,
            "ticket_number": t.ticket_number,
            "customer_rating": t.customer_rating,
            "customer_feedback": t.customer_feedback,
            "customer_dispute_tags": t.customer_dispute_tags or [],
            "resolved_at": t.resolved_at.isoformat() if t.resolved_at else None
        }
        for t in tickets
    ]


@router.post("/complaints/{ticket_id}/follow-up")
async def create_state_complaint_follow_up(
    ticket_id: int,
    follow_up_data: dict = Body(...),
    current_user: User = Depends(require_role([UserRole.STATE_ADMIN])),
    db: Session = Depends(get_db)
):
    """Log follow-up action for a complaint ticket in the state"""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.state_id != current_user.state_id:
        raise HTTPException(status_code=403, detail="Ticket not in your state")

    action_type = follow_up_data.get("action_type") or "follow_up"
    notes = follow_up_data.get("notes") or ""
    preferred_date = follow_up_data.get("preferred_date")
    goodwill = follow_up_data.get("goodwill")
    create_follow_up_ticket = bool(follow_up_data.get("create_follow_up_ticket"))
    engineer_id = follow_up_data.get("engineer_id")
    if engineer_id is not None:
        try:
            engineer_id = int(engineer_id)
        except (TypeError, ValueError):
            engineer_id = None
    follow_up_preferred_dt = None
    if preferred_date:
        try:
            follow_up_preferred_dt = datetime.fromisoformat(preferred_date.replace('Z', '+00:00'))
        except Exception:
            follow_up_preferred_dt = None

    assigned_engineer = None
    if engineer_id:
        assigned_engineer = db.query(User).filter(
            User.id == engineer_id,
            User.state_id == current_user.state_id,
            User.role == UserRole.SUPPORT_ENGINEER
        ).first()
        if not assigned_engineer:
            raise HTTPException(status_code=404, detail="Engineer not found in your state")
    elif create_follow_up_ticket:
        assigned_engineer = pick_available_engineer_state(
            db,
            current_user.state_id,
            ticket.city_id,
            ticket.organization_id
        )

    comment = TicketComment(
        ticket_id=ticket.id,
        user_id=current_user.id,
        comment_text=f"Follow-up action: {action_type}. Notes: {notes}",
        comment_type="follow_up",
        extra_data={
            "action_type": action_type,
            "preferred_date": preferred_date,
            "goodwill": goodwill,
            "create_follow_up_ticket": create_follow_up_ticket
        }
    )
    db.add(comment)

    follow_up_ticket_id = None
    if create_follow_up_ticket:
        from app.models.ticket import TicketPriority
        follow_up_priority = ticket.priority
        if ticket.sla_breach_risk and ticket.sla_breach_risk > 0.7:
            follow_up_priority = TicketPriority.URGENT
        new_ticket_number = f"TKT-{datetime.utcnow().strftime('%Y%m%d')}-{db.query(Ticket).count() + 1:06d}"
        follow_up_ticket = Ticket(
            ticket_number=new_ticket_number,
            organization_id=ticket.organization_id,
            customer_id=ticket.customer_id,
            device_id=ticket.device_id,
            created_by_id=current_user.id,
            parent_ticket_id=ticket.id,
            issue_description=f"Follow-up visit for ticket {ticket.ticket_number}. {notes}".strip(),
            issue_photos=ticket.issue_photos or [],
            service_address=ticket.service_address,
            service_latitude=ticket.service_latitude,
            service_longitude=ticket.service_longitude,
            priority=follow_up_priority,
            issue_category=ticket.issue_category,
            status=TicketStatus.ASSIGNED if assigned_engineer else TicketStatus.CREATED,
            assigned_engineer_id=assigned_engineer.id if assigned_engineer else None,
            assigned_by_id=current_user.id if assigned_engineer else None,
            assigned_at=datetime.now(timezone.utc) if assigned_engineer else None,
            city_id=ticket.city_id,
            state_id=ticket.state_id,
            country_id=ticket.country_id,
            follow_up_preferred_date=follow_up_preferred_dt
        )
        db.add(follow_up_ticket)
        db.flush()
        follow_up_ticket_id = follow_up_ticket.id

        if ticket.customer_id:
            channels = [NotificationChannel.IN_APP]
            if ticket.contact_preferences:
                if "sms" in ticket.contact_preferences:
                    channels.append(NotificationChannel.SMS)
                if "whatsapp" in ticket.contact_preferences:
                    channels.append(NotificationChannel.WHATSAPP)
            for channel in channels:
                notification = Notification(
                    organization_id=ticket.organization_id,
                    user_id=ticket.customer_id,
                    notification_type=NotificationType.TICKET_UPDATED,
                    channel=channel,
                    title="Follow-up visit scheduled",
                    message=f"A follow-up visit was scheduled for ticket {ticket.ticket_number}.",
                    ticket_id=follow_up_ticket_id,
                    status=NotificationStatus.PENDING,
                    action_url=f"/customer/ticket/{follow_up_ticket_id}"
                )
                db.add(notification)
        if assigned_engineer:
            notification = Notification(
                organization_id=ticket.organization_id,
                user_id=assigned_engineer.id,
                notification_type=NotificationType.TICKET_ASSIGNED,
                channel=NotificationChannel.IN_APP,
                title="New follow-up ticket assigned",
                message=f"Follow-up ticket {new_ticket_number} has been assigned to you.",
                ticket_id=follow_up_ticket_id,
                status=NotificationStatus.PENDING,
                action_url=f"/engineer/ticket/{follow_up_ticket_id}"
            )
            db.add(notification)

    db.commit()
    return {"message": "Follow-up action logged", "follow_up_ticket_id": follow_up_ticket_id}


@router.post("/tickets/bulk-reassign")
async def bulk_reassign_tickets_state(
    reassign_data: dict = Body(...),
    current_user: User = Depends(require_role([UserRole.STATE_ADMIN])),
    db: Session = Depends(get_db)
):
    """Bulk reassign tickets to an engineer within the state"""
    ticket_ids = reassign_data.get("ticket_ids") or []
    engineer_id = reassign_data.get("engineer_id")
    if not ticket_ids or not engineer_id:
        raise HTTPException(status_code=400, detail="ticket_ids and engineer_id are required")

    engineer = db.query(User).filter(
        User.id == engineer_id,
        User.state_id == current_user.state_id,
        User.role == UserRole.SUPPORT_ENGINEER
    ).first()
    if not engineer:
        raise HTTPException(status_code=404, detail="Engineer not found in your state")

    tickets = db.query(Ticket).filter(
        Ticket.id.in_(ticket_ids),
        Ticket.state_id == current_user.state_id
    ).all()
    if not tickets:
        raise HTTPException(status_code=404, detail="No matching tickets found")

    for ticket in tickets:
        comment = TicketComment(
            ticket_id=ticket.id,
            user_id=current_user.id,
            comment_text=f"Ticket reassigned from engineer {ticket.assigned_engineer_id} to {engineer_id}",
            comment_type="reassignment"
        )
        db.add(comment)
        ticket.assigned_engineer_id = engineer_id
        ticket.assigned_by_id = current_user.id
        ticket.assigned_at = datetime.now(timezone.utc)
        ticket.status = TicketStatus.ASSIGNED

    db.commit()
    return {"message": f"Reassigned {len(tickets)} tickets"}


@router.get("/sla-risk")
async def get_state_sla_risk(
    min_risk: float = 0.4,
    city_id: Optional[int] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    limit: int = 100,
    current_user: User = Depends(require_role([UserRole.STATE_ADMIN])),
    db: Session = Depends(get_db)
):
    """List tickets at risk of SLA breach for the state"""
    if not current_user.state_id:
        raise HTTPException(status_code=400, detail="User must be assigned to a state")

    query = db.query(Ticket).filter(
        Ticket.state_id == current_user.state_id,
        Ticket.sla_breach_risk.isnot(None),
        Ticket.sla_breach_risk >= min_risk
    )

    if city_id:
        query = query.filter(Ticket.city_id == city_id)
    if status:
        try:
            query = query.filter(Ticket.status == TicketStatus(status))
        except ValueError:
            pass
    if priority:
        try:
            from app.models.ticket import TicketPriority
            query = query.filter(Ticket.priority == TicketPriority(priority))
        except ValueError:
            pass

    tickets = query.order_by(Ticket.sla_breach_risk.desc()).limit(limit).all()

    return [
        {
            "id": t.id,
            "ticket_number": t.ticket_number,
            "status": t.status.value,
            "priority": t.priority.value,
            "issue_category": t.issue_category,
            "sla_breach_risk": t.sla_breach_risk,
            "sla_deadline": t.sla_deadline.isoformat() if t.sla_deadline else None,
            "city_id": t.city_id,
            "created_at": t.created_at.isoformat() if t.created_at else None
        }
        for t in tickets
    ]


@router.get("/compliance-alerts")
async def get_state_compliance_alerts(
    current_user: User = Depends(require_role([UserRole.STATE_ADMIN])),
    db: Session = Depends(get_db)
):
    """Return compliance alerts for cities with high SLA risk ratios"""
    if not current_user.state_id:
        raise HTTPException(status_code=400, detail="User must be assigned to a state")

    cities = db.query(City).filter(City.state_id == current_user.state_id).all()
    alerts = []
    for city in cities:
        total = db.query(Ticket).filter(Ticket.city_id == city.id).count()
        at_risk = db.query(Ticket).filter(
            Ticket.city_id == city.id,
            Ticket.sla_breach_risk.isnot(None),
            Ticket.sla_breach_risk >= 0.7
        ).count()
        ratio = (at_risk / total) if total else 0
        if ratio >= 0.2 and total >= 5:
            alerts.append({
                "city_id": city.id,
                "city_name": city.name,
                "at_risk": at_risk,
                "total": total,
                "ratio": round(ratio * 100, 2)
            })

    return alerts


@router.post("/demand-forecast")
async def state_demand_forecast(
    payload: dict = Body(...),
    current_user: User = Depends(require_role([UserRole.STATE_ADMIN])),
    db: Session = Depends(get_db)
):
    """Demand forecasting by part for the state"""
    if not current_user.state_id:
        raise HTTPException(status_code=400, detail="User must be assigned to a state")
    part_id = payload.get("part_id")
    forecast_days = int(payload.get("forecast_days", 30))
    if not part_id:
        raise HTTPException(status_code=400, detail="part_id is required")
    return await forecast_service.forecast_demand(
        part_id=part_id,
        state_id=current_user.state_id,
        organization_id=current_user.organization_id,
        forecast_days=forecast_days
    )


@router.post("/policy-impact")
async def simulate_policy_impact(
    payload: dict = Body(...),
    current_user: User = Depends(require_role([UserRole.STATE_ADMIN])),
    db: Session = Depends(get_db)
):
    """Simulate SLA policy impact by changing target hours"""
    if not current_user.state_id:
        raise HTTPException(status_code=400, detail="User must be assigned to a state")
    target_hours = float(payload.get("target_hours", 24))

    cities = db.query(City).filter(City.state_id == current_user.state_id).all()
    city_ids = [c.id for c in cities]
    tickets = db.query(Ticket).filter(Ticket.city_id.in_(city_ids)).all()

    if not tickets:
        return {"predicted_breach_rate": 0, "current_breach_rate": 0}

    def is_breach(t: Ticket, hours: float) -> bool:
        end_time = t.resolved_at or datetime.now(timezone.utc)
        if not t.created_at:
            return False
        elapsed = (end_time - t.created_at).total_seconds() / 3600
        return elapsed > hours

    current_breaches = len([t for t in tickets if t.sla_deadline and t.resolved_at and t.resolved_at > t.sla_deadline])
    current_breach_rate = (current_breaches / len(tickets)) * 100
    predicted_breaches = len([t for t in tickets if is_breach(t, target_hours)])
    predicted_breach_rate = (predicted_breaches / len(tickets)) * 100

    return {
        "current_breach_rate": round(current_breach_rate, 2),
        "predicted_breach_rate": round(predicted_breach_rate, 2),
        "target_hours": target_hours
    }


@router.get("/training-gaps")
async def get_training_gaps(
    current_user: User = Depends(require_role([UserRole.STATE_ADMIN])),
    db: Session = Depends(get_db)
):
    """Detect training gaps based on repeat visits"""
    if not current_user.state_id:
        raise HTTPException(status_code=400, detail="User must be assigned to a state")
    cities = db.query(City).filter(City.state_id == current_user.state_id).all()
    city_ids = [c.id for c in cities]

    followups = db.query(Ticket).filter(
        Ticket.city_id.in_(city_ids),
        Ticket.parent_ticket_id.isnot(None),
        Ticket.assigned_engineer_id.isnot(None)
    ).all()

    stats = {}
    for t in followups:
        engineer = db.query(User).filter(User.id == t.assigned_engineer_id).first()
        if not engineer:
            continue
        key = engineer.engineer_skill_level or "unknown"
        stats.setdefault(key, {"skill_level": key, "repeat_visits": 0, "engineers": set()})
        stats[key]["repeat_visits"] += 1
        stats[key]["engineers"].add(engineer.id)

    return [
        {
            "skill_level": s["skill_level"],
            "repeat_visits": s["repeat_visits"],
            "engineers": len(s["engineers"])
        }
        for s in stats.values()
    ]


@router.get("/demand-forecast")
async def get_state_demand_forecast(
    days: int = 30,
    current_user: User = Depends(require_role([UserRole.STATE_ADMIN])),
    db: Session = Depends(get_db)
):
    """Forecast top parts demand for the state"""
    if not current_user.state_id:
        raise HTTPException(status_code=400, detail="User must be assigned to a state")

    since = datetime.now(timezone.utc) - timedelta(days=90)
    transactions = db.query(InventoryTransaction).join(Inventory).filter(
        Inventory.state_id == current_user.state_id,
        InventoryTransaction.transaction_type == "out",
        InventoryTransaction.created_at >= since
    ).all()

    usage = {}
    for tx in transactions:
        usage[tx.part_id] = usage.get(tx.part_id, 0) + tx.quantity

    top_parts = sorted(usage.items(), key=lambda x: x[1], reverse=True)[:5]
    forecasts = []
    for part_id, qty in top_parts:
        part = db.query(Part).filter(Part.id == part_id).first()
        avg_per_day = qty / 90 if qty else 0
        avg_per_week = avg_per_day * 7
        forecast_qty = round(avg_per_day * days, 2)
        forecasts.append({
            "part_id": part_id,
            "part_name": part.name if part else f"Part {part_id}",
            "forecast_days": days,
            "predicted_demand": forecast_qty,
            "weekly_forecast": [round(avg_per_week, 2)] * 4
        })

    return forecasts


@router.post("/policy-impact")
async def simulate_policy_impact(
    payload: dict = Body(...),
    current_user: User = Depends(require_role([UserRole.STATE_ADMIN])),
    db: Session = Depends(get_db)
):
    """Simulate SLA policy impact on compliance"""
    if not current_user.state_id:
        raise HTTPException(status_code=400, detail="User must be assigned to a state")

    target_hours = float(payload.get("target_hours", 24))
    tickets = db.query(Ticket).filter(
        Ticket.state_id == current_user.state_id,
        Ticket.resolved_at.isnot(None),
        Ticket.created_at.isnot(None)
    ).all()

    compliant = 0
    for t in tickets:
        hours = (t.resolved_at - t.created_at).total_seconds() / 3600
        if hours <= target_hours:
            compliant += 1

    total = len(tickets)
    compliance_rate = round((compliant / total) * 100, 2) if total else 0
    projected_breaches = max(total - compliant, 0)
    estimated_penalty = projected_breaches * 200

    return {
        "target_hours": target_hours,
        "total_tickets": total,
        "compliance_rate": compliance_rate,
        "projected_breaches": projected_breaches,
        "estimated_penalty": estimated_penalty
    }


@router.get("/training-gaps")
async def get_training_gaps(
    current_user: User = Depends(require_role([UserRole.STATE_ADMIN])),
    db: Session = Depends(get_db)
):
    """Identify engineers with high repeat visits or low ratings"""
    if not current_user.state_id:
        raise HTTPException(status_code=400, detail="User must be assigned to a state")

    engineers = db.query(User).filter(
        User.state_id == current_user.state_id,
        User.role == UserRole.SUPPORT_ENGINEER
    ).all()

    results = []
    for engineer in engineers:
        tickets = db.query(Ticket).filter(Ticket.assigned_engineer_id == engineer.id).all()
        total = len(tickets)
        follow_ups = len([t for t in tickets if t.parent_ticket_id])
        avg_rating = None
        ratings = [t.customer_rating for t in tickets if t.customer_rating]
        if ratings:
            avg_rating = round(sum(ratings) / len(ratings), 2)
        follow_up_rate = (follow_ups / total) if total else 0

        if follow_up_rate >= 0.2 or (avg_rating is not None and avg_rating < 3.5):
            results.append({
                "engineer_id": engineer.id,
                "engineer_name": engineer.full_name,
                "skill_level": engineer.engineer_skill_level,
                "follow_up_rate": round(follow_up_rate * 100, 2),
                "avg_rating": avg_rating,
                "total_tickets": total
            })

    return results


@router.get("/sla-policies")
async def list_state_sla_policies(
    current_user: User = Depends(require_role([UserRole.STATE_ADMIN])),
    db: Session = Depends(get_db)
):
    """List SLA policies scoped to this state"""
    if not current_user.organization_id or not current_user.state_id:
        raise HTTPException(status_code=400, detail="User must be associated with an organization and state")

    policies = db.query(SLAPolicy).filter(
        SLAPolicy.organization_id == current_user.organization_id,
        SLAPolicy.state_id == current_user.state_id
    ).all()

    return [
        {
            "id": p.id,
            "sla_type": p.sla_type.value,
            "target_hours": p.target_hours,
            "product_category": p.product_category,
            "product_id": p.product_id,
            "city_id": p.city_id,
            "priority_overrides": p.priority_overrides,
            "business_hours_only": p.business_hours_only,
            "is_active": p.is_active
        }
        for p in policies
    ]


@router.post("/sla-policies")
async def create_state_sla_policy(
    policy_data: dict = Body(...),
    current_user: User = Depends(require_role([UserRole.STATE_ADMIN])),
    db: Session = Depends(get_db)
):
    """Create SLA policy scoped to this state"""
    if not current_user.organization_id or not current_user.state_id:
        raise HTTPException(status_code=400, detail="User must be associated with an organization and state")

    sla_type = policy_data.get("sla_type")
    target_hours = policy_data.get("target_hours")
    if not sla_type or not target_hours:
        raise HTTPException(status_code=400, detail="Missing required fields: sla_type, target_hours")

    city_id = policy_data.get("city_id")
    if city_id:
        city = db.query(City).filter(City.id == city_id, City.state_id == current_user.state_id).first()
        if not city:
            raise HTTPException(status_code=404, detail="City not found in your state")

    policy = SLAPolicy(
        organization_id=current_user.organization_id,
        sla_type=SLAType(sla_type),
        target_hours=target_hours,
        product_category=policy_data.get("product_category"),
        product_id=policy_data.get("product_id"),
        state_id=current_user.state_id,
        city_id=city_id,
        priority_overrides=policy_data.get("priority_overrides", {}),
        business_hours_only=policy_data.get("business_hours_only", False),
        business_hours=policy_data.get("business_hours", {}),
        is_active=policy_data.get("is_active", True)
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return {"id": policy.id, "message": "SLA policy created"}


@router.put("/sla-policies/{policy_id}")
async def update_state_sla_policy(
    policy_id: int,
    policy_data: dict = Body(...),
    current_user: User = Depends(require_role([UserRole.STATE_ADMIN])),
    db: Session = Depends(get_db)
):
    """Update SLA policy scoped to this state"""
    policy = db.query(SLAPolicy).filter(
        SLAPolicy.id == policy_id,
        SLAPolicy.organization_id == current_user.organization_id,
        SLAPolicy.state_id == current_user.state_id
    ).first()
    if not policy:
        raise HTTPException(status_code=404, detail="SLA policy not found")

    if "sla_type" in policy_data:
        policy.sla_type = SLAType(policy_data["sla_type"])
    if "target_hours" in policy_data:
        policy.target_hours = policy_data["target_hours"]
    if "product_category" in policy_data:
        policy.product_category = policy_data["product_category"]
    if "product_id" in policy_data:
        policy.product_id = policy_data["product_id"]
    if "city_id" in policy_data:
        city = db.query(City).filter(City.id == policy_data["city_id"], City.state_id == current_user.state_id).first()
        if not city:
            raise HTTPException(status_code=404, detail="City not found in your state")
        policy.city_id = policy_data["city_id"]
    if "priority_overrides" in policy_data:
        policy.priority_overrides = policy_data["priority_overrides"]
    if "business_hours_only" in policy_data:
        policy.business_hours_only = policy_data["business_hours_only"]
    if "business_hours" in policy_data:
        policy.business_hours = policy_data["business_hours"]
    if "is_active" in policy_data:
        policy.is_active = policy_data["is_active"]

    db.commit()
    return {"message": "SLA policy updated"}


@router.delete("/sla-policies/{policy_id}")
async def delete_state_sla_policy(
    policy_id: int,
    current_user: User = Depends(require_role([UserRole.STATE_ADMIN])),
    db: Session = Depends(get_db)
):
    """Delete SLA policy scoped to this state"""
    policy = db.query(SLAPolicy).filter(
        SLAPolicy.id == policy_id,
        SLAPolicy.organization_id == current_user.organization_id,
        SLAPolicy.state_id == current_user.state_id
    ).first()
    if not policy:
        raise HTTPException(status_code=404, detail="SLA policy not found")
    db.delete(policy)
    db.commit()
    return {"message": "SLA policy deleted"}


@router.get("/service-policies")
async def list_state_service_policies(
    current_user: User = Depends(require_role([UserRole.STATE_ADMIN])),
    db: Session = Depends(get_db)
):
    """List service policies scoped to this state"""
    if not current_user.organization_id or not current_user.state_id:
        raise HTTPException(status_code=400, detail="User must be associated with an organization and state")

    policies = db.query(ServicePolicy).filter(
        ServicePolicy.organization_id == current_user.organization_id,
        ServicePolicy.state_id == current_user.state_id
    ).all()

    return [
        {
            "id": p.id,
            "policy_type": p.policy_type,
            "rules": p.rules,
            "product_category": p.product_category,
            "product_id": p.product_id,
            "city_id": p.city_id,
            "is_active": p.is_active
        }
        for p in policies
    ]


@router.post("/service-policies")
async def create_state_service_policy(
    policy_data: dict = Body(...),
    current_user: User = Depends(require_role([UserRole.STATE_ADMIN])),
    db: Session = Depends(get_db)
):
    """Create service policy scoped to this state"""
    if not current_user.organization_id or not current_user.state_id:
        raise HTTPException(status_code=400, detail="User must be associated with an organization and state")

    city_id = policy_data.get("city_id")
    if city_id:
        city = db.query(City).filter(City.id == city_id, City.state_id == current_user.state_id).first()
        if not city:
            raise HTTPException(status_code=404, detail="City not found in your state")

    policy = ServicePolicy(
        organization_id=current_user.organization_id,
        policy_type=policy_data.get("policy_type"),
        rules=policy_data.get("rules", {}),
        product_category=policy_data.get("product_category"),
        product_id=policy_data.get("product_id"),
        state_id=current_user.state_id,
        city_id=city_id,
        is_active=policy_data.get("is_active", True)
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return {"id": policy.id, "message": "Service policy created"}


@router.put("/service-policies/{policy_id}")
async def update_state_service_policy(
    policy_id: int,
    policy_data: dict = Body(...),
    current_user: User = Depends(require_role([UserRole.STATE_ADMIN])),
    db: Session = Depends(get_db)
):
    """Update service policy scoped to this state"""
    policy = db.query(ServicePolicy).filter(
        ServicePolicy.id == policy_id,
        ServicePolicy.organization_id == current_user.organization_id,
        ServicePolicy.state_id == current_user.state_id
    ).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Service policy not found")

    if "policy_type" in policy_data:
        policy.policy_type = policy_data["policy_type"]
    if "rules" in policy_data:
        policy.rules = policy_data["rules"]
    if "product_category" in policy_data:
        policy.product_category = policy_data["product_category"]
    if "product_id" in policy_data:
        policy.product_id = policy_data["product_id"]
    if "city_id" in policy_data:
        city = db.query(City).filter(City.id == policy_data["city_id"], City.state_id == current_user.state_id).first()
        if not city:
            raise HTTPException(status_code=404, detail="City not found in your state")
        policy.city_id = policy_data["city_id"]
    if "is_active" in policy_data:
        policy.is_active = policy_data["is_active"]

    db.commit()
    return {"message": "Service policy updated"}


@router.delete("/service-policies/{policy_id}")
async def delete_state_service_policy(
    policy_id: int,
    current_user: User = Depends(require_role([UserRole.STATE_ADMIN])),
    db: Session = Depends(get_db)
):
    """Delete service policy scoped to this state"""
    policy = db.query(ServicePolicy).filter(
        ServicePolicy.id == policy_id,
        ServicePolicy.organization_id == current_user.organization_id,
        ServicePolicy.state_id == current_user.state_id
    ).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Service policy not found")
    db.delete(policy)
    db.commit()
    return {"message": "Service policy deleted"}
