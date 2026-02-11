"""
Create Platform Admin and one Organization Admin for AWS DB (or local).

Prerequisites:
  - DATABASE_URL set (e.g. in .env or environment)
  - DB created and migrations applied: alembic upgrade head

Run from project root:
  cd backend && python scripts/create_platform_and_org_admin.py
Or from backend dir:
  python -m scripts.create_platform_and_org_admin
"""
import sys
import os

# Ensure backend app is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models.user import User, UserRole
from app.models.organization import Organization, OrganizationType


# Credentials to create (change if needed)
PLATFORM_ADMIN_EMAIL = "admin@erepairing.com"
PLATFORM_ADMIN_PASSWORD = "Admin@123"
PLATFORM_ADMIN_PHONE = "+91000000001"

ORG_ADMIN_EMAIL = "orgadmin@erepairing.com"
ORG_ADMIN_PASSWORD = "OrgAdmin@123"
ORG_ADMIN_PHONE = "+91000000002"
ORG_NAME = "eRepairing Demo Organization"
ORG_EMAIL = "org@erepairing.com"
ORG_PHONE = "+91000000003"


def create_platform_admin(db: Session) -> User | None:
    """Create Platform Admin user if not exists."""
    existing = db.query(User).filter(User.email == PLATFORM_ADMIN_EMAIL).first()
    if existing:
        print("Platform Admin already exists (skip).")
        return existing

    user = User(
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
    db.add(user)
    db.commit()
    db.refresh(user)
    print("Platform Admin created.")
    return user


def create_organization_and_org_admin(db: Session):
    """Create one Organization and its Organization Admin user if not exist."""
    # Create org if not exists
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
        print("Organization created:", org.name)
    else:
        print("Organization already exists (skip):", org.name)

    # Create Org Admin user if not exists
    existing = db.query(User).filter(User.email == ORG_ADMIN_EMAIL).first()
    if existing:
        print("Organization Admin already exists (skip).")
        return org, existing

    user = User(
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
    db.add(user)
    db.commit()
    db.refresh(user)
    print("Organization Admin created.")
    return org, user


def main():
    db: Session = SessionLocal()
    try:
        print("Creating Platform Admin and Organization Admin...")
        platform_admin = create_platform_admin(db)
        org, org_admin = create_organization_and_org_admin(db)
        print()
        print("=" * 60)
        print("USERS CREATED – use these to log in (e.g. on AWS)")
        print("=" * 60)
        print()
        print("1) PLATFORM ADMIN")
        print("   ID:      ", platform_admin.id if platform_admin else "N/A")
        print("   Email:   ", PLATFORM_ADMIN_EMAIL)
        print("   Password:", PLATFORM_ADMIN_PASSWORD)
        print()
        print("2) ORGANIZATION ADMIN")
        print("   ID:      ", org_admin.id if org_admin else "N/A")
        print("   Email:   ", ORG_ADMIN_EMAIL)
        print("   Password:", ORG_ADMIN_PASSWORD)
        print("   Org ID:  ", org.id if org else "N/A")
        print()
        print("=" * 60)
    finally:
        db.close()


if __name__ == "__main__":
    main()
