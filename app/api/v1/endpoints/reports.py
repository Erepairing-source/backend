"""
Report export endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime, timedelta
import io
import csv
import json

from app.core.database import get_db
from app.core.permissions import require_role, get_current_user
from app.models.user import User, UserRole
from app.models.ticket import Ticket, TicketStatus, TicketComment
from app.models.inventory import InventoryTransaction
from app.models.device import Device

router = APIRouter()


@router.get("/tickets/export")
async def export_tickets_report(
    format: str = Query("csv", pattern="^(csv|json)$"),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Export tickets report from database"""
    query = db.query(Ticket)
    
    # Role-based filtering from database
    if current_user.role == UserRole.CUSTOMER:
        query = query.filter(Ticket.customer_id == current_user.id)
    elif current_user.role == UserRole.SUPPORT_ENGINEER:
        query = query.filter(Ticket.assigned_engineer_id == current_user.id)
    elif current_user.role == UserRole.CITY_ADMIN:
        query = query.filter(Ticket.city_id == current_user.city_id)
    elif current_user.role == UserRole.STATE_ADMIN:
        from app.models.location import City
        cities = db.query(City).filter(City.state_id == current_user.state_id).all()
        city_ids = [city.id for city in cities]
        query = query.filter(Ticket.city_id.in_(city_ids))
    elif current_user.role == UserRole.ORGANIZATION_ADMIN:
        query = query.filter(Ticket.organization_id == current_user.organization_id)
    # Platform admin can see all
    
    # Date filtering
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            query = query.filter(Ticket.created_at >= start_dt)
        except:
            pass
    
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            query = query.filter(Ticket.created_at <= end_dt)
        except:
            pass
    
    # Status filtering
    if status:
        try:
            status_enum = TicketStatus(status)
            query = query.filter(Ticket.status == status_enum)
        except:
            pass
    
    tickets = query.order_by(Ticket.created_at.desc()).all()
    
    # Prepare data
    data = []
    for ticket in tickets:
        data.append({
            "ticket_number": ticket.ticket_number,
            "status": ticket.status.value,
            "priority": ticket.priority.value,
            "issue_category": ticket.issue_category,
            "issue_description": ticket.issue_description,
            "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
            "assigned_at": ticket.assigned_at.isoformat() if ticket.assigned_at else None,
            "resolved_at": ticket.resolved_at.isoformat() if ticket.resolved_at else None,
            "customer_id": ticket.customer_id,
            "assigned_engineer_id": ticket.assigned_engineer_id,
            "service_address": ticket.service_address
        })
    
    if format == "csv":
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=data[0].keys() if data else [])
        writer.writeheader()
        writer.writerows(data)
        
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode('utf-8')),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=tickets_report_{datetime.now().strftime('%Y%m%d')}.csv"}
        )
    else:
        return JSONResponse(content={"tickets": data, "count": len(data)})


@router.get("/inventory/export")
async def export_inventory_report(
    format: str = Query("csv", pattern="^(csv|json)$"),
    city_id: Optional[int] = None,
    low_stock_only: bool = False,
    current_user: User = Depends(require_role([
        UserRole.CITY_ADMIN,
        UserRole.STATE_ADMIN,
        UserRole.ORGANIZATION_ADMIN
    ])),
    db: Session = Depends(get_db)
):
    """Export inventory report from database"""
    from app.models.inventory import Inventory
    
    query = db.query(Inventory).filter(
        Inventory.organization_id == current_user.organization_id
    )
    
    if current_user.role == UserRole.CITY_ADMIN:
        query = query.filter(Inventory.city_id == current_user.city_id)
    elif current_user.role == UserRole.STATE_ADMIN:
        from app.models.location import City
        cities = db.query(City).filter(City.state_id == current_user.state_id).all()
        city_ids = [city.id for city in cities]
        query = query.filter(Inventory.city_id.in_(city_ids))
    
    if city_id:
        query = query.filter(Inventory.city_id == city_id)
    
    if low_stock_only:
        query = query.filter(Inventory.is_low_stock == True)
    
    inventory_items = query.all()
    
    # Prepare data
    data = []
    for inv in inventory_items:
        data.append({
            "part_name": inv.part.name,
            "sku": inv.part.sku,
            "city_id": inv.city_id,
            "current_stock": inv.current_stock,
            "min_threshold": inv.min_threshold,
            "max_threshold": inv.max_threshold,
            "is_low_stock": inv.is_low_stock,
            "reserved_stock": inv.reserved_stock
        })
    
    if format == "csv":
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=data[0].keys() if data else [])
        writer.writeheader()
        writer.writerows(data)
        
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode('utf-8')),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=inventory_report_{datetime.now().strftime('%Y%m%d')}.csv"}
        )
    else:
        return JSONResponse(content={"inventory": data, "count": len(data)})


@router.get("/audit-logs")
async def get_audit_logs(
    entity_type: Optional[str] = None,  # ticket, inventory, user, etc.
    entity_id: Optional[int] = None,
    user_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = Query(100, le=1000),
    current_user: User = Depends(require_role([
        UserRole.CITY_ADMIN,
        UserRole.STATE_ADMIN,
        UserRole.ORGANIZATION_ADMIN,
        UserRole.PLATFORM_ADMIN
    ])),
    db: Session = Depends(get_db)
):
    """Get audit logs from database (using TicketComment and InventoryTransaction as activity logs)"""
    logs = []
    
    # Get ticket comments as audit logs
    ticket_comments_query = db.query(TicketComment)
    
    # Apply filters
    if entity_type == "ticket" and entity_id:
        ticket_comments_query = ticket_comments_query.filter(TicketComment.ticket_id == entity_id)
    if user_id:
        ticket_comments_query = ticket_comments_query.filter(TicketComment.user_id == user_id)
    
    # Role-based filtering
    if current_user.role == UserRole.CITY_ADMIN:
        # Get tickets in the city
        city_tickets = db.query(Ticket.id).filter(Ticket.city_id == current_user.city_id).subquery()
        ticket_comments_query = ticket_comments_query.filter(TicketComment.ticket_id.in_(db.query(city_tickets.c.id)))
    elif current_user.role == UserRole.STATE_ADMIN:
        from app.models.location import City
        cities = db.query(City).filter(City.state_id == current_user.state_id).all()
        city_ids = [city.id for city in cities]
        state_tickets = db.query(Ticket.id).filter(Ticket.city_id.in_(city_ids)).subquery()
        ticket_comments_query = ticket_comments_query.filter(TicketComment.ticket_id.in_(db.query(state_tickets.c.id)))
    elif current_user.role == UserRole.ORGANIZATION_ADMIN:
        org_tickets = db.query(Ticket.id).filter(Ticket.organization_id == current_user.organization_id).subquery()
        ticket_comments_query = ticket_comments_query.filter(TicketComment.ticket_id.in_(db.query(org_tickets.c.id)))
    
    # Date filtering
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            ticket_comments_query = ticket_comments_query.filter(TicketComment.created_at >= start_dt)
        except:
            pass
    
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            ticket_comments_query = ticket_comments_query.filter(TicketComment.created_at <= end_dt)
        except:
            pass
    
    ticket_comments = ticket_comments_query.order_by(TicketComment.created_at.desc()).limit(limit).all()
    
    for comment in ticket_comments:
        logs.append({
            "id": comment.id,
            "entity_type": "ticket",
            "entity_id": comment.ticket_id,
            "action": comment.comment_type or "comment",
            "description": comment.comment_text,
            "user_id": comment.user_id,
            "user_name": comment.user.full_name if comment.user else "System",
            "created_at": comment.created_at.isoformat() if comment.created_at else None,
            "extra_data": comment.extra_data or {}
        })
    
    # Get inventory transactions as audit logs
    inventory_transactions_query = db.query(InventoryTransaction)
    
    # Role-based filtering
    if current_user.role == UserRole.CITY_ADMIN:
        city_inventory = db.query(Inventory.id).filter(Inventory.city_id == current_user.city_id).subquery()
        inventory_transactions_query = inventory_transactions_query.filter(InventoryTransaction.inventory_id.in_(db.query(city_inventory.c.id)))
    elif current_user.role == UserRole.STATE_ADMIN:
        from app.models.location import City
        cities = db.query(City).filter(City.state_id == current_user.state_id).all()
        city_ids = [city.id for city in cities]
        state_inventory = db.query(Inventory.id).filter(Inventory.city_id.in_(city_ids)).subquery()
        inventory_transactions_query = inventory_transactions_query.filter(InventoryTransaction.inventory_id.in_(db.query(state_inventory.c.id)))
    elif current_user.role == UserRole.ORGANIZATION_ADMIN:
        org_inventory = db.query(Inventory.id).filter(Inventory.organization_id == current_user.organization_id).subquery()
        inventory_transactions_query = inventory_transactions_query.filter(InventoryTransaction.inventory_id.in_(db.query(org_inventory.c.id)))
    
    if user_id:
        inventory_transactions_query = inventory_transactions_query.filter(InventoryTransaction.performed_by_id == user_id)
    
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            inventory_transactions_query = inventory_transactions_query.filter(InventoryTransaction.created_at >= start_dt)
        except:
            pass
    
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            inventory_transactions_query = inventory_transactions_query.filter(InventoryTransaction.created_at <= end_dt)
        except:
            pass
    
    inventory_transactions = inventory_transactions_query.order_by(InventoryTransaction.created_at.desc()).limit(limit).all()
    
    for transaction in inventory_transactions:
        logs.append({
            "id": transaction.id,
            "entity_type": "inventory",
            "entity_id": transaction.inventory_id,
            "action": transaction.transaction_type,
            "description": f"{transaction.transaction_type}: {transaction.quantity} units of {transaction.part.name if transaction.part else 'part'}. {transaction.notes or ''}",
            "user_id": transaction.performed_by_id,
            "user_name": transaction.performed_by.full_name if transaction.performed_by else "System",
            "created_at": transaction.created_at.isoformat() if transaction.created_at else None,
            "extra_data": {
                "part_id": transaction.part_id,
                "quantity": transaction.quantity,
                "previous_stock": transaction.previous_stock,
                "new_stock": transaction.new_stock
            }
        })
    
    # Sort by created_at descending
    logs.sort(key=lambda x: x["created_at"] or "", reverse=True)
    
    return {
        "logs": logs[:limit],
        "total": len(logs),
        "filters": {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "user_id": user_id,
            "start_date": start_date,
            "end_date": end_date
        }
    }


@router.get("/audit-logs/export")
async def export_audit_logs(
    format: str = Query("csv", pattern="^(csv|json)$"),
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: User = Depends(require_role([
        UserRole.CITY_ADMIN,
        UserRole.STATE_ADMIN,
        UserRole.ORGANIZATION_ADMIN,
        UserRole.PLATFORM_ADMIN
    ])),
    db: Session = Depends(get_db)
):
    """Export audit logs from database"""
    # Get logs using the same logic as get_audit_logs
    logs_response = await get_audit_logs(
        entity_type=entity_type,
        entity_id=entity_id,
        start_date=start_date,
        end_date=end_date,
        limit=10000,
        current_user=current_user,
        db=db
    )
    
    logs = logs_response["logs"]
    
    if format == "csv":
        output = io.StringIO()
        if logs:
            writer = csv.DictWriter(output, fieldnames=logs[0].keys())
            writer.writeheader()
            writer.writerows(logs)
        
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode('utf-8')),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=audit_logs_{datetime.now().strftime('%Y%m%d')}.csv"}
        )
    else:
        return JSONResponse(content={"logs": logs, "count": len(logs)})
