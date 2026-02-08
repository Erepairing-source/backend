"""
Platform Settings model
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON, Float
from sqlalchemy.sql import func

from app.core.database import Base


class PlatformSettings(Base):
    """Platform-wide settings and configuration"""
    __tablename__ = "platform_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    setting_key = Column(String(100), unique=True, nullable=False, index=True)
    setting_value = Column(Text, nullable=True)  # JSON string or plain text
    setting_type = Column(String(50), nullable=False, default="string")  # string, number, boolean, json
    category = Column(String(50), nullable=False, index=True)  # general, billing, security, notifications, features, integrations
    description = Column(Text, nullable=True)
    is_public = Column(Boolean, default=False)  # Can be accessed without auth
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<PlatformSettings {self.setting_key}={self.setting_value}>"



