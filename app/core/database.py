"""
Database configuration and session management
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# Avoid hanging forever on dead RDS/network: TCP connect timeout (pymysql).
_engine_kw = dict(
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,  # Recycle connections after 1 hour
    pool_timeout=30,  # Fail fast if pool exhausted instead of waiting indefinitely
    echo=False,  # Set to True for SQL query logging
)
if "mysql" in settings.DATABASE_URL and "pymysql" in settings.DATABASE_URL:
    _engine_kw["connect_args"] = {"connect_timeout": 10}

engine = create_engine(settings.DATABASE_URL, **_engine_kw)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency for getting database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

