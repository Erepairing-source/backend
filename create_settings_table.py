"""
Script to create platform_settings table
Run this once to initialize the settings table
"""
from app.core.database import Base, engine
from app.models.platform_settings import PlatformSettings

if __name__ == "__main__":
    print("Creating platform_settings table...")
    Base.metadata.create_all(bind=engine, tables=[PlatformSettings.__table__])
    print("Table created successfully!")
    print("\nYou can now use the /api/v1/platform-admin/settings/initialize endpoint to populate default settings.")

