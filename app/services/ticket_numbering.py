"""
Human-readable ticket numbers: ER-YYYYMMDD-NNN (daily sequence, platform-wide).
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import func

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from app.models.ticket import Ticket


def allocate_er_ticket_number(db: "Session") -> str:
    """Next ER-YYYYMMDD-### for the current UTC day. Caller must commit with the new ticket row."""
    day = datetime.utcnow().strftime("%Y%m%d")
    prefix = f"ER-{day}-"
    max_num = (
        db.query(func.max(Ticket.ticket_number))
        .filter(Ticket.ticket_number.like(f"{prefix}%"))
        .scalar()
    )
    next_seq = 1
    if max_num and isinstance(max_num, str):
        try:
            next_seq = int(max_num.rsplit("-", 1)[-1]) + 1
        except ValueError:
            next_seq = 1
    candidate = f"{prefix}{next_seq:03d}"
    while db.query(Ticket.id).filter(Ticket.ticket_number == candidate).first():
        next_seq += 1
        candidate = f"{prefix}{next_seq:03d}"
    return candidate
