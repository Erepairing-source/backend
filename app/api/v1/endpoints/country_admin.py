"""
Country Admin endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.core.permissions import require_role
from sqlalchemy import func
from datetime import datetime, timedelta, timezone

from app.models.user import User, UserRole
from app.models.ticket import Ticket, TicketStatus
from app.models.location import Country, State, City
from app.models.organization import Organization, OrganizationHierarchy
from app.models.device import Device

# Full list of Indian states (so Country Admin always shows all states for India)
INDIA_STATES_FULL = [
    {"name": "Andhra Pradesh"}, {"name": "Arunachal Pradesh"}, {"name": "Assam"}, {"name": "Bihar"},
    {"name": "Chhattisgarh"}, {"name": "Goa"}, {"name": "Gujarat"}, {"name": "Haryana"},
    {"name": "Himachal Pradesh"}, {"name": "Jharkhand"}, {"name": "Karnataka"}, {"name": "Kerala"},
    {"name": "Madhya Pradesh"}, {"name": "Maharashtra"}, {"name": "Manipur"}, {"name": "Meghalaya"},
    {"name": "Mizoram"}, {"name": "Nagaland"}, {"name": "Odisha"}, {"name": "Punjab"},
    {"name": "Rajasthan"}, {"name": "Sikkim"}, {"name": "Tamil Nadu"}, {"name": "Telangana"},
    {"name": "Tripura"}, {"name": "Uttar Pradesh"}, {"name": "Uttarakhand"}, {"name": "West Bengal"},
    {"name": "Andaman and Nicobar Islands"}, {"name": "Chandigarh"},
    {"name": "Dadra and Nagar Haveli and Daman and Diu"}, {"name": "Delhi"},
    {"name": "Jammu and Kashmir"}, {"name": "Ladakh"}, {"name": "Lakshadweep"}, {"name": "Puducherry"},
]
from app.models.inventory import Inventory
from typing import List


def _get_org_ids(current_user: User, db: Session) -> List[int]:
    """Organization IDs visible to this country admin (OEM + linked service partners)."""
    if not current_user.organization_id:
        return []
    org = db.query(Organization).filter(Organization.id == current_user.organization_id).first()
    if not org:
        return []
    org_ids = [current_user.organization_id]
    if org.org_type.value == "oem":
        links = db.query(OrganizationHierarchy).filter(
            OrganizationHierarchy.oem_organization_id == current_user.organization_id
        ).all()
        org_ids.extend([link.service_partner_id for link in links])
    return org_ids


router = APIRouter()


@router.get("/dashboard")
async def get_country_dashboard(
    time_range: str = "30d",
    current_user: User = Depends(require_role([UserRole.COUNTRY_ADMIN])),
    db: Session = Depends(get_db)
):
    """Get country-wide dashboard statistics"""
    if not current_user.country_id:
        raise HTTPException(status_code=400, detail="User must be assigned to a country")
    
    # Get all states in the country
    states = db.query(State).filter(State.country_id == current_user.country_id).all()
    state_ids = [state.id for state in states]
    
    # Get all cities in those states
    cities = db.query(City).filter(City.state_id.in_(state_ids)).all()
    city_ids = [city.id for city in cities]
    
    # Scope tickets to this org (OEM + linked partners) when assigned
    org_ids = _get_org_ids(current_user, db)
    ticket_city_filter = Ticket.city_id.in_(city_ids)
    ticket_org_filter = Ticket.organization_id.in_(org_ids) if org_ids else True
    
    def _tickets_q(*extra_filters):
        q = db.query(Ticket).filter(ticket_city_filter)
        if org_ids:
            q = q.filter(ticket_org_filter)
        for f in extra_filters:
            q = q.filter(f)
        return q
    
    # Calculate statistics
    total_tickets = _tickets_q().count()
    resolved_tickets = _tickets_q(Ticket.status == TicketStatus.RESOLVED).count()
    national_sla_compliance = (resolved_tickets / total_tickets * 100) if total_tickets > 0 else 0
    
    # Calculate MTTR (Mean Time To Resolution) from actual ticket data
    resolved_tickets_with_times = _tickets_q(
        Ticket.status == TicketStatus.RESOLVED,
        Ticket.created_at.isnot(None),
        Ticket.resolved_at.isnot(None)
    ).all()
    
    if resolved_tickets_with_times:
        total_resolution_time = sum(
            (t.resolved_at - t.created_at).total_seconds() / 3600  # Convert to hours
            for t in resolved_tickets_with_times
        )
        national_mttr = max(total_resolution_time / len(resolved_tickets_with_times), 0.0)
    else:
        national_mttr = 0.0
    
    # Calculate First Time Fix Rate (FTFR) - tickets resolved without reassignment
    first_time_fixes = _tickets_q(
        Ticket.status == TicketStatus.RESOLVED,
        Ticket.assigned_engineer_id.isnot(None)
    ).count()
    national_ftfr = (first_time_fixes / resolved_tickets * 100) if resolved_tickets > 0 else 0.0
    
    # Calculate average customer satisfaction (NPS) from ticket ratings
    avg_rating_q = _tickets_q(Ticket.customer_rating.isnot(None))
    tickets_with_ratings = avg_rating_q.with_entities(func.avg(Ticket.customer_rating)).scalar() or 0.0
    customer_satisfaction = float(tickets_with_ratings) if tickets_with_ratings else 0.0
    
    # Calculate warranty cost (simplified - would need actual cost tracking)
    warranty_tickets = _tickets_q(Ticket.warranty_status == "in_warranty").count()
    warranty_cost = 0  # Would need actual cost calculation from parts/inventory

    # For India, show full state count in StatCard (matches states table)
    country = db.query(Country).filter(Country.id == current_user.country_id).first()
    is_india = False
    if country:
        code = (country.code or "").strip().upper()
        name = (country.name or "").strip().lower()
        is_india = code in ("IN", "IND") or name == "india" or "india" in name
    total_states_display = len(INDIA_STATES_FULL) if is_india else len(states)
    
    return {
        "totalStates": total_states_display,
        "totalTickets": total_tickets,
        "nationalSlaCompliance": round(national_sla_compliance, 2),
        "nationalMttr": round(national_mttr, 2),
        "nationalFtfr": round(national_ftfr, 2),
        "customerSatisfaction": round(customer_satisfaction, 2),
        "warrantyCost": warranty_cost
    }


def _state_metrics_row(state, city_ids, org_ids, db: Session):
    """Build one state row with SLA/MTTR/FTFR/NPS from DB tickets."""
    state_tickets_q = db.query(Ticket).filter(Ticket.city_id.in_(city_ids))
    if org_ids:
        state_tickets_q = state_tickets_q.filter(Ticket.organization_id.in_(org_ids))
    state_tickets = state_tickets_q.all()
    resolved = [t for t in state_tickets if t.status == TicketStatus.RESOLVED]
    sla_compliance = (len(resolved) / len(state_tickets) * 100) if state_tickets else 0

    def _hours_between(created, resolved_dt):
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if resolved_dt.tzinfo is None:
            resolved_dt = resolved_dt.replace(tzinfo=timezone.utc)
        return (resolved_dt - created).total_seconds() / 3600
    resolved_with_times = [t for t in resolved if t.created_at and t.resolved_at]
    if resolved_with_times:
        total_time = sum(_hours_between(t.created_at, t.resolved_at) for t in resolved_with_times)
        mttr = max(total_time / len(resolved_with_times), 0.0)
    else:
        mttr = 0.0
    first_time_fixes = len([t for t in resolved if t.assigned_engineer_id])
    ftfr = (first_time_fixes / len(resolved) * 100) if resolved else 0.0
    ratings = [t.customer_rating for t in state_tickets if t.customer_rating]
    nps = sum(ratings) / len(ratings) if ratings else 0.0
    if sla_compliance >= 90:
        status = "healthy"
    elif sla_compliance >= 70:
        status = "warning"
    else:
        status = "critical"
    return {
        "id": state.id,
        "name": state.name,
        "slaCompliance": round(sla_compliance, 2),
        "mttr": round(mttr, 2),
        "ftfr": round(ftfr, 2),
        "nps": round(nps, 2),
        "status": status
    }


@router.get("/states")
async def get_country_states(
    current_user: User = Depends(require_role([UserRole.COUNTRY_ADMIN])),
    db: Session = Depends(get_db)
):
    """Get all states with performance metrics. For India, returns all Indian states (zeros if not in DB)."""
    if not current_user.country_id:
        raise HTTPException(status_code=400, detail="User must be assigned to a country")

    country = db.query(Country).filter(Country.id == current_user.country_id).first()
    # Treat as India if code is IN/IND or name contains "india" (robust to DB variations)
    is_india = False
    if country:
        code = (country.code or "").strip().upper()
        name = (country.name or "").strip().lower()
        is_india = code in ("IN", "IND") or name == "india" or "india" in name
    org_ids = _get_org_ids(current_user, db)
    db_states = db.query(State).filter(State.country_id == current_user.country_id).all()
    db_state_by_name = {s.name.strip().lower(): s for s in db_states}

    result = []
    if is_india:
        # Return all Indian states so the table is complete; use DB metrics where state exists
        for s in INDIA_STATES_FULL:
            name = (s.get("name") or "").strip()
            if not name:
                continue
            name_lower = name.lower()
            if name_lower in db_state_by_name:
                state = db_state_by_name[name_lower]
                cities = db.query(City).filter(City.state_id == state.id).all()
                city_ids = [c.id for c in cities]
                result.append(_state_metrics_row(state, city_ids, org_ids, db))
            else:
                result.append({
                    "id": None,
                    "name": name,
                    "slaCompliance": 0,
                    "mttr": 0,
                    "ftfr": 0,
                    "nps": 0,
                    "status": "critical"
                })
        return result

    # Non-India: only states present in DB
    for state in db_states:
        cities = db.query(City).filter(City.state_id == state.id).all()
        city_ids = [city.id for city in cities]
        result.append(_state_metrics_row(state, city_ids, org_ids, db))
    return result


@router.get("/warranty-abuse")
async def get_warranty_abuse_signals(
    current_user: User = Depends(require_role([UserRole.COUNTRY_ADMIN])),
    db: Session = Depends(get_db)
):
    """Identify states with unusually high warranty usage"""
    if not current_user.country_id:
        raise HTTPException(status_code=400, detail="User must be assigned to a country")
    
    states = db.query(State).filter(State.country_id == current_user.country_id).all()
    alerts = []
    for state in states:
        cities = db.query(City).filter(City.state_id == state.id).all()
        city_ids = [city.id for city in cities]
        total = db.query(Ticket).filter(Ticket.city_id.in_(city_ids)).count()
        warranty = db.query(Ticket).filter(
            Ticket.city_id.in_(city_ids),
            Ticket.warranty_status == "in_warranty"
        ).count()
        ratio = (warranty / total) if total else 0
        if ratio >= 0.6 and total >= 10:
            alerts.append({
                "state_id": state.id,
                "state_name": state.name,
                "warranty_tickets": warranty,
                "total_tickets": total,
                "ratio": round(ratio * 100, 2)
            })

    return alerts


@router.get("/warranty-abuse/products")
async def get_warranty_abuse_by_product(
    current_user: User = Depends(require_role([UserRole.COUNTRY_ADMIN])),
    db: Session = Depends(get_db)
):
    """Warranty abuse signals by product model"""
    if not current_user.country_id:
        raise HTTPException(status_code=400, detail="User must be assigned to a country")

    states = db.query(State).filter(State.country_id == current_user.country_id).all()
    city_ids = [c.id for s in states for c in db.query(City).filter(City.state_id == s.id).all()]
    tickets = db.query(Ticket).filter(Ticket.city_id.in_(city_ids)).all()

    model_stats = {}
    for t in tickets:
        if not t.device_id:
            continue
        device = db.query(Device).filter(Device.id == t.device_id).first()
        if not device:
            continue
        key = device.model_number or "unknown"
        stats = model_stats.setdefault(key, {"total": 0, "warranty": 0})
        stats["total"] += 1
        if t.warranty_status == "in_warranty":
            stats["warranty"] += 1

    results = []
    for model, stats in model_stats.items():
        ratio = (stats["warranty"] / stats["total"]) if stats["total"] else 0
        if ratio >= 0.6 and stats["total"] >= 5:
            results.append({
                "model_number": model,
                "warranty_tickets": stats["warranty"],
                "total_tickets": stats["total"],
                "ratio": round(ratio * 100, 2)
            })

    return results


@router.get("/oem-defects")
async def get_oem_defect_trends(
    current_user: User = Depends(require_role([UserRole.COUNTRY_ADMIN])),
    db: Session = Depends(get_db)
):
    """Detect model-level defect spikes in last 30 days"""
    if not current_user.country_id:
        raise HTTPException(status_code=400, detail="User must be assigned to a country")

    now = datetime.now(timezone.utc)
    recent_since = now - timedelta(days=30)
    prev_since = now - timedelta(days=60)

    states = db.query(State).filter(State.country_id == current_user.country_id).all()
    city_ids = [c.id for s in states for c in db.query(City).filter(City.state_id == s.id).all()]

    recent = db.query(Ticket).filter(Ticket.city_id.in_(city_ids), Ticket.created_at >= recent_since).all()
    prev = db.query(Ticket).filter(Ticket.city_id.in_(city_ids), Ticket.created_at < recent_since, Ticket.created_at >= prev_since).all()

    recent_counts = {}
    for t in recent:
        if not t.device_id:
            continue
        device = db.query(Device).filter(Device.id == t.device_id).first()
        if not device:
            continue
        key = device.model_number or "unknown"
        recent_counts[key] = recent_counts.get(key, 0) + 1

    prev_counts = {}
    for t in prev:
        if not t.device_id:
            continue
        device = db.query(Device).filter(Device.id == t.device_id).first()
        if not device:
            continue
        key = device.model_number or "unknown"
        prev_counts[key] = prev_counts.get(key, 0) + 1

    spikes = []
    for model, count in recent_counts.items():
        prev_count = prev_counts.get(model, 0)
        if count >= 5 and (prev_count == 0 or count >= prev_count * 1.5):
            spikes.append({
                "model_number": model,
                "recent_tickets": count,
                "previous_tickets": prev_count,
                "trend": "spike"
            })

    return spikes


@router.get("/partner-score")
async def get_partner_score_predictions(
    current_user: User = Depends(require_role([UserRole.COUNTRY_ADMIN])),
    db: Session = Depends(get_db)
):
    """Predict partner score based on SLA, NPS, MTTR"""
    if not current_user.organization_id:
        return []

    partners = db.query(Organization).filter(Organization.org_type == "service_company").all()
    results = []
    for partner in partners:
        tickets = db.query(Ticket).filter(Ticket.organization_id == partner.id).all()
        resolved = [t for t in tickets if t.status == TicketStatus.RESOLVED and t.created_at and t.resolved_at]
        sla = (len(resolved) / len(tickets) * 100) if tickets else 0
        mttr = 0.0
        if resolved:
            mttr = sum((t.resolved_at - t.created_at).total_seconds() / 3600 for t in resolved) / len(resolved)
        ratings = [t.customer_rating for t in tickets if t.customer_rating]
        nps = sum(ratings) / len(ratings) if ratings else 0

        score = max(0, min(100, round((sla * 0.5) + (max(0, 5 - mttr) * 8) + (nps * 10), 2)))
        results.append({
            "partner_id": partner.id,
            "partner_name": partner.name,
            "sla": round(sla, 2),
            "mttr": round(mttr, 2),
            "nps": round(nps, 2),
            "predicted_score": score
        })
    
    return results


@router.get("/partners")
async def get_partner_performance(
    current_user: User = Depends(require_role([UserRole.COUNTRY_ADMIN])),
    db: Session = Depends(get_db)
):
    """Get partner performance data (for OEM organizations)"""
    # Get user's organization
    if not current_user.organization_id:
        return []
    
    org = db.query(Organization).filter(Organization.id == current_user.organization_id).first()
    if not org or org.org_type.value != "oem":
        return []
    
    # Get only service partners linked to this OEM
    hierarchy_links = db.query(OrganizationHierarchy).filter(
        OrganizationHierarchy.oem_organization_id == current_user.organization_id
    ).all()
    linked_partner_ids = [link.service_partner_id for link in hierarchy_links]
    if not linked_partner_ids:
        return []
    partners = db.query(Organization).filter(
        Organization.id.in_(linked_partner_ids),
        Organization.org_type == "service_company"
    ).all()
    
    result = []
    for partner in partners:
        # Get tickets handled by this partner
        partner_tickets = db.query(Ticket).filter(
            Ticket.organization_id == partner.id
        ).all()
        
        resolved = [t for t in partner_tickets if t.status == TicketStatus.RESOLVED]
        sla_adherence = (len(resolved) / len(partner_tickets) * 100) if partner_tickets else 0
        
        # Calculate average NPS from ratings
        ratings = [t.customer_rating for t in partner_tickets if t.customer_rating]
        nps = sum(ratings) / len(ratings) if ratings else 0.0
        
        # Calculate cost per ticket (simplified - would need actual cost tracking)
        # For now, use a base calculation or return 0
        cost_per_ticket = 0.0  # Would need actual cost calculation from parts/inventory
        
        # Determine status
        if sla_adherence >= 90:
            status = "excellent"
        elif sla_adherence >= 70:
            status = "good"
        elif sla_adherence >= 50:
            status = "needs_improvement"
        else:
            status = "poor"
        
        predicted_score = round(
            (sla_adherence * 0.5) + (nps * 0.3) + (min(len(partner_tickets), 100) * 0.2),
            2
        )
        result.append({
            "id": partner.id,
            "name": partner.name,
            "ticketsHandled": len(partner_tickets),
            "slaAdherence": round(sla_adherence, 2),
            "costPerTicket": round(cost_per_ticket, 2),
            "nps": round(nps, 2),
            "status": status,
            "predictedScore": predicted_score
        })
    
    return result


@router.get("/oem-defect-trends")
async def get_oem_defect_trends(
    current_user: User = Depends(require_role([UserRole.COUNTRY_ADMIN])),
    db: Session = Depends(get_db)
):
    """Detect model-level defect spikes"""
    if not current_user.country_id:
        raise HTTPException(status_code=400, detail="User must be assigned to a country")

    states = db.query(State).filter(State.country_id == current_user.country_id).all()
    state_ids = [s.id for s in states]
    cities = db.query(City).filter(City.state_id.in_(state_ids)).all()
    city_ids = [c.id for c in cities]

    tickets = db.query(Ticket).filter(
        Ticket.city_id.in_(city_ids),
        Ticket.device_id.isnot(None),
        Ticket.created_at >= datetime.now(timezone.utc) - timedelta(days=90)
    ).all()

    trends = {}
    for t in tickets:
        if not t.device:
            continue
        key = (t.device.model_number, t.issue_category or "general")
        trends.setdefault(key, {"model": t.device.model_number, "issue_category": t.issue_category or "general", "count": 0})
        trends[key]["count"] += 1

    top = sorted(trends.values(), key=lambda x: x["count"], reverse=True)[:10]
    return top

