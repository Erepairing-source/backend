"""
Script to create new database tables for Product, SLA Policy, Integration, etc.
"""
from sqlalchemy import create_engine, inspect
from app.core.database import Base, engine
from app.core.config import settings

# Import all models to register them
from app.models.product import Product, ProductModel
from app.models.product_part import ProductPart
from app.models.sla_policy import SLAPolicy, ServicePolicy
from app.models.integration import Integration
from app.models.escalation import Escalation
from app.models.notification import Notification

def create_new_tables():
    """Create all new tables"""
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    
    tables_to_create = {
        'products': Product,
        'product_models': ProductModel,
        'product_parts': ProductPart,
        'sla_policies': SLAPolicy,
        'service_policies': ServicePolicy,
        'integrations': Integration,
        'escalations': Escalation,
        'notifications': Notification
    }
    
    created_tables = []
    skipped_tables = []
    
    for table_name, model_class in tables_to_create.items():
        if table_name not in existing_tables:
            try:
                model_class.__table__.create(bind=engine, checkfirst=True)
                created_tables.append(table_name)
                print(f"[OK] Created table: {table_name}")
            except Exception as e:
                print(f"[ERROR] Error creating table {table_name}: {e}")
        else:
            skipped_tables.append(table_name)
            print(f"[SKIP] Table already exists: {table_name}")
    
    print(f"\nSummary:")
    print(f"  Created: {len(created_tables)} tables")
    print(f"  Skipped: {len(skipped_tables)} tables")
    
    if created_tables:
        print(f"\nCreated tables: {', '.join(created_tables)}")
    if skipped_tables:
        print(f"Existing tables: {', '.join(skipped_tables)}")

if __name__ == "__main__":
    print("Creating new database tables...")
    print("=" * 50)
    create_new_tables()
    print("=" * 50)
    print("Done!")

