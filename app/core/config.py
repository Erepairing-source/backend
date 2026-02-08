"""
Application configuration
"""
from pydantic_settings import BaseSettings
from typing import List, Optional


class Settings(BaseSettings):
    # App
    PROJECT_NAME: str = "eRepairing.com"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    
    # Database
    DATABASE_URL: str = "mysql+pymysql://root:Ak18070406%40@localhost:3306/erepairingnew?charset=utf8mb4"
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:3001"]
    ALLOWED_HOSTS: List[str] = ["localhost", "127.0.0.1", "*.erepairing.com"]
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # AWS S3 (for file storage)
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: str = "ap-south-1"
    S3_BUCKET_NAME: str = "erepairing-uploads"
    
    # Twilio (SMS/WhatsApp)
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_PHONE_NUMBER: Optional[str] = None

    # Maps
    MAPBOX_ACCESS_TOKEN: Optional[str] = None
    GOOGLE_MAPS_API_KEY: Optional[str] = None
    MAPS_PROVIDER: str = "mapbox"  # mapbox or google

    # OEM Warranty Sync
    OEM_WARRANTY_SYNC_ENABLED: bool = False
    OEM_WARRANTY_SYNC_INTERVAL_MINUTES: int = 1440
    OEM_WARRANTY_SYNC_BATCH_SIZE: int = 200
    
    # OpenAI (for AI features)
    OPENAI_API_KEY: Optional[str] = None
    
    # AI Model Paths
    AI_MODELS_DIR: str = "./models"
    
    # Email
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM_EMAIL: str = "noreply@erepairing.com"
    
    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

