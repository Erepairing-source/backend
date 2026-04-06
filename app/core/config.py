"""
Application configuration.
Production: set CORS_ORIGINS, ALLOWED_HOSTS, FRONTEND_URL (and DATABASE_URL, SECRET_KEY, SMTP_*) in .env.
"""
import json
import os
from pathlib import Path

from dotenv import dotenv_values
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import List, Optional, Union

_BACKEND_ENV = Path(__file__).resolve().parent.parent.parent / ".env"


def _parse_list(value: Union[str, List[str]]) -> List[str]:
    """
    Parse env list for CORS_ORIGINS / ALLOWED_HOSTS.
    Accepts:
    - JSON array: ["https://a.com","https://b.com"]
    - Comma-separated: https://a.com,https://b.com
    """
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return []
        if s.startswith("["):
            try:
                parsed = json.loads(s)
                if isinstance(parsed, list):
                    return [str(x).strip() for x in parsed if str(x).strip()]
            except json.JSONDecodeError:
                pass
        return [x.strip() for x in s.split(",") if x.strip()]
    return []


def _apply_backend_dotenv() -> None:
    """
    Load backend/.env into os.environ so SMTP works regardless of process cwd.
    CORS_ORIGINS / ALLOWED_HOSTS: JSON arrays or comma-separated lists (see _parse_list).
    """
    if not _BACKEND_ENV.is_file():
        return
    values = dotenv_values(_BACKEND_ENV, encoding="utf-8-sig")
    for k, v in values.items():
        if v is None:
            continue
        if k == "CORS_ORIGINS":
            os.environ[k] = json.dumps(_parse_list(v))
        elif k == "ALLOWED_HOSTS":
            os.environ[k] = json.dumps(_parse_list(v))
        else:
            os.environ[k] = v


_apply_backend_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # os.environ is filled by load_dotenv(_BACKEND_ENV) above
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # App
    PROJECT_NAME: str = "eRepairing.com"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Security (change SECRET_KEY in production)
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    
    # Database (set DATABASE_URL in production to your AWS RDS or MySQL URL)
    DATABASE_URL: str = "mysql+pymysql://root:Ak18070406%40@localhost:3306/erepairingnew?charset=utf8mb4"
    
    # CORS: production set comma-separated, e.g. CORS_ORIGINS=https://yourapp.com,https://www.yourapp.com
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000", "http://localhost:3001", "http://localhost:3002",
        "http://localhost:3003", "http://localhost:3004", "http://127.0.0.1:3000",
        "http://127.0.0.1:3001", "http://127.0.0.1:3002", "http://127.0.0.1:3003", "http://127.0.0.1:3004"
    ]
    # ALLOWED_HOSTS: production set comma-separated, e.g. ALLOWED_HOSTS=yourapp.com,api.yourapp.com
    ALLOWED_HOSTS: List[str] = ["localhost", "127.0.0.1", "*.erepairing.com", "testserver"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def cors_origins_list(cls, v):
        if v is None:
            return [
                "http://localhost:3000", "http://localhost:3001", "http://localhost:3002",
                "http://localhost:3003", "http://localhost:3004",
                "http://127.0.0.1:3000", "http://127.0.0.1:3001", "http://127.0.0.1:3002",
                "http://127.0.0.1:3003", "http://127.0.0.1:3004"
            ]
        return _parse_list(v)

    @field_validator("ALLOWED_HOSTS", mode="before")
    @classmethod
    def allowed_hosts_list(cls, v):
        if v is None:
            return ["localhost", "127.0.0.1", "*.erepairing.com", "testserver"]
        return _parse_list(v)
    
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
    # mapbox | google | osm — osm uses free Nominatim; mapbox/google fall back to Nominatim if keys are missing
    MAPS_PROVIDER: str = "mapbox"
    # Required by Nominatim usage policy: identify your application (URL or contact email)
    NOMINATIM_USER_AGENT: str = "eRepairing/1.0 (https://www.erepairing.com)"

    # OEM Warranty Sync
    OEM_WARRANTY_SYNC_ENABLED: bool = False
    OEM_WARRANTY_SYNC_INTERVAL_MINUTES: int = 1440
    OEM_WARRANTY_SYNC_BATCH_SIZE: int = 200
    
    # OpenAI (for AI features)
    OPENAI_API_KEY: Optional[str] = None
    # Google Gemini (role assistant + chatbot when set; preferred over Groq/OpenAI for those)
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-2.0-flash"
    # Free-tier LLM option (Groq). Used by role assistant when Gemini/OpenAI unavailable.
    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL: str = "llama-3.1-8b-instant"
    
    # AI Model Paths
    AI_MODELS_DIR: str = "./models"
    
    # Email
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM_EMAIL: str = "noreply@erepairing.com"
    SMTP_FROM_NAME: str = "eRepairing"
    SMTP_REPLY_TO: Optional[str] = None
    # Port 465 (Hostinger): set SMTP_USE_SSL=true and SMTP_USE_TLS=false
    SMTP_USE_SSL: bool = False
    SMTP_USE_TLS: bool = True

    # Production: set to your live site (e.g. https://www.erepairing.com) — all email links use this (set-password, verify, login).
    FRONTEND_URL: str = "http://localhost:3000"
    SET_PASSWORD_TOKEN_EXPIRE_HOURS: int = 24

    # Daily reminder job: POST /api/v1/jobs/reminders/run with header X-Reminder-Secret
    REMINDER_JOB_SECRET: Optional[str] = None
    
    # Environment (set ENVIRONMENT=production and DEBUG=false in production)
    ENVIRONMENT: str = "development"
    DEBUG: bool = True


settings = Settings()


def frontend_base_url() -> str:
    """Public web app origin with no trailing slash. Used for links in emails (set-password, verify-email, login)."""
    u = (settings.FRONTEND_URL or "").strip().rstrip("/")
    return u if u else "http://localhost:3000"

