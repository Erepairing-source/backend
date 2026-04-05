"""
Background OEM warranty sync job
"""
import asyncio
import logging
import os
from datetime import datetime

from app.core.config import settings

logger = logging.getLogger(__name__)

_oem_leader_fp = None


def try_acquire_oem_sync_leader_lock() -> bool:
    """
    With multiple Uvicorn workers, only one process should run the OEM sync loop.
    Without this, each worker starts identical background jobs (extra DB/API load).
    Uses non-blocking flock on POSIX. On Windows (no fcntl), returns True.
    """
    global _oem_leader_fp
    try:
        import fcntl
    except ImportError:
        return True

    lock_path = os.environ.get("OEM_SYNC_LOCK_PATH", "/tmp/erepairing_oem_sync.lock")
    fp = None
    try:
        fp = open(lock_path, "a+")
        fcntl.flock(fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        fp.seek(0)
        fp.truncate()
        fp.write(f"{os.getpid()}\n")
        fp.flush()
        _oem_leader_fp = fp
        logger.info("OEM warranty sync: this worker holds the leader lock")
        return True
    except BlockingIOError:
        if fp is not None:
            fp.close()
        logger.info("OEM warranty sync: another worker is leader; skipping background loop here")
        return False
    except OSError as e:
        if fp is not None:
            fp.close()
        logger.warning("OEM warranty sync: leader lock failed (%s); starting loop in this worker", e)
        return True
from app.core.database import SessionLocal
from app.models.integration import Integration, IntegrationType
from app.models.device import Device
from app.models.warranty import Warranty, WarrantyStatus
from app.services.oem_warranty import OEMWarrantyService


def run_sync_cycle_blocking():
    """Runs OEM warranty sync using sync DB + HTTP (safe for asyncio.to_thread)."""
    service = OEMWarrantyService()
    db = SessionLocal()
    try:
        integrations = db.query(Integration).filter(
            Integration.integration_type == IntegrationType.API,
            Integration.is_active == True
        ).all()
        for integration in integrations:
            config = integration.config or {}
            enabled = config.get("oem_sync_enabled", settings.OEM_WARRANTY_SYNC_ENABLED)
            interval_min = int(config.get("oem_sync_interval_minutes", settings.OEM_WARRANTY_SYNC_INTERVAL_MINUTES))
            batch_size = int(config.get("oem_sync_batch_size", settings.OEM_WARRANTY_SYNC_BATCH_SIZE))

            if not enabled:
                continue
            if integration.last_sync_at:
                elapsed = (datetime.utcnow() - integration.last_sync_at).total_seconds() / 60
                if elapsed < interval_min:
                    continue

            devices = db.query(Device).filter(
                Device.organization_id == integration.organization_id
            ).limit(batch_size).all()

            synced = 0
            failed = 0
            for device in devices:
                try:
                    result = service.fetch_warranty_sync(integration, device.serial_number)
                    if result.get("error"):
                        failed += 1
                        continue
                    start_date = datetime.fromisoformat(result["start_date"])
                    end_date = datetime.fromisoformat(result["end_date"])
                    existing = db.query(Warranty).filter(
                        Warranty.device_id == device.id,
                        Warranty.status == WarrantyStatus.ACTIVE
                    ).first()
                    if existing:
                        existing.warranty_type = result.get("warranty_type")
                        existing.start_date = start_date
                        existing.end_date = end_date
                        existing.covered_parts = result.get("covered_parts", [])
                        existing.covered_services = result.get("covered_services", [])
                        existing.warranty_number = result.get("warranty_number")
                    else:
                        db.add(Warranty(
                            device_id=device.id,
                            organization_id=device.organization_id,
                            warranty_type=result.get("warranty_type"),
                            start_date=start_date,
                            end_date=end_date,
                            covered_parts=result.get("covered_parts", []),
                            covered_services=result.get("covered_services", []),
                            warranty_number=result.get("warranty_number"),
                            status=WarrantyStatus.ACTIVE
                        ))
                    synced += 1
                except Exception:
                    failed += 1
                    continue
            integration.last_sync_at = datetime.utcnow()
            config["last_sync_stats"] = {
                "synced": synced,
                "failed": failed,
                "total": len(devices),
                "ran_at": integration.last_sync_at.isoformat()
            }
            integration.config = config
        db.commit()
    finally:
        db.close()


async def start_oem_sync_loop():
    """Run sync in a worker thread so sync SQLAlchemy + HTTP never block API requests."""
    while True:
        try:
            await asyncio.to_thread(run_sync_cycle_blocking)
        except Exception:
            logger.exception("OEM warranty sync cycle failed")
        await asyncio.sleep(max(5, settings.OEM_WARRANTY_SYNC_INTERVAL_MINUTES) * 60)
