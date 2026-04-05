"""
eRepairing.com - Main FastAPI Application
"""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import asyncio
import os
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy import text

from app.core.config import settings
from app.core.database import Base, engine
from app.api.v1.api import api_router
from app.services.oem_sync_job import start_oem_sync_loop, try_acquire_oem_sync_leader_lock

# Import all models to ensure they're registered
from app.models import (
    platform_settings, product, product_part, sla_policy, integration,
    escalation, notification, reminder_log,
)
from app.models.email_verification_otp import EmailVerificationOTP

app = FastAPI(
    title="eRepairing.com API",
    description="AI-first Service Management Platform for device manufacturers",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)


@app.on_event("startup")
async def startup_event():
    """Create database tables on startup"""
    try:
        # Create all tables if they don't exist
        tables_to_create = [
            platform_settings.PlatformSettings.__table__,
            product.Product.__table__,
            product.ProductModel.__table__,
            product_part.ProductPart.__table__,
            sla_policy.SLAPolicy.__table__,
            sla_policy.ServicePolicy.__table__,
            integration.Integration.__table__,
            escalation.Escalation.__table__,
            notification.Notification.__table__,
            reminder_log.ReminderLog.__table__,
            # Required for signup / set-password email flow if alembic not applied
            EmailVerificationOTP.__table__,
        ]
        
        Base.metadata.create_all(bind=engine, tables=tables_to_create)
        print("[OK] Database tables checked/created successfully")
    except Exception as e:
        print(f"Note: Could not create tables automatically: {e}")
        print("You may need to run migrations or create tables manually.")
        print("Run: python -m backend.scripts.create_new_tables")

    fu = (settings.FRONTEND_URL or "").lower()
    if fu and "localhost" in fu and settings.ENVIRONMENT.lower() == "production":
        print(
            "[WARN] FRONTEND_URL points to localhost while ENVIRONMENT=production; "
            "set FRONTEND_URL to your live site (e.g. https://www.erepairing.com) so email links work."
        )

    if settings.OEM_WARRANTY_SYNC_ENABLED:
        run_main = os.environ.get("RUN_MAIN")
        # Dev (--reload): only the reloader child should start the loop (matches prior behavior).
        # Prod (multi-worker): flock so only one worker runs OEM sync.
        start_oem = (settings.DEBUG and run_main == "true") or (
            not settings.DEBUG and try_acquire_oem_sync_leader_lock()
        )
        if start_oem:
            asyncio.create_task(start_oem_sync_loop())

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Trusted hosts
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.ALLOWED_HOSTS,
)

# Static uploads
uploads_dir = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(uploads_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")

# Include API routes
app.include_router(api_router, prefix="/api/v1")


@app.get("/")
def root():
    return {
        "message": "eRepairing.com API",
        "version": "1.0.0",
        "status": "operational"
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/health/ready")
def health_ready():
    """For load balancers: confirms the process can reach the database (runs in a thread pool)."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ready", "database": "ok"}
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "database": "unavailable"},
        )


