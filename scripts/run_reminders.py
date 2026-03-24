#!/usr/bin/env python3
"""
Run contract renewal + service visit reminder emails once.
Schedule daily (e.g. cron 8:00 UTC):

    cd backend && python scripts/run_reminders.py

Requires DATABASE_URL and SMTP_* in .env for emails to send.
"""
import os
import sys

# Run from backend/ so `app` imports resolve
_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from app.core.database import SessionLocal  # noqa: E402
from app.services.reminders import run_all_reminders  # noqa: E402


def main() -> None:
    db = SessionLocal()
    try:
        result = run_all_reminders(db)
        print(result)
    finally:
        db.close()


if __name__ == "__main__":
    main()
