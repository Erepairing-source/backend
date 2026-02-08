"""
Role Assistant Service
Provides role-specific guidance for dashboard navigation and access.
"""
from typing import Dict, List, Any, Optional

from app.services.ai.chat_memory import get_or_create_session, add_message, get_recent_messages

from app.models.user import UserRole


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
        "overview": "You manage city tickets, engineers, complaints, and inventory.",
        "access": [
            "City tickets list with SLA risk",
            "Bulk reassign and auto-redispatch",
            "Complaints follow-up workflow",
            "Set HQ coordinates for ETA"
        ],
        "ai_features": [
            "SLA risk tagging",
            "Auto-redispatch suggestions",
            "Geo/ETA insights"
        ],
        "sections": [
            {"title": "City Tickets", "path": "/city-admin/dashboard", "keywords": ["tickets", "sla", "risk"]},
            {"title": "Complaints", "path": "/city-admin/dashboard", "keywords": ["complaint", "follow", "goodwill"]},
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

        if not msg or msg in {"help", "hello", "hi", "start"}:
            result = self._build_overview_reply(guide)
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

        result = self._build_overview_reply(guide)
        result["session_id"] = session_id or ""
        if db and session:
            add_message(db, session, "assistant", result["reply"])
        return result

    def _build_overview_reply(self, guide: Dict[str, Any]) -> Dict[str, Any]:
        reply = (
            f"{guide['overview']}\n\n"
            + self._format_list("Top things you can do:", guide["access"])
        )
        return {
            "reply": reply,
            "actions": self._actions_from_sections(guide["sections"])
        }

    def _format_list(self, title: str, items: List[str]) -> str:
        lines = [title] + [f"- {item}" for item in items]
        return "\n".join(lines)

    def _actions_from_sections(self, sections: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        return [{"title": s["title"], "url": s["path"]} for s in sections[:3]]
