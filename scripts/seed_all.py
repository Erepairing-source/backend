"""
Seed all reference data and default users for AWS (RDS).

Intended for AWS deployment. Set DATABASE_URL to your AWS RDS (PostgreSQL).
Not for local MySQL – run this against your production/staging RDS after migrations.

Seeds:
  1. Roles (reference: UserRole enum – no DB table, printed for docs)
  2. Locations: India (IN), 35 states, all cities (UP 75+)
  3. Plans: Starter, Growth, Enterprise
  4. Platform Admin user
  5. One Organization + Organization Admin user
  6. Demo subscription for that org

Usage (from backend directory):
  set DATABASE_URL to your AWS RDS connection string (PostgreSQL), then:
  python scripts/seed_all.py

Prerequisite: alembic upgrade head (on the same AWS DB)
"""
import os
import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models.user import User, UserRole
from app.models.organization import Organization, OrganizationType
from app.models.location import Country, State, City
from app.models.subscription import Plan, PlanType, Subscription, BillingPeriod


# --- Config (change if needed) ---
PLATFORM_ADMIN_EMAIL = "admin@erepairing.com"
PLATFORM_ADMIN_PASSWORD = "Admin@123"
PLATFORM_ADMIN_PHONE = "+91000000001"

ORG_ADMIN_EMAIL = "orgadmin@erepairing.com"
ORG_ADMIN_PASSWORD = "OrgAdmin@123"
ORG_ADMIN_PHONE = "+91000000002"

ORG_NAME = "eRepairing Demo Organization"
ORG_EMAIL = "org@erepairing.com"
ORG_PHONE = "+91000000003"


def seed_roles_info() -> None:
    """Roles are defined in code (UserRole enum). No DB seed; just print for reference."""
    roles = [r.value for r in UserRole]
    print("[OK] Roles (from code, no DB table):", ", ".join(roles))


def seed_locations(db: Session) -> None:
    """India (IN), 35 states, all cities from app.data.india_locations (UP 75+)."""
    from app.data.india_locations import INDIA_STATES, INDIA_CITIES_BY_STATE

    india = db.query(Country).filter(Country.code == "IN").first()
    if not india:
        india = db.query(Country).filter(Country.name == "India").first()
        if india:
            if india.code != "IN":
                india.code = "IN"
                db.commit()
                db.refresh(india)
            print("[OK] Country India already exists (code set to IN).")
        else:
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
        state = db.query(State).filter(State.name == state_name, State.country_id == india.id).first()
        if not state:
            state = State(name=state_name, code=state_code, country_id=india.id)
            db.add(state)
            db.commit()
            db.refresh(state)
            print(f"  [OK] Created state: {state_name} ({state_code})")
        for city_name in INDIA_CITIES_BY_STATE.get(state_name, []):
            if not db.query(City).filter(City.name == city_name, City.state_id == state.id).first():
                db.add(City(name=city_name, state_id=state.id))
                db.commit()
        print(f"    -> {len(INDIA_CITIES_BY_STATE.get(state_name, []))} cities")

    total_cities = db.query(City).join(State, City.state_id == State.id).filter(State.country_id == india.id).count()
    print(f"[OK] India: {len(INDIA_STATES)} states, {total_cities} cities (UP 75+)")


def seed_plans(db: Session) -> None:
    """Starter, Growth, Enterprise plans."""
    plans_data = [
        {
            "name": "Starter",
            "plan_type": PlanType.STARTER,
            "monthly_price": 20000.0 / 12,
            "annual_price": 20000.0,
            "max_engineers": 2,
            "max_organizations": 1,
            "max_tickets_per_month": 500,
            "features": {"ai_triage": False, "demand_forecasting": False, "copilot": False, "multilingual_chatbot": True, "advanced_analytics": False},
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
            "features": {"ai_triage": True, "demand_forecasting": True, "copilot": True, "multilingual_chatbot": True, "advanced_analytics": False},
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
            "features": {"ai_triage": True, "demand_forecasting": True, "copilot": True, "multilingual_chatbot": True, "advanced_analytics": True, "api_access": True, "iot_integration": True, "sla_guarantees": True},
            "description": "Full-featured solution for large enterprises",
            "display_order": 3,
        },
    ]
    for plan_data in plans_data:
        name = plan_data["name"]
        if not db.query(Plan).filter(Plan.name == name).first():
            db.add(Plan(**plan_data))
            db.commit()
            print(f"[OK] Created plan: {name}")
        else:
            print(f"[OK] Plan already exists: {name}")


def seed_platform_admin(db: Session) -> User:
    """Create Platform Admin user if not exists."""
    admin = db.query(User).filter(User.email == PLATFORM_ADMIN_EMAIL).first()
    if admin:
        print("[OK] Platform Admin already exists.")
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


def seed_org_and_org_admin(db: Session) -> tuple:
    """One demo Organization and its Organization Admin."""
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
        print(f"[OK] Created Organization: {org.name}")
    else:
        print(f"[OK] Organization already exists: {org.name}")

    org_admin = db.query(User).filter(User.email == ORG_ADMIN_EMAIL).first()
    if org_admin:
        print("[OK] Organization Admin already exists.")
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
    """Attach Growth (or first available) plan to demo org."""
    if db.query(Subscription).filter(Subscription.organization_id == org.id).first():
        print("[OK] Subscription already exists for demo org.")
        return
    plan = db.query(Plan).filter(Plan.name == "Growth").first() or db.query(Plan).filter(Plan.name == "Starter").first() or db.query(Plan).first()
    if not plan:
        print("[WARN] No plans found; skip subscription.")
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
    print(f"[OK] Created demo subscription (plan: {plan.name}).")


def main() -> None:
    db = SessionLocal()
    try:
        print("=" * 60)
        print("SEED ALL – roles, locations, plans, platform admin, org admin, subscription")
        print("=" * 60)
        print()

        seed_roles_info()
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

        # Summary with IDs and passwords
        india = db.query(Country).filter(Country.code == "IN").first()
        state_count = db.query(State).filter(State.country_id == india.id).count() if india else 0
        city_count = db.query(City).join(State, City.state_id == State.id).filter(State.country_id == india.id).count() if india else 0

        print("=" * 60)
        print("SEED COMPLETE – use these to log in")
        print("=" * 60)
        print()
        print("Roles (code):", ", ".join(r.value for r in UserRole))
        print()
        print("Locations: India (IN), country_id =", india.id if india else "N/A", f"| {state_count} states | {city_count} cities")
        print()
        print("1) PLATFORM ADMIN")
        print("   User ID:  ", platform_admin.id if platform_admin else "N/A")
        print("   Email:    ", PLATFORM_ADMIN_EMAIL)
        print("   Password: ", PLATFORM_ADMIN_PASSWORD)
        print()
        print("2) ORGANIZATION ADMIN")
        print("   Org ID:   ", org.id if org else "N/A")
        print("   User ID:  ", org_admin.id if org_admin else "N/A")
        print("   Email:    ", ORG_ADMIN_EMAIL)
        print("   Password: ", ORG_ADMIN_PASSWORD)
        print()
        print("Use these credentials on your frontend (point API to AWS backend).")
        print("=" * 60)
    finally:
        db.close()


if __name__ == "__main__":
    main()
