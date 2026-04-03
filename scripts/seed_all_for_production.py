"""
Seed all core data needed to run the application in a fresh database.

This script will:
- Create India + a set of key states and cities
- Create default subscription plans (Starter, Growth, Enterprise)
- Create one Platform Admin user
- Create one demo Organization and its Organization Admin user

It is safe to run multiple times; existing rows are reused.

Usage (from backend directory, with DATABASE_URL pointing to your AWS DB and
all migrations already applied with `alembic upgrade head`):

    python scripts/seed_all_for_production.py
"""

import os
import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

# Ensure backend app is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal  # noqa: E402
from app.core.security import get_password_hash  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402
from app.models.organization import Organization, OrganizationType  # noqa: E402
from app.models.location import Country, State, City  # noqa: E402
from app.models.subscription import (  # noqa: E402
    Plan,
    PlanType,
    Subscription,
    BillingPeriod,
)


# === Credentials and defaults (change if you want different values) ==========

PLATFORM_ADMIN_EMAIL = "admin@erepairing.com"
PLATFORM_ADMIN_PASSWORD = "Admin@123"
PLATFORM_ADMIN_PHONE = "+91000000001"

ORG_ADMIN_EMAIL = "orgadmin@erepairing.com"
ORG_ADMIN_PASSWORD = "OrgAdmin@123"
ORG_ADMIN_PHONE = "+91000000002"

ORG_NAME = "eRepairing Demo Organization"
ORG_EMAIL = "org@erepairing.com"
ORG_PHONE = "+91000000003"


def seed_locations(db: Session) -> None:
    """Create India (code IN) and seed all 35 states + all cities from app.data.india_locations (UP 75+)."""
    from app.data.india_locations import INDIA_STATES, INDIA_CITIES_BY_STATE

    india = db.query(Country).filter(Country.code == "IN").first()
    if not india:
        india = Country(name="India", code="IN")
        db.add(india)
        db.commit()
        db.refresh(india)
        print("[OK] Created country: India (IN)")
    else:
        print("[OK] Country already exists: India (IN)")

    for s in INDIA_STATES:
        state_name = s["name"]
        state_code = s.get("code") or ""
        state = (
            db.query(State)
            .filter(State.name == state_name, State.country_id == india.id)
            .first()
        )
        if not state:
            state = State(name=state_name, code=state_code, country_id=india.id)
            db.add(state)
            db.commit()
            db.refresh(state)
            print(f"  [OK] Created state: {state_name} ({state_code})")
        else:
            print(f"  [OK] State already exists: {state_name}")

        for city_name in INDIA_CITIES_BY_STATE.get(state_name, []):
            if not db.query(City).filter(City.name == city_name, City.state_id == state.id).first():
                db.add(City(name=city_name, state_id=state.id))
                db.commit()
        print(f"    -> {len(INDIA_CITIES_BY_STATE.get(state_name, []))} cities")

    total_cities = db.query(City).join(State, City.state_id == State.id).filter(State.country_id == india.id).count()
    print(f"[OK] India: {len(INDIA_STATES)} states, {total_cities} cities (UP 75+)")


def seed_plans(db: Session) -> None:
    """Create default subscription plans (Starter, Growth, Enterprise)."""
    plans_data = [
        {
            "name": "Starter",
            "plan_type": PlanType.STARTER,
            "monthly_price": 20000.0 / 12,
            "annual_price": 20000.0,
            "max_engineers": 2,
            "max_organizations": 1,
            "max_tickets_per_month": 500,
            "features": {
                "ai_triage": False,
                "demand_forecasting": False,
                "copilot": False,
                "multilingual_chatbot": True,
                "advanced_analytics": False,
            },
            "description": "Perfect for small manufacturers",
            "display_order": 1,
        },
        {
            "name": "Growth",
            "plan_type": PlanType.GROWTH,
            "monthly_price": 200000.0 / 12,
            "annual_price": 200000.0,
            "max_engineers": 10,
            "max_organizations": 5,
            "max_tickets_per_month": 5000,
            "features": {
                "ai_triage": True,
                "demand_forecasting": True,
                "copilot": True,
                "multilingual_chatbot": True,
                "advanced_analytics": False,
            },
            "description": "For growing service networks",
            "display_order": 2,
        },
        {
            "name": "Enterprise",
            "plan_type": PlanType.ENTERPRISE,
            "monthly_price": 1000000.0 / 12,
            "annual_price": 1000000.0,
            "max_engineers": None,
            "max_organizations": None,
            "max_tickets_per_month": None,
            "features": {
                "ai_triage": True,
                "demand_forecasting": True,
                "copilot": True,
                "multilingual_chatbot": True,
                "advanced_analytics": True,
                "api_access": True,
                "iot_integration": True,
                "sla_guarantees": True,
            },
            "description": "Full-featured solution for large enterprises",
            "display_order": 3,
        },
    ]

    for plan_data in plans_data:
        name = plan_data["name"]
        plan = db.query(Plan).filter(Plan.name == name).first()
        if not plan:
            plan = Plan(**plan_data)
            db.add(plan)
            db.commit()
            print(f"[OK] Created plan: {name}")
        else:
            print(f"[OK] Plan already exists: {name}")


def seed_platform_admin(db: Session) -> User:
    """Create Platform Admin user if not exists."""
    admin = db.query(User).filter(User.email == PLATFORM_ADMIN_EMAIL).first()
    if admin:
        print("[OK] Platform Admin already exists (will not overwrite password).")
        return admin

    admin = User(
        email=PLATFORM_ADMIN_EMAIL,
        phone=PLATFORM_ADMIN_PHONE,
        password_hash=get_password_hash(PLATFORM_ADMIN_PASSWORD),
        full_name="Platform Admin",
        role=UserRole.PLATFORM_ADMIN,
        organization_id=None,
        country_id=None,
        state_id=None,
        city_id=None,
        is_active=True,
        is_verified=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    print("[OK] Created Platform Admin user.")
    return admin


def seed_org_and_org_admin(db: Session) -> tuple[Organization, User]:
    """Create one demo organization and its Organization Admin (idempotent)."""
    org = db.query(Organization).filter(Organization.email == ORG_EMAIL).first()
    if not org:
        org = Organization(
            name=ORG_NAME,
            org_type=OrganizationType.SERVICE_COMPANY,
            email=ORG_EMAIL,
            phone=ORG_PHONE,
            address=None,
            country_id=None,
            state_id=None,
            city_id=None,
            parent_organization_id=None,
            subscription_id=None,
            is_active=True,
        )
        db.add(org)
        db.commit()
        db.refresh(org)
        print(f"[OK] Created demo Organization: {org.name}")
    else:
        print(f"[OK] Organization already exists: {org.name}")

    org_admin = db.query(User).filter(User.email == ORG_ADMIN_EMAIL).first()
    if org_admin:
        print("[OK] Organization Admin already exists (will not overwrite password).")
        return org, org_admin

    org_admin = User(
        email=ORG_ADMIN_EMAIL,
        phone=ORG_ADMIN_PHONE,
        password_hash=get_password_hash(ORG_ADMIN_PASSWORD),
        full_name="Organization Admin",
        role=UserRole.ORGANIZATION_ADMIN,
        organization_id=org.id,
        country_id=None,
        state_id=None,
        city_id=None,
        is_active=True,
        is_verified=True,
    )
    db.add(org_admin)
    db.commit()
    db.refresh(org_admin)
    print("[OK] Created Organization Admin user.")
    return org, org_admin


def seed_demo_subscription(db: Session, org: Organization) -> None:
    """
    Attach a subscription to the demo organization (if none exists),
    using the Growth plan by default.
    """
    existing_sub = db.query(Subscription).filter(Subscription.organization_id == org.id).first()
    if existing_sub:
        print(f"[OK] Subscription already exists for org {org.id} (status={existing_sub.status}).")
        return

    # Prefer Growth plan, then Starter, then any plan.
    plan = (
        db.query(Plan)
        .filter(Plan.name == "Growth")
        .first()
        or db.query(Plan).filter(Plan.name == "Starter").first()
        or db.query(Plan).first()
    )
    if not plan:
        print("[WARN] No plans found; skipping demo subscription.")
        return

    now = datetime.now(timezone.utc)
    end_date = now + timedelta(days=365)

    sub = Subscription(
        organization_id=org.id,
        plan_id=plan.id,
        billing_period=BillingPeriod.ANNUAL,
        current_price=plan.annual_price,
        currency="INR",
        start_date=now,
        end_date=end_date,
        trial_end_date=None,
        status="active",
        auto_renew=True,
        payment_method="manual",
        last_payment_date=now,
        next_billing_date=end_date,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    print(f"[OK] Created demo subscription for org {org.id} with plan {plan.name}.")


def main() -> None:
    db: Session = SessionLocal()
    try:
        print("Seeding core data into database...")
        print()

        seed_locations(db)
        print()
        seed_plans(db)
        print()
        platform_admin = seed_platform_admin(db)
        print()
        org, org_admin = seed_org_and_org_admin(db)
        print()
        seed_demo_subscription(db, org)
        print()

        print("=" * 70)
        print("SEED COMPLETE – use these credentials to log in")
        print("=" * 70)
        print()
        print("1) PLATFORM ADMIN")
        print("   ID:       ", platform_admin.id if platform_admin else "N/A")
        print("   Email:    ", PLATFORM_ADMIN_EMAIL)
        print("   Password: ", PLATFORM_ADMIN_PASSWORD)
        print()
        print("2) ORGANIZATION ADMIN")
        print("   Org ID:   ", org.id if org else "N/A")
        print("   User ID:  ", org_admin.id if org_admin else "N/A")
        print("   Email:    ", ORG_ADMIN_EMAIL)
        print("   Password: ", ORG_ADMIN_PASSWORD)
        print()
        print("You can now log in on the frontend using these accounts.")
        print("=" * 70)
    finally:
        db.close()


if __name__ == "__main__":
    main()

