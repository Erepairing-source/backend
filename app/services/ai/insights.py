"""
AI Insights (heuristics-based)
Provides ticket summaries, checklists, and SLA risk explanations.
"""
from typing import Dict, List, Any
from datetime import datetime, timezone, timedelta

from app.models.ticket import Ticket


def build_ticket_summary(ticket: Ticket) -> Dict[str, Any]:
    highlights: List[str] = []
    if ticket.sla_breach_risk is not None and ticket.sla_breach_risk >= 0.7:
        highlights.append("High SLA breach risk")
    if ticket.warranty_status == "in_warranty":
        highlights.append("Covered by warranty")
    if ticket.parent_ticket_id:
        highlights.append("Follow-up ticket")
    if ticket.engineer_eta_start and ticket.engineer_eta_end:
        highlights.append("ETA shared by engineer")

    summary = (
        f"Ticket {ticket.ticket_number} is {ticket.status.value} with priority {ticket.priority.value}. "
        f"Issue: {ticket.issue_category or 'general'}."
    )
    if ticket.issue_description:
        summary += f" {ticket.issue_description[:160]}"

    return {
        "summary": summary.strip(),
        "highlights": highlights,
        "status": ticket.status.value,
        "priority": ticket.priority.value,
        "sla_breach_risk": ticket.sla_breach_risk
    }


def build_checklist(ticket: Ticket) -> Dict[str, Any]:
    issue_text = (ticket.issue_description or "").lower()
    category = (ticket.issue_category or "").lower()
    device_model = ticket.device.model_number if ticket.device else None

    steps = [
        "Confirm device model and warranty status",
        "Verify reported symptoms with customer",
        "Inspect power source and connectors",
        "Run basic diagnostics",
        "Capture photos before and after repair"
    ]

    if "no power" in issue_text or "power" in category:
        steps = [
            "Check power cable and outlet",
            "Inspect fuse/adapter for damage",
            "Test power button response",
            "Check internal power module",
            "Replace faulty power component"
        ]
    elif "screen" in issue_text or "display" in category:
        steps = [
            "Inspect screen for physical damage",
            "Check display cable connections",
            "Run display diagnostic test",
            "Replace display module if needed",
            "Verify brightness and touch response"
        ]
    elif "noise" in issue_text:
        steps = [
            "Identify noise source",
            "Check for loose parts",
            "Inspect fan/motor bearings",
            "Tighten or replace faulty part",
            "Run noise test after fix"
        ]
    elif "leak" in issue_text:
        steps = [
            "Locate leak source",
            "Inspect seals and hoses",
            "Check drainage path",
            "Replace damaged components",
            "Run leak test after repair"
        ]
    elif "cooling" in category or "cool" in issue_text:
        steps = [
            "Check thermostat settings",
            "Inspect airflow and filters",
            "Check refrigerant pressure",
            "Inspect compressor operation",
            "Confirm cooling performance"
        ]

    return {
        "issue_category": ticket.issue_category,
        "device_model": device_model,
        "steps": steps
    }


def build_parts_suggestions(ticket: Ticket) -> Dict[str, Any]:
    suggestions: List[Any] = []
    if ticket.ai_suggested_parts:
        for idx, part in enumerate(ticket.ai_suggested_parts):
            confidence = 0.7 - (idx * 0.1)
            suggestion = part if isinstance(part, dict) else {"part_id": part}
            suggestion["confidence"] = round(max(confidence, 0.3), 2)
            suggestions.append(suggestion)

        for idx, suggestion in enumerate(suggestions):
            suggestion["alternatives"] = [
                alt for alt in suggestions if alt is not suggestion
            ][:2]

    return {
        "suggestions": suggestions,
        "note": "Suggestions based on triage history" if suggestions else "No suggestions available yet"
    }


def compute_sla_risk(ticket: Ticket) -> float:
    if ticket.sla_deadline:
        now = datetime.now(timezone.utc)
        # Ensure sla_deadline is timezone-aware
        deadline = ticket.sla_deadline
        if deadline.tzinfo is None:
            # If naive, assume UTC
            deadline = deadline.replace(tzinfo=timezone.utc)
        else:
            # If aware, convert to UTC
            deadline = deadline.astimezone(timezone.utc)
        remaining_hours = (deadline - now).total_seconds() / 3600
    else:
        remaining_hours = None

    risk = 0.1
    if ticket.priority.value in ["high", "urgent"]:
        risk += 0.2
    if ticket.status.value in ["created", "assigned"]:
        risk += 0.2
    if remaining_hours is not None:
        if remaining_hours <= 4:
            risk += 0.4
        elif remaining_hours <= 24:
            risk += 0.2
    return round(min(risk, 0.99), 2)


def build_sla_risk_explanation(ticket: Ticket) -> Dict[str, Any]:
    reasons = []
    now = datetime.now(timezone.utc)
    if ticket.sla_deadline:
        # Ensure sla_deadline is timezone-aware
        deadline = ticket.sla_deadline
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        else:
            deadline = deadline.astimezone(timezone.utc)
        remaining = (deadline - now).total_seconds() / 3600
        if remaining < 4:
            reasons.append("SLA deadline is within 4 hours")
        elif remaining < 24:
            reasons.append("SLA deadline is within 24 hours")
    if ticket.priority.value in ["high", "urgent"]:
        reasons.append("High/urgent priority")
    if ticket.status.value in ["created", "assigned"]:
        reasons.append("Ticket not started yet")

    return {
        "sla_breach_risk": ticket.sla_breach_risk if ticket.sla_breach_risk is not None else compute_sla_risk(ticket),
        "reasons": reasons
    }


def predict_satisfaction_risk(ticket: Ticket) -> Dict[str, Any]:
    reasons = []
    risk = 0.1
    text = (ticket.issue_description or "").lower()

    if ticket.customer_rating is not None and ticket.customer_rating <= 2:
        risk += 0.6
        reasons.append("Low customer rating")
    if ticket.sentiment_score is not None and ticket.sentiment_score < -0.2:
        risk += 0.4
        reasons.append("Negative sentiment detected")
    if ticket.customer_dispute_tags:
        risk += 0.3
        reasons.append("Customer dispute tags present")
    if any(word in text for word in ["delay", "late", "not resolved", "angry", "complaint"]):
        risk += 0.2
        reasons.append("Risky keywords in description")
    if ticket.parent_ticket_id:
        risk += 0.2
        reasons.append("Follow-up ticket")

    return {
        "risk_score": round(min(risk, 0.99), 2),
        "reasons": reasons
    }


def generate_auto_notes(ticket: Ticket) -> Dict[str, Any]:
    lines = []
    if ticket.device:
        lines.append(f"Device: {ticket.device.brand} {ticket.device.model_number} (SN: {ticket.device.serial_number})")
    lines.append(f"Issue: {ticket.issue_description}")
    if ticket.arrival_confirmed_at:
        lines.append(f"Arrival confirmed at {ticket.arrival_confirmed_at.isoformat()}")
    if ticket.parts_used:
        lines.append(f"Parts used: {ticket.parts_used}")
    if ticket.resolution_photos:
        lines.append(f"Resolution photos attached: {len(ticket.resolution_photos)}")
    if ticket.warranty_status:
        lines.append(f"Warranty: {ticket.warranty_status}")

    return {
        "notes": "\n".join(lines).strip()
    }
