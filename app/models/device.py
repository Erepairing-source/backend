"""
Device models
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Device(Base):
    """Device model"""
    __tablename__ = "devices"
    
    id = Column(Integer, primary_key=True, index=True)
    serial_number = Column(String(100), unique=True, index=True, nullable=False)
    model_number = Column(String(100), nullable=False, index=True)
    product_category = Column(String(100), nullable=False, index=True)  # AC, Washing Machine, TV, etc.
    brand = Column(String(100), nullable=False, index=True)
    
    # Product relationships
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    product_model_id = Column(Integer, ForeignKey("product_models.id"), nullable=True)
    
    # Customer
    customer_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)  # OEM
    
    # Purchase details
    purchase_date = Column(DateTime(timezone=True), nullable=True)
    invoice_number = Column(String(100), nullable=True)
    invoice_photo = Column(Text, nullable=True)  # URL
    
    # Device info
    device_photo = Column(Text, nullable=True)  # URL
    qr_code = Column(String(255), nullable=True, unique=True, index=True)
    additional_info = Column(JSON, default=dict)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    customer = relationship("User", backref="devices")
    organization = relationship("Organization")
    product = relationship("Product", back_populates="devices")
    product_model = relationship("ProductModel", back_populates="devices")
    registrations = relationship("DeviceRegistration", back_populates="device")
    tickets = relationship("Ticket", back_populates="device")
    warranties = relationship("Warranty", back_populates="device")
    
    def __repr__(self):
        return f"<Device {self.serial_number} ({self.brand} {self.model_number})>"


class DeviceRegistration(Base):
    """Device registration history"""
    __tablename__ = "device_registrations"
    
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False)
    registration_method = Column(String(50), nullable=False)  # serial, qr, invoice
    registration_data = Column(JSON, default=dict)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    device = relationship("Device", back_populates="registrations")


