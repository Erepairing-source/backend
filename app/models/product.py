"""
Product Catalog models
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum, Text, Float, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.core.database import Base


class ProductCategory(str, enum.Enum):
    """Product categories"""
    AC = "ac"
    REFRIGERATOR = "refrigerator"
    WASHING_MACHINE = "washing_machine"
    TV = "tv"
    MICROWAVE = "microwave"
    AIR_PURIFIER = "air_purifier"
    WATER_PURIFIER = "water_purifier"
    OTHER = "other"


class Product(Base):
    """Product master - e.g., 'Split AC 1.5T'"""
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    
    # Product details
    name = Column(String(255), nullable=False)  # e.g., "Split AC 1.5T"
    category = Column(Enum(ProductCategory), nullable=False, index=True)
    brand = Column(String(100), nullable=True)
    
    # Description
    description = Column(Text, nullable=True)
    specifications = Column(JSON, default=dict)  # Technical specs
    
    # Warranty defaults
    default_warranty_months = Column(Integer, default=12)
    extended_warranty_available = Column(Boolean, default=False)
    
    # Common failure patterns (for AI)
    common_failures = Column(JSON, default=list)  # Array of common issues
    recommended_parts = Column(JSON, default=list)  # Array of part IDs
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    organization = relationship("Organization", back_populates="products")
    models = relationship("ProductModel", back_populates="product", cascade="all, delete-orphan")
    devices = relationship("Device", back_populates="product")
    
    def __repr__(self):
        return f"<Product {self.name} ({self.category})>"


class ProductModel(Base):
    """Specific product model - e.g., 'CoolAir Split AC 1.5T Model XYZ-123'"""
    __tablename__ = "product_models"
    
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    
    # Model details
    model_number = Column(String(100), nullable=False, index=True)  # e.g., "XYZ-123"
    model_name = Column(String(255), nullable=True)
    
    # Compatibility
    compatible_parts = Column(JSON, default=list)  # Array of part IDs
    service_instructions = Column(Text, nullable=True)  # OEM-specific instructions
    
    # AI Copilot data
    diagnostic_playbook = Column(JSON, default=dict)  # Step-by-step diagnostic guide
    error_code_mappings = Column(JSON, default=dict)  # Error codes -> solutions
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    product = relationship("Product", back_populates="models")
    organization = relationship("Organization")
    devices = relationship("Device", back_populates="product_model")
    
    def __repr__(self):
        return f"<ProductModel {self.model_number}>"



