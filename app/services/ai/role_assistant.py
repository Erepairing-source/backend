"""
Role Assistant Service.
Provides role-specific guidance + role-scoped DB context and optional free LLM response.
"""
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
import json
from urllib import request as urlrequest
from urllib.error import URLError, HTTPError
from urllib.parse import quote
from sqlalchemy import func

from app.core.config import settings
from app.services.ai.chat_memory import get_or_create_session, add_message, get_recent_messages

from app.models.user import UserRole, User
from app.models.ticket import Ticket, TicketStatus
from app.models.organization import Organization
from app.models.subscription import Subscription, VendorOrganization, Vendor


ROLE_GUIDES: Dict[str, Dict[str, Any]] = {
    UserRole.CUSTOMER.value: {
        "role_name": "Customer",
        "overview": "You can create tickets, track service visits, and manage devices.",
        "access": [
            "Create and track tickets",
            "Reschedule visits",
            "View devices and warranty status",
            "See notifications and ETA updates"
        ],
        "ai_features": [
            "AI issue triage during ticket creation",
            "Ticket cost estimate preview",
            "Live engineer tracking"
        ],
        "sections": [
            {"title": "Create Ticket", "path": "/customer/create-ticket", "keywords": ["create", "new", "raise", "ticket"]},
            {"title": "My Tickets", "path": "/customer/dashboard", "keywords": ["tickets", "status", "reschedule"]},
            {"title": "Register Device", "path": "/customer/register-device", "keywords": ["device", "register", "warranty"]},
            {"title": "Notifications", "path": "/customer/dashboard", "keywords": ["notification", "alert", "eta"]}
        ]
    },
    UserRole.SUPPORT_ENGINEER.value: {
        "role_name": "Support Engineer",
        "overview": "You handle assigned tickets, optimize routes, and complete service visits.",
        "access": [
            "View assigned tickets and follow-ups",
            "Share live location and ETA",
            "Use AI copilot for diagnostics",
            "Export visit calendar"
        ],
        "ai_features": [
            "AI repair copilot",
            "Route/ETA suggestions",
            "Ticket summaries"
        ],
        "sections": [
            {"title": "Assigned Tickets", "path": "/engineer/dashboard", "keywords": ["assigned", "tickets", "jobs"]},
            {"title": "Ticket Details", "path": "/engineer/ticket/[id]", "keywords": ["details", "copilot", "notes"]},
            {"title": "Calendar Export", "path": "/engineer/dashboard", "keywords": ["calendar", "ics"]},
            {"title": "Live Location", "path": "/engineer/ticket/[id]", "keywords": ["location", "share", "track"]}
        ]
    },
    UserRole.CITY_ADMIN.value: {
        "role_name": "City Admin",
        "overview": "You manage city tickets, engineers, customer feedback, and inventory.",
        "access": [
            "City tickets list with SLA risk",
            "Bulk reassign and auto-redispatch",
            "Feedback follow-up workflow",
            "Set HQ coordinates for ETA"
        ],
        "ai_features": [
            "SLA risk tagging",
            "Auto-redispatch suggestions",
            "Geo/ETA insights"
        ],
        "sections": [
            {"title": "City Tickets", "path": "/city-admin/dashboard", "keywords": ["tickets", "sla", "risk"]},
            {"title": "Feedback", "path": "/city-admin/dashboard", "keywords": ["feedback", "complaint", "follow", "goodwill"]},
            {"title": "Engineers", "path": "/city-admin/dashboard", "keywords": ["engineer", "availability", "reassign"]},
            {"title": "HQ Settings", "path": "/city-admin/dashboard", "keywords": ["hq", "eta", "location"]}
        ]
    },
    UserRole.STATE_ADMIN.value: {
        "role_name": "State Admin",
        "overview": "You monitor multiple cities and manage SLA policies and reallocations.",
        "access": [
            "State-wide dashboards",
            "City drill-down pages",
            "SLA policy management",
            "Compliance alerts and bulk reassignment"
        ],
        "ai_features": [
            "SLA risk dashboard",
            "Compliance alerts",
            "Demand/forecast insights"
        ],
        "sections": [
            {"title": "State Dashboard", "path": "/state-admin/dashboard", "keywords": ["dashboard", "state", "risk"]},
            {"title": "City Drilldown", "path": "/state-admin/city/[id]", "keywords": ["city", "drill", "details"]},
            {"title": "SLA Policies", "path": "/state-admin/policies", "keywords": ["policy", "sla"]},
            {"title": "Compliance Alerts", "path": "/state-admin/dashboard", "keywords": ["compliance", "alerts"]}
        ]
    },
    UserRole.COUNTRY_ADMIN.value: {
        "role_name": "Country Admin",
        "overview": "You monitor national performance and partner outcomes.",
        "access": [
            "National SLA/MTTR/FTFR metrics",
            "State performance overview",
            "Partner performance and alerts",
            "Warranty abuse signals"
        ],
        "ai_features": [
            "Warranty abuse signals",
            "Partner performance analytics",
            "National health KPIs"
        ],
        "sections": [
            {"title": "National Dashboard", "path": "/country-admin/dashboard", "keywords": ["dashboard", "national", "kpi"]},
            {"title": "State Overview", "path": "/country-admin/dashboard", "keywords": ["state", "overview"]},
            {"title": "Warranty Signals", "path": "/country-admin/dashboard", "keywords": ["warranty", "abuse"]},
            {"title": "Partners", "path": "/country-admin/dashboard", "keywords": ["partner", "performance"]}
        ]
    },
    UserRole.ORGANIZATION_ADMIN.value: {
        "role_name": "Organization Admin",
        "overview": "You configure integrations, OEM sync, and org-wide settings.",
        "access": [
            "Integration settings and OEM sync",
            "Inventory oversight",
            "User management",
            "Org-level analytics"
        ],
        "ai_features": [
            "OEM sync monitoring",
            "Integration health stats",
            "Warranty sync insights"
        ],
        "sections": [
            {"title": "Org Dashboard", "path": "/organization-admin/dashboard", "keywords": ["dashboard", "org", "settings"]},
            {"title": "Integrations", "path": "/organization-admin/dashboard", "keywords": ["integration", "oem", "sync"]},
            {"title": "Users", "path": "/organization-admin/dashboard", "keywords": ["users", "roles"]},
            {"title": "Inventory", "path": "/organization-admin/dashboard", "keywords": ["inventory", "parts"]}
        ]
    },
    UserRole.PLATFORM_ADMIN.value: {
        "role_name": "Platform Admin",
        "overview": "You manage platform-wide settings, vendors, and org onboarding.",
        "access": [
            "Platform settings",
            "Vendor management",
            "Organization onboarding",
            "System reports"
        ],
        "ai_features": [
            "System health summaries",
            "Risk and anomaly signals"
        ],
        "sections": [
            {"title": "Platform Dashboard", "path": "/platform-admin/dashboard", "keywords": ["platform", "settings"]},
            {"title": "Vendors", "path": "/platform-admin/dashboard", "keywords": ["vendor", "partner"]},
            {"title": "Organizations", "path": "/platform-admin/dashboard", "keywords": ["organization", "onboarding"]},
            {"title": "Reports", "path": "/platform-admin/dashboard", "keywords": ["reports", "audit"]}
        ]
    },
    UserRole.VENDOR.value: {
        "role_name": "Vendor",
        "overview": "You manage parts and supply for assigned regions.",
        "access": [
            "Inventory and parts requests",
            "Dispatch updates",
            "Supply status updates"
        ],
        "ai_features": [
            "Demand forecasting",
            "Stock risk alerts"
        ],
        "sections": [
            {"title": "Vendor Dashboard", "path": "/vendor/dashboard", "keywords": ["inventory", "parts", "stock"]},
            {"title": "Requests", "path": "/vendor/dashboard", "keywords": ["request", "dispatch"]},
            {"title": "Supply Status", "path": "/vendor/dashboard", "keywords": ["supply", "status"]}
        ]
    }
}


class RoleAssistantService:
    """Return role-specific guidance for dashboard usage."""

    def answer(self, role: str, message: str, page: Optional[str] = None, session_id: Optional[str] = None, db=None, user_id: Optional[int] = None) -> Dict[str, Any]:
        guide = ROLE_GUIDES.get(role, None)
        if not guide:
            return {
                "reply": "I could not find guidance for this role yet. Please ask an admin.",
                "actions": [],
                "session_id": session_id or ""
            }

        msg = (message or "").strip().lower()
        session = None
        history_text = []
        if db:
            session = get_or_create_session(db, user_id=user_id, role=role, context_type="role_assistant", session_id=session_id)
            if msg:
                add_message(db, session, "user", message)
            history_text = [m.message for m in get_recent_messages(db, session, limit=6) if m.sender == "user"]
            session_id = session.session_id

        # Build role-scoped snapshot from DB (no cross-role leakage).
        data_context = self._build_role_data_context(role=role, user_id=user_id, db=db)

        if not msg or msg in {"help", "hello", "hi", "start"}:
            result = self._build_overview_reply(guide, data_context)
            result["session_id"] = session_id or ""
            if db and session:
                add_message(db, session, "assistant", result["reply"])
            return result

        if "history" in msg or "previous" in msg or "last" in msg:
            recent = history_text[-5:]
            reply = "Your recent questions:\n" + "\n".join([f"- {q}" for q in recent]) if recent else "No previous questions yet."
            result = {"reply": reply, "actions": self._actions_from_sections(guide["sections"]), "session_id": session_id or ""}
            if db and session:
                add_message(db, session, "assistant", reply)
            return result

        if "access" in msg or "role" in msg or "permission" in msg:
            result = {
                "reply": self._format_list(
                    f"Access for {guide['role_name']}:",
                    guide["access"]
                ),
                "actions": self._actions_from_sections(guide["sections"]),
                "session_id": session_id or ""
            }
            if db and session:
                add_message(db, session, "assistant", result["reply"])
            return result

        if "ai" in msg or "assistant" in msg or "smart" in msg:
            result = {
                "reply": self._format_list(
                    f"AI features for {guide['role_name']}:",
                    guide["ai_features"]
                ),
                "actions": self._actions_from_sections(guide["sections"]),
                "session_id": session_id or ""
            }
            if db and session:
                add_message(db, session, "assistant", result["reply"])
            return result

        if "where" in msg or "find" in msg or "location" in msg or "open" in msg:
            result = {
                "reply": self._format_list(
                    "You can find these sections:",
                    [f"{s['title']} ({s['path']})" for s in guide["sections"]]
                ),
                "actions": self._actions_from_sections(guide["sections"]),
                "session_id": session_id or ""
            }
            if db and session:
                add_message(db, session, "assistant", result["reply"])
            return result

        for section in guide["sections"]:
            if any(keyword in msg for keyword in section["keywords"]):
                result = {
                    "reply": f"Open {section['title']} here: {section['path']}. I can also guide you step-by-step if needed.",
                    "actions": [{"title": section["title"], "url": section["path"]}],
                    "session_id": session_id or ""
                }
                if db and session:
                    add_message(db, session, "assistant", result["reply"])
                return result

        # Try Gemini (preferred), then Groq, with strict role + data context.
        llm_reply = self._try_llm_response(
            role=role,
            guide=guide,
            message=message,
            page=page,
            data_context=data_context,
            history_text=history_text,
        )
        if llm_reply:
            result = {
                "reply": llm_reply,
                "actions": self._actions_from_sections(guide["sections"]),
                "session_id": session_id or "",
                "context": data_context,
            }
            if db and session:
                add_message(db, session, "assistant", result["reply"])
            return result

        result = self._build_overview_reply(guide, data_context)
        result["session_id"] = session_id or ""
        if db and session:
            add_message(db, session, "assistant", result["reply"])
        return result

    def _build_overview_reply(self, guide: Dict[str, Any], data_context: Dict[str, Any]) -> Dict[str, Any]:
        reply_parts = [
            guide["overview"],
            "",
            self._format_list("Top things you can do:", guide["access"]),
        ]
        snapshot = self._format_snapshot(data_context)
        if snapshot:
            reply_parts += ["", snapshot]
        reply = "\n".join(reply_parts)
        return {
            "reply": reply,
            "actions": self._actions_from_sections(guide["sections"]),
            "context": data_context,
        }

    def _format_list(self, title: str, items: List[str]) -> str:
        lines = [title] + [f"- {item}" for item in items]
        return "\n".join(lines)

    def _actions_from_sections(self, sections: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        return [{"title": s["title"], "url": s["path"]} for s in sections[:3]]

    def _format_snapshot(self, data_context: Dict[str, Any]) -> str:
        metrics = data_context.get("metrics") or {}
        if not metrics:
            return ""
        lines = ["Live snapshot from your role scope:"]
        for k, v in metrics.items():
            label = k.replace("_", " ").title()
            lines.append(f"- {label}: {v}")
        return "\n".join(lines)

    def _build_role_data_context(self, role: str, user_id: Optional[int], db) -> Dict[str, Any]:
        if not db or not user_id:
            return {"metrics": {}}

        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"metrics": {}}

        metrics: Dict[str, Any] = {}
        base_ticket_q = db.query(Ticket)

        if role == UserRole.CUSTOMER.value:
            q = base_ticket_q.filter(Ticket.customer_id == user.id)
            metrics["my_total_tickets"] = q.count()
            metrics["my_open_tickets"] = q.filter(Ticket.status.in_([TicketStatus.CREATED, TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS, TicketStatus.WAITING_PARTS])).count()
            metrics["my_resolved_tickets"] = q.filter(Ticket.status.in_([TicketStatus.RESOLVED, TicketStatus.CLOSED])).count()

        elif role == UserRole.SUPPORT_ENGINEER.value:
            q = base_ticket_q.filter(Ticket.assigned_engineer_id == user.id)
            metrics["assigned_tickets"] = q.count()
            metrics["in_progress_tickets"] = q.filter(Ticket.status == TicketStatus.IN_PROGRESS).count()
            metrics["waiting_parts_tickets"] = q.filter(Ticket.status == TicketStatus.WAITING_PARTS).count()

        elif role in {UserRole.CITY_ADMIN.value, UserRole.STATE_ADMIN.value, UserRole.COUNTRY_ADMIN.value, UserRole.ORGANIZATION_ADMIN.value}:
            q = base_ticket_q
            if user.organization_id:
                q = q.filter(Ticket.organization_id == user.organization_id)
            if role == UserRole.CITY_ADMIN.value and user.city_id:
                q = q.filter(Ticket.city_id == user.city_id)
            elif role == UserRole.STATE_ADMIN.value and user.state_id:
                q = q.filter(Ticket.state_id == user.state_id)
            elif role == UserRole.COUNTRY_ADMIN.value and user.country_id:
                q = q.filter(Ticket.country_id == user.country_id)
            metrics["total_tickets"] = q.count()
            metrics["open_tickets"] = q.filter(Ticket.status.in_([TicketStatus.CREATED, TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS, TicketStatus.WAITING_PARTS])).count()
            metrics["resolved_tickets"] = q.filter(Ticket.status.in_([TicketStatus.RESOLVED, TicketStatus.CLOSED])).count()
            if user.organization_id:
                metrics["active_users_in_org"] = db.query(User).filter(User.organization_id == user.organization_id, User.is_active == True).count()

        elif role == UserRole.PLATFORM_ADMIN.value:
            metrics["total_organizations"] = db.query(Organization).count()
            metrics["active_organizations"] = db.query(Organization).filter(Organization.is_active == True).count()
            metrics["total_users"] = db.query(User).count()
            metrics["total_tickets"] = db.query(Ticket).count()
            metrics["active_subscriptions"] = db.query(Subscription).filter(Subscription.status == "active").count()

        elif role == UserRole.VENDOR.value:
            vendor = db.query(Vendor).filter(Vendor.user_id == user.id).first()
            if not vendor:
                return {"metrics": metrics, "generated_at": datetime.now(timezone.utc).isoformat()}
            vendor_org_q = db.query(VendorOrganization).filter(VendorOrganization.vendor_id == vendor.id)
            org_ids = [x.organization_id for x in vendor_org_q.all()]
            metrics["linked_organizations"] = len(org_ids)
            if org_ids:
                t_q = base_ticket_q.filter(Ticket.organization_id.in_(org_ids))
                metrics["tickets_in_linked_orgs"] = t_q.count()
                metrics["open_tickets_in_linked_orgs"] = t_q.filter(Ticket.status.in_([TicketStatus.CREATED, TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS, TicketStatus.WAITING_PARTS])).count()

        return {"metrics": metrics, "generated_at": datetime.now(timezone.utc).isoformat()}

    def _try_gemini(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        api_key = (settings.GEMINI_API_KEY or "").strip()
        if not api_key:
            return None
        model = (settings.GEMINI_MODEL or "gemini-2.0-flash").strip()
        # Single user turn with explicit system block (works across Gemini 1.5/2.x REST)
        combined = (
            f"{system_prompt}\n\n---\n\n{user_prompt}\n\n"
            "Reply now in plain text only. No markdown headings unless necessary."
        )
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{quote(model, safe='')}:{quote('generateContent', safe='')}"
            f"?key={quote(api_key, safe='')}"
        )
        body = {
            "contents": [{"role": "user", "parts": [{"text": combined}]}],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 512,
                "topP": 0.95,
            },
        }
        try:
            req = urlrequest.Request(
                url,
                data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlrequest.urlopen(req, timeout=20) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            candidates = payload.get("candidates") or []
            if not candidates:
                return None
            parts = (candidates[0].get("content") or {}).get("parts") or []
            texts = [p.get("text", "") for p in parts if isinstance(p, dict)]
            content = "".join(texts).strip()
            return content or None
        except (URLError, HTTPError, TimeoutError, ValueError, json.JSONDecodeError, IndexError, KeyError):
            return None

    def _try_groq(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        api_key = settings.GROQ_API_KEY
        if not api_key:
            return None
        try:
            body = {
                "model": settings.GROQ_MODEL,
                "temperature": 0.2,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            }
            req = urlrequest.Request(
                "https://api.groq.com/openai/v1/chat/completions",
                data=json.dumps(body).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urlrequest.urlopen(req, timeout=15) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            content = (
                payload.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )
            return content or None
        except (URLError, HTTPError, TimeoutError, ValueError, json.JSONDecodeError):
            return None

    def _try_llm_response(
        self,
        role: str,
        guide: Dict[str, Any],
        message: str,
        page: Optional[str],
        data_context: Dict[str, Any],
        history_text: List[str],
    ) -> Optional[str]:
        system_prompt = (
            "You are the eRepairing in-app assistant. "
            "Answer ONLY using the user's role, allowed actions, dashboard sections, and the numeric data context provided. "
            "Do not invent tickets, users, or policies. If something is not in the context, say you do not have that data and point to the best matching section path. "
            "Stay relevant to the user's question. "
            "Be brief: at most ~120 words unless the user clearly asks for a long explanation. "
            "Use short paragraphs or bullet steps when helpful."
        )
        user_prompt = (
            f"Role: {role}\n"
            f"Role overview: {guide.get('overview')}\n"
            f"Allowed actions: {json.dumps(guide.get('access', []))}\n"
            f"Sections: {json.dumps(guide.get('sections', []))}\n"
            f"Current page: {page or 'unknown'}\n"
            f"Data context: {json.dumps(data_context)}\n"
            f"Recent user questions: {json.dumps(history_text[-5:])}\n"
            f"User question: {message}\n\n"
            "Give concise plain text with practical next steps (where to click / what to do next)."
        )

        text = self._try_gemini(system_prompt, user_prompt)
        if text:
            return text
        return self._try_groq(system_prompt, user_prompt)
