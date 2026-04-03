"""
Hierarchy-based approval for starting a ticket.
Engineer accepts → approval request created (city level); city admin approves → engineer can start.
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class TicketStartApproval(Base):
    """Approval request for starting service (hierarchy: city → state → country)."""
    __tablename__ = "ticket_start_approvals"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True)
    requested_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    approval_level = Column(String(20), nullable=False, default="city")  # city | state | country
    status = Column(String(20), nullable=False, default="pending", index=True)  # pending | approved | rejected
    approved_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    ticket = relationship("Ticket", backref="start_approvals")
    requested_by = relationship("User", foreign_keys=[requested_by_id])
    approved_by = relationship("User", foreign_keys=[approved_by_id])
