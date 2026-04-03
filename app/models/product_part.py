"""
Product-Part relationship model
This creates a proper many-to-many relationship between Products and Parts
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class ProductPart(Base):
    """Many-to-many relationship between Products and Parts"""
    __tablename__ = "product_parts"
    
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    part_id = Column(Integer, ForeignKey("parts.id"), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    
    # Relationship details
    is_required = Column(Boolean, default=False)  # Is this part required for this product?
    is_common = Column(Boolean, default=True)  # Is this a commonly used part for this product?
    usage_frequency = Column(String(50), default="occasional")  # frequent, occasional, rare
    notes = Column(Text, nullable=True)  # Additional notes about this relationship
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    product = relationship("Product", backref="product_parts")
    part = relationship("Part", backref="part_products")
    organization = relationship("Organization")
    
    def __repr__(self):
        return f"<ProductPart Product:{self.product_id} Part:{self.part_id}>"



