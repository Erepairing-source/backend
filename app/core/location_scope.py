"""
Unified org + geography scoping for list/detail queries.

Hierarchy (same org when set, then location):
  Platform → all
  Organization admin → organization
  Country admin → organization + country
  State admin → organization + state
  City admin / engineer → organization + city (engineer: city or assigned on tickets only)
  Customer → self only (users/devices); own tickets
  Vendor → organizations linked to vendor (tickets/devices); not user listing
"""
from __future__ import annotations

from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Query, Session

from app.models.user import User, UserRole
from app.models.ticket import Ticket
from app.models.device import Device
from app.models.subscription import Vendor, VendorOrganization


def role_value(role) -> str:
    if role is None:
        return ""
    if isinstance(role, UserRole):
        return role.value
    return str(role)


def _org_id(user: User) -> Optional[int]:
    return user.organization_id


def apply_user_query_scope(query: Query, current_user: User) -> Query:
    """Scope a SQLAlchemy query on User to what the current role may see."""
    rv = role_value(current_user.role)

    if rv == UserRole.PLATFORM_ADMIN.value:
        return query

    if rv == UserRole.ORGANIZATION_ADMIN.value:
        if not current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account is not linked to an organization. Contact support.",
            )
        return query.filter(User.organization_id == current_user.organization_id)

    if rv == UserRole.COUNTRY_ADMIN.value:
        if not current_user.country_id:
            return query.filter(False)
        q = query.filter(User.country_id == current_user.country_id)
        if current_user.organization_id:
            q = q.filter(User.organization_id == current_user.organization_id)
        return q

    if rv == UserRole.STATE_ADMIN.value:
        if not current_user.state_id:
            return query.filter(False)
        q = query.filter(User.state_id == current_user.state_id)
        if current_user.organization_id:
            q = q.filter(User.organization_id == current_user.organization_id)
        return q

    if rv == UserRole.CITY_ADMIN.value:
        if not current_user.city_id:
            return query.filter(False)
        q = query.filter(User.city_id == current_user.city_id)
        if current_user.organization_id:
            q = q.filter(User.organization_id == current_user.organization_id)
        return q

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You cannot list users with this role.",
    )


def apply_ticket_query_scope(
    query: Query,
    current_user: User,
    db: Session,
    *,
    assigned_to_me: bool = False,
) -> Query:
    """Scope Ticket query by role (org + location). Vendor: linked orgs only."""
    rv = role_value(current_user.role)
    oid = _org_id(current_user)

    if rv == UserRole.CUSTOMER.value:
        return query.filter(Ticket.customer_id == current_user.id)

    if rv == UserRole.PLATFORM_ADMIN.value:
        return query

    if rv == UserRole.VENDOR.value:
        vendor = db.query(Vendor).filter(Vendor.user_id == current_user.id).first()
        if not vendor:
            return query.filter(False)
        org_ids = [
            vo.organization_id
            for vo in db.query(VendorOrganization).filter(VendorOrganization.vendor_id == vendor.id).all()
            if vo.organization_id
        ]
        if not org_ids:
            return query.filter(False)
        return query.filter(Ticket.organization_id.in_(org_ids))

    if rv == UserRole.ORGANIZATION_ADMIN.value:
        if not oid:
            return query.filter(False)
        return query.filter(Ticket.organization_id == oid)

    if rv == UserRole.COUNTRY_ADMIN.value:
        if not current_user.country_id:
            return query.filter(False)
        q = query.filter(Ticket.country_id == current_user.country_id)
        if oid:
            q = q.filter(Ticket.organization_id == oid)
        return q

    if rv == UserRole.STATE_ADMIN.value:
        if not current_user.state_id:
            return query.filter(False)
        q = query.filter(Ticket.state_id == current_user.state_id)
        if oid:
            q = q.filter(Ticket.organization_id == oid)
        return q

    if rv == UserRole.CITY_ADMIN.value:
        if not current_user.city_id:
            return query.filter(False)
        q = query.filter(Ticket.city_id == current_user.city_id)
        if oid:
            q = q.filter(Ticket.organization_id == oid)
        return q

    if rv == UserRole.SUPPORT_ENGINEER.value:
        if oid:
            query = query.filter(Ticket.organization_id == oid)
        if assigned_to_me:
            return query.filter(Ticket.assigned_engineer_id == current_user.id)
        return query.filter(
            or_(
                Ticket.city_id == current_user.city_id,
                Ticket.assigned_engineer_id == current_user.id,
            )
        )

    return query.filter(False)


def get_ticket_if_accessible(db: Session, ticket_id: int, current_user: User) -> Optional[Ticket]:
    """Single ticket if the current user may access it (same rules as list)."""
    return apply_ticket_query_scope(
        db.query(Ticket).filter(Ticket.id == ticket_id),
        current_user,
        db,
        assigned_to_me=False,
    ).first()


def _vendor_org_ids(db: Session, user_id: int) -> list:
    vendor = db.query(Vendor).filter(Vendor.user_id == user_id).first()
    if not vendor:
        return []
    return [
        vo.organization_id
        for vo in db.query(VendorOrganization).filter(VendorOrganization.vendor_id == vendor.id).all()
        if vo.organization_id
    ]


def device_query_for_user(db: Session, current_user: User) -> Query:
    """Base Device query visible to the current user (list or further filter)."""
    rv = role_value(current_user.role)
    oid = _org_id(current_user)

    if rv == UserRole.CUSTOMER.value:
        return db.query(Device).filter(Device.customer_id == current_user.id)

    if rv == UserRole.PLATFORM_ADMIN.value:
        return db.query(Device)

    if rv == UserRole.VENDOR.value:
        org_ids = _vendor_org_ids(db, current_user.id)
        if not org_ids:
            return db.query(Device).filter(Device.id == -1)
        return (
            db.query(Device)
            .join(User, Device.customer_id == User.id)
            .filter(User.organization_id.in_(org_ids))
        )

    if not oid:
        return db.query(Device).filter(Device.id == -1)

    base = (
        db.query(Device)
        .outerjoin(User, Device.customer_id == User.id)
        .filter(
            or_(
                Device.organization_id == oid,
                User.organization_id == oid,
            )
        )
    )

    if rv == UserRole.ORGANIZATION_ADMIN.value:
        return base

    if rv == UserRole.COUNTRY_ADMIN.value:
        if not current_user.country_id:
            return db.query(Device).filter(Device.id == -1)
        return base.filter(User.country_id == current_user.country_id)

    if rv == UserRole.STATE_ADMIN.value:
        if not current_user.state_id:
            return db.query(Device).filter(Device.id == -1)
        return base.filter(User.state_id == current_user.state_id)

    if rv == UserRole.CITY_ADMIN.value:
        if not current_user.city_id:
            return db.query(Device).filter(Device.id == -1)
        return base.filter(User.city_id == current_user.city_id)

    if rv == UserRole.SUPPORT_ENGINEER.value:
        if not current_user.city_id:
            return db.query(Device).filter(Device.id == -1)
        return base.filter(User.city_id == current_user.city_id)

    return db.query(Device).filter(Device.id == -1)


def get_device_if_accessible(db: Session, device_id: int, current_user: User) -> Optional[Device]:
    return device_query_for_user(db, current_user).filter(Device.id == device_id).first()
