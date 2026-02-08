"""
Main API router
"""
from fastapi import APIRouter

from app.api.v1.endpoints import auth, tickets, users, organizations, ai, inventory, warranty, platform_admin, vendor, locations, signup, state_admin, country_admin, org_admin, city_admin, reports, devices, notifications, routes

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(tickets.router, prefix="/tickets", tags=["tickets"])
api_router.include_router(devices.router, prefix="/devices", tags=["devices"])
api_router.include_router(organizations.router, prefix="/organizations", tags=["organizations"])
api_router.include_router(ai.router, prefix="/ai", tags=["ai"])
api_router.include_router(inventory.router, prefix="/inventory", tags=["inventory"])
api_router.include_router(warranty.router, prefix="/warranty", tags=["warranty"])
api_router.include_router(platform_admin.router, prefix="/platform-admin", tags=["platform-admin"])
api_router.include_router(vendor.router, prefix="/vendor", tags=["vendor"])
api_router.include_router(locations.router, prefix="/locations", tags=["locations"])
api_router.include_router(signup.router, prefix="/signup", tags=["signup"])
api_router.include_router(state_admin.router, prefix="/state-admin", tags=["state-admin"])
api_router.include_router(country_admin.router, prefix="/country-admin", tags=["country-admin"])
api_router.include_router(org_admin.router, prefix="/org-admin", tags=["org-admin"])
api_router.include_router(city_admin.router, prefix="/city-admin", tags=["city-admin"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(routes.router, prefix="/routes", tags=["routes"])

