"""
Signup workflow tests: location resolution and hierarchy.
Requires test DB; signup needs at least one Plan (created in test if needed).
"""
import pytest
from app.models.subscription import Plan
from app.models.location import Country
from app.models.user import UserRole


@pytest.fixture
def plan_in_db(test_db):
    """Ensure at least one active plan exists for signup."""
    from app.models.subscription import PlanType
    plan = test_db.query(Plan).filter(Plan.is_active == True).first()
    if not plan:
        plan = Plan(
            name="Starter",
            plan_type=PlanType.STARTER,
            monthly_price=999.0,
            annual_price=9990.0,
            max_engineers=5,
            is_active=True,
        )
        test_db.add(plan)
        test_db.commit()
        test_db.refresh(plan)
    return plan


@pytest.mark.api
def test_signup_requires_core_fields(client):
    """Signup returns 400 when required fields are missing."""
    response = client.post("/api/v1/signup/", json={})
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data


@pytest.mark.api
def test_signup_requires_location(client, plan_in_db):
    """Signup returns 400 when location (country/state/city) is missing."""
    payload = {
        "org_name": "Test Org",
        "org_type": "service_company",
        "org_email": "org@test.com",
        "org_phone": "+919999999999",
        "admin_name": "Admin",
        "admin_email": "admin@test.com",
        "admin_phone": "+918888888888",
        "admin_password": "password123",
        "plan_id": plan_in_db.id,
        "billing_period": "monthly",
    }
    response = client.post("/api/v1/signup/", json=payload)
    assert response.status_code == 400
    assert "location" in response.json().get("detail", "").lower() or "country" in response.json().get("detail", "").lower()


@pytest.mark.api
def test_signup_with_location_code_name(client, plan_in_db):
    """Signup with country_code, state_code, city_name succeeds and returns org + user + token."""
    import time
    ts = int(time.time())
    payload = {
        "org_name": f"Workflow Org {ts}",
        "org_type": "service_company",
        "org_email": f"org{ts}@workflow-test.com",
        "org_phone": "+919999999999",
        "org_address": "Test Address",
        "country_id": None,
        "country_code": "IN",
        "state_id": None,
        "state_code": "DL",
        "city_id": None,
        "city_name": "New Delhi",
        "admin_name": "Workflow Admin",
        "admin_email": f"admin{ts}@workflow-test.com",
        "admin_phone": f"+9177777{ts % 100000:05d}",
        "admin_password": "Test@12345",
        "plan_id": plan_in_db.id,
        "billing_period": "monthly",
        "vendor_code": "",
    }
    response = client.post("/api/v1/signup/", json=payload)
    assert response.status_code == 201, response.json()
    data = response.json()
    assert "organization" in data
    assert data["organization"]["name"] == payload["org_name"]
    assert "user" in data
    assert data["user"]["role"] == UserRole.ORGANIZATION_ADMIN.value
    assert "access_token" in data
    assert "subscription" in data


@pytest.mark.api
def test_signup_duplicate_org_email_fails(client, plan_in_db):
    """Signup with existing org email returns 400."""
    import time
    ts = int(time.time())
    payload = {
        "org_name": f"Dup Org {ts}",
        "org_type": "service_company",
        "org_email": "duplicate-org@workflow-test.com",
        "org_phone": "+919999999999",
        "country_code": "IN",
        "state_code": "DL",
        "city_name": "New Delhi",
        "admin_name": "Dup Admin",
        "admin_email": f"dupadmin{ts}@workflow-test.com",
        "admin_phone": f"+9166666{ts % 100000:05d}",
        "admin_password": "Test@12345",
        "plan_id": plan_in_db.id,
        "billing_period": "monthly",
    }
    r1 = client.post("/api/v1/signup/", json=payload)
    assert r1.status_code == 201
    payload["admin_email"] = f"dupadmin2{ts}@workflow-test.com"
    payload["admin_phone"] = f"+9166666{(ts % 100000) + 1:05d}"
    r2 = client.post("/api/v1/signup/", json=payload)
    assert r2.status_code == 400
    assert "already exists" in r2.json().get("detail", "").lower()
