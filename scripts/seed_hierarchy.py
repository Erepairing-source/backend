"""
Seed hierarchy test data: 1 country, 2-3 states, 2 cities per state, 1 org,
and users: org admin, country admin, state admin per state, city admin + support engineer per city, 2 customers.

Use for manual testing of hierarchy flow (org → country → state → city).
Run from backend directory after: alembic upgrade head

  set DATABASE_URL=...   (optional; default from .env)
  python scripts/seed_hierarchy.py
"""
import os
import sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models.user import User, UserRole
from app.models.organization import Organization, OrganizationType
from app.models.location import Country, State, City
from app.models.subscription import Plan, PlanType, BillingPeriod, Subscription

TEST_PASSWORD = "HierarchyTest1!"


def seed_hierarchy(db):
    # Country
    country = db.query(Country).filter(Country.code == "IN").first() or db.query(Country).filter(Country.name == "India").first()
    if not country:
        country = Country(name="India", code="IN")
        db.add(country)
        db.flush()
        print("[OK] Created country: India (IN)")
    else:
        print("[OK] Country exists: India (IN)")

    # States: Karnataka, Maharashtra, Tamil Nadu
    state_names = [("Karnataka", "KA"), ("Maharashtra", "MH"), ("Tamil Nadu", "TN")]
    states = []
    for name, code in state_names:
        s = db.query(State).filter(State.name == name, State.country_id == country.id).first()
        if not s:
            s = State(name=name, code=code, country_id=country.id)
            db.add(s)
            db.flush()
            print(f"  [OK] Created state: {name} ({code})")
        states.append(s)

    # Cities: 2 per state
    city_names = {
        "Karnataka": ["Bengaluru", "Mysuru"],
        "Maharashtra": ["Mumbai", "Pune"],
        "Tamil Nadu": ["Chennai", "Coimbatore"],
    }
    cities = []
    for state in states:
        for cname in city_names.get(state.name, []):
            c = db.query(City).filter(City.name == cname, City.state_id == state.id).first()
            if not c:
                c = City(name=cname, state_id=state.id)
                db.add(c)
                db.flush()
                print(f"    [OK] Created city: {cname} ({state.name})")
            cities.append(c)

    # Plan (if missing)
    plan = db.query(Plan).filter(Plan.is_active == True).first()
    if not plan:
        plan = Plan(
            name="HierarchyPlan",
            plan_type=PlanType.STARTER,
            monthly_price=999.0,
            annual_price=9990.0,
            max_engineers=10,
            is_active=True,
            is_visible=True,
        )
        db.add(plan)
        db.flush()
        print("[OK] Created plan: HierarchyPlan")

    # Organization
    org = db.query(Organization).filter(Organization.email == "hierarchy-org@test.com").first()
    if not org:
        org = Organization(
            name="Hierarchy Test Org",
            org_type=OrganizationType.SERVICE_COMPANY,
            email="hierarchy-org@test.com",
            phone="+911111111111",
            country_id=country.id,
            state_id=states[0].id,
            city_id=cities[0].id,
            is_active=True,
        )
        db.add(org)
        db.flush()
        print("[OK] Created org: Hierarchy Test Org")

    # Subscription
    if not db.query(Subscription).filter(Subscription.organization_id == org.id).first():
        start = datetime.now(timezone.utc)
        sub = Subscription(
            organization_id=org.id,
            plan_id=plan.id,
            billing_period=BillingPeriod.MONTHLY,
            current_price=999.0,
            currency="INR",
            status="active",
            start_date=start,
            end_date=start + timedelta(days=30),
        )
        db.add(sub)
        db.flush()
        org.subscription_id = sub.id
        db.flush()
        print("[OK] Created subscription for org")

    pwd_hash = get_password_hash(TEST_PASSWORD)
    users_created = {}

    # Org admin
    org_admin = db.query(User).filter(User.email == "orgadmin@hierarchy.example.com").first()
    if not org_admin:
        org_admin = User(
            email="orgadmin@hierarchy.example.com",
            phone="+910001000001",
            password_hash=pwd_hash,
            full_name="Org Admin",
            role=UserRole.ORGANIZATION_ADMIN,
            organization_id=org.id,
            country_id=country.id,
            state_id=states[0].id,
            city_id=cities[0].id,
            is_active=True,
            is_verified=True,
        )
        db.add(org_admin)
        db.flush()
        users_created["org_admin"] = org_admin
        print("[OK] Created user: orgadmin@hierarchy.example.com (Organization Admin)")

    # Country admin
    country_admin = db.query(User).filter(User.email == "countryadmin@hierarchy.example.com").first()
    if not country_admin:
        country_admin = User(
            email="countryadmin@hierarchy.example.com",
            phone="+910001000002",
            password_hash=pwd_hash,
            full_name="Country Admin",
            role=UserRole.COUNTRY_ADMIN,
            organization_id=org.id,
            country_id=country.id,
            state_id=None,
            city_id=None,
            is_active=True,
            is_verified=True,
        )
        db.add(country_admin)
        db.flush()
        users_created["country_admin"] = country_admin
        print("[OK] Created user: countryadmin@hierarchy.example.com (Country Admin)")

    # State admins (one per state)
    for state in states:
        email = f"stateadmin_{state.code.lower()}@hierarchy.example.com"
        if db.query(User).filter(User.email == email).first():
            continue
        u = User(
            email=email,
            phone=f"+9100010000{state.id}",
            password_hash=pwd_hash,
            full_name=f"State Admin {state.name}",
            role=UserRole.STATE_ADMIN,
            organization_id=org.id,
            country_id=country.id,
            state_id=state.id,
            city_id=None,
            is_active=True,
            is_verified=True,
        )
        db.add(u)
        db.flush()
        users_created[f"state_admin_{state.code}"] = u
        print(f"[OK] Created user: {email} (State Admin {state.name})")

    # City admins and support engineers (one per city)
    for city in cities:
        state = next(s for s in states if s.id == city.state_id)
        for role, suffix in [(UserRole.CITY_ADMIN, "cityadmin"), (UserRole.SUPPORT_ENGINEER, "engineer")]:
            email = f"{suffix}_{city.id}@hierarchy.example.com"
            if db.query(User).filter(User.email == email).first():
                continue
            u = User(
                email=email,
                phone=f"+910002{city.id:04d}" if role == UserRole.CITY_ADMIN else f"+910003{city.id:04d}",
                password_hash=pwd_hash,
                full_name=f"{role.value.replace('_', ' ').title()} {city.name}",
                role=role,
                organization_id=org.id,
                country_id=country.id,
                state_id=state.id,
                city_id=city.id,
                is_active=True,
                is_available=(role == UserRole.SUPPORT_ENGINEER),
                is_verified=True,
            )
            db.add(u)
            db.flush()
            key = f"city_admin_{city.id}" if role == UserRole.CITY_ADMIN else f"engineer_{city.id}"
            users_created[key] = u
        print(f"[OK] Created city admin + engineer for {city.name}")

    # Fixed test users for Playwright (always cityadmin_test@, engineer_test@ so tests don't depend on city id)
    first_city = cities[0]
    first_state = next(s for s in states if s.id == first_city.state_id)
    for email, role, name in [
        ("cityadmin_test@hierarchy.example.com", UserRole.CITY_ADMIN, "City Admin Test"),
        ("engineer_test@hierarchy.example.com", UserRole.SUPPORT_ENGINEER, "Engineer Test"),
    ]:
        if not db.query(User).filter(User.email == email).first():
            u = User(
                email=email,
                phone="+910009000001" if role == UserRole.CITY_ADMIN else "+910009000002",
                password_hash=pwd_hash,
                full_name=name,
                role=role,
                organization_id=org.id,
                country_id=country.id,
                state_id=first_state.id,
                city_id=first_city.id,
                is_active=True,
                is_available=(role == UserRole.SUPPORT_ENGINEER),
                is_verified=True,
            )
            db.add(u)
            db.flush()
            print(f"[OK] Created user: {email} (for Playwright)")

    # Customers (2: different cities)
    for email, name, city in [
        ("customer1@hierarchy.example.com", "Customer One", cities[0]),
        ("customer2@hierarchy.example.com", "Customer Two", cities[-1]),
    ]:
        if db.query(User).filter(User.email == email).first():
            continue
        state = next(s for s in states if s.id == city.state_id)
        u = User(
            email=email,
            phone=f"+9100040000{city.id}",
            password_hash=pwd_hash,
            full_name=name,
            role=UserRole.CUSTOMER,
            organization_id=org.id,
            country_id=country.id,
            state_id=state.id,
            city_id=city.id,
            is_active=True,
            is_verified=True,
        )
        db.add(u)
        db.flush()
        users_created[email.split("@")[0]] = u
        print(f"[OK] Created user: {email} (Customer)")

    db.commit()
    return {
        "country": country,
        "states": states,
        "cities": cities,
        "org": org,
        "users": users_created,
    }


def main():
    db = SessionLocal()
    try:
        print("=" * 60)
        print("SEED HIERARCHY – country, states, cities, org, users")
        print("=" * 60)
        data = seed_hierarchy(db)
        print()
        print("=" * 60)
        print("HIERARCHY SEED COMPLETE – use these to test")
        print("=" * 60)
        print("Password for all users:", TEST_PASSWORD)
        print()
        print("1) Org Admin (sees all org users & tickets)")
        print("   orgadmin@hierarchy.example.com")
        print("2) Country Admin (sees all states in country)")
        print("   countryadmin@hierarchy.example.com")
        print("3) State Admins (see only their state)")
        print("   stateadmin_ka@hierarchy.example.com  – Karnataka")
        print("   stateadmin_mh@hierarchy.example.com  – Maharashtra")
        print("   stateadmin_tn@hierarchy.example.com  – Tamil Nadu")
        print("4) City Admins – cityadmin_<id>@... or cityadmin_test@hierarchy.example.com (Playwright)")
        print("5) Support Engineers – engineer_<id>@... or engineer_test@hierarchy.example.com (Playwright)")
        print("6) Customers – customer1@..., customer2@...")
        print("=" * 60)
    finally:
        db.close()


if __name__ == "__main__":
    main()
