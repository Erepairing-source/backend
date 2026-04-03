"""
Inventory models
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum, Text, Float, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.core.database import Base


class Part(Base):
    """Part/SKU model"""
    __tablename__ = "parts"
    
    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String(100), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Product mapping
    applicable_products = Column(JSON, default=list)  # Array of product categories/models
    compatible_models = Column(JSON, default=list)  # Specific model numbers
    
    # Pricing
    cost_price = Column(Float, nullable=True)
    selling_price = Column(Float, nullable=True)
    
    # Unit
    unit = Column(String(20), default="piece")
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    inventory_items = relationship("Inventory", back_populates="part")
    transactions = relationship("InventoryTransaction", back_populates="part")
    reorder_requests = relationship("ReorderRequest", back_populates="part")
    
    def __repr__(self):
        return f"<Part {self.sku} - {self.name}>"


class Inventory(Base):
    """Inventory stock levels"""
    __tablename__ = "inventory"
    
    id = Column(Integer, primary_key=True, index=True)
    part_id = Column(Integer, ForeignKey("parts.id"), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    
    # Location
    country_id = Column(Integer, ForeignKey("countries.id"), nullable=True)
    state_id = Column(Integer, ForeignKey("states.id"), nullable=True, index=True)
    city_id = Column(Integer, ForeignKey("cities.id"), nullable=True, index=True)
    warehouse_name = Column(String(255), nullable=True)
    
    # Stock levels
    current_stock = Column(Integer, default=0, nullable=False)
    min_threshold = Column(Integer, default=0, nullable=False)
    max_threshold = Column(Integer, nullable=True)
    reserved_stock = Column(Integer, default=0)  # Reserved for pending tickets
    
    # Status
    is_low_stock = Column(Boolean, default=False, index=True)
    last_restocked_at = Column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    part = relationship("Part", back_populates="inventory_items")
    organization = relationship("Organization")
    country = relationship("Country")
    state = relationship("State")
    city = relationship("City")
    
    def __repr__(self):
        return f"<Inventory {self.part.sku} - Stock: {self.current_stock}>"


class InventoryTransaction(Base):
    """Inventory transaction log"""
    __tablename__ = "inventory_transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    part_id = Column(Integer, ForeignKey("parts.id"), nullable=False, index=True)
    inventory_id = Column(Integer, ForeignKey("inventory.id"), nullable=False)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=True)
    
    transaction_type = Column(String(50), nullable=False)  # in, out, adjustment, return
    quantity = Column(Integer, nullable=False)
    previous_stock = Column(Integer, nullable=False)
    new_stock = Column(Integer, nullable=False)
    
    performed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Relationships
    part = relationship("Part", back_populates="transactions")
    inventory = relationship("Inventory")
    ticket = relationship("Ticket")
    performed_by = relationship("User")


class ReorderRequest(Base):
    """Reorder request for low stock"""
    __tablename__ = "reorder_requests"
    
    id = Column(Integer, primary_key=True, index=True)
    part_id = Column(Integer, ForeignKey("parts.id"), nullable=False, index=True)
    inventory_id = Column(Integer, ForeignKey("inventory.id"), nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    
    requested_quantity = Column(Integer, nullable=False)
    current_stock = Column(Integer, nullable=False)
    min_threshold = Column(Integer, nullable=False)
    
    # Approval workflow
    status = Column(String(50), default="pending", index=True)  # pending, approved, rejected, fulfilled
    requested_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    part = relationship("Part", back_populates="reorder_requests")
    inventory = relationship("Inventory")
    organization = relationship("Organization")
    requested_by = relationship("User", foreign_keys=[requested_by_id])
    approved_by = relationship("User", foreign_keys=[approved_by_id])




