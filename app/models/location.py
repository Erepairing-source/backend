"""
Location models (Country, State, City)
"""
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Country(Base):
    """Country model"""
    __tablename__ = "countries"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True, index=True)
    code = Column(String(3), nullable=False, unique=True)  # ISO code
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    states = relationship("State", back_populates="country")
    users = relationship("User", back_populates="country")
    organizations = relationship("Organization", back_populates="country")


class State(Base):
    """State model"""
    __tablename__ = "states"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    code = Column(String(10), nullable=True)
    country_id = Column(Integer, ForeignKey("countries.id"), nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    country = relationship("Country", back_populates="states")
    cities = relationship("City", back_populates="state")
    users = relationship("User", back_populates="state")
    organizations = relationship("Organization", back_populates="state")


class City(Base):
    """City model"""
    __tablename__ = "cities"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    state_id = Column(Integer, ForeignKey("states.id"), nullable=False)
    latitude = Column(String(20), nullable=True)
    longitude = Column(String(20), nullable=True)
    hq_latitude = Column(String(20), nullable=True)
    hq_longitude = Column(String(20), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    state = relationship("State", back_populates="cities")
    users = relationship("User", back_populates="city")
    organizations = relationship("Organization", back_populates="city")




