"""
Comprehensive script to ensure ALL database tables exist
This script creates any missing tables and verifies all models are registered
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import inspect, create_engine
from app.core.database import Base, engine
from app.core.config import settings

# Import ALL models to ensure they're registered with SQLAlchemy
from app.models.user import User
from app.models.organization import Organization, OrganizationHierarchy
from app.models.ticket import Ticket, TicketComment
from app.models.device import Device, DeviceRegistration
from app.models.inventory import Part, Inventory, InventoryTransaction, ReorderRequest
from app.models.warranty import Warranty, WarrantyClaim
from app.models.ai_models import AITriageResult, AIPrediction, SentimentAnalysis
from app.models.subscription import Subscription, Plan, PlanFeature, Vendor, VendorOrganization
from app.models.location import Country, State, City
from app.models.platform_settings import PlatformSettings
from app.models.product import Product, ProductModel
from app.models.product_part import ProductPart
from app.models.sla_policy import SLAPolicy, ServicePolicy
from app.models.escalation import Escalation
from app.models.integration import Integration
from app.models.notification import Notification

def get_all_tables():
    """Get list of all expected tables from models"""
    return {
        'users': User,
        'organizations': Organization,
        'organization_hierarchies': OrganizationHierarchy,
        'tickets': Ticket,
        'ticket_comments': TicketComment,
        'devices': Device,
        'device_registrations': DeviceRegistration,
        'parts': Part,
        'inventory': Inventory,
        'inventory_transactions': InventoryTransaction,
        'reorder_requests': ReorderRequest,
        'warranties': Warranty,
        'warranty_claims': WarrantyClaim,
        'ai_triage_results': AITriageResult,
        'ai_predictions': AIPrediction,
        'sentiment_analyses': SentimentAnalysis,
        'subscriptions': Subscription,
        'plans': Plan,
        'plan_features': PlanFeature,
        'vendors': Vendor,
        'vendor_organizations': VendorOrganization,
        'countries': Country,
        'states': State,
        'cities': City,
        'platform_settings': PlatformSettings,
        'products': Product,
        'product_models': ProductModel,
        'product_parts': ProductPart,
        'sla_policies': SLAPolicy,
        'service_policies': ServicePolicy,
        'escalations': Escalation,
        'integrations': Integration,
        'notifications': Notification,
    }

def ensure_all_tables():
    """Create all missing tables"""
    print("=" * 60)
    print("Ensuring ALL database tables exist...")
    print("=" * 60)
    
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    
    all_tables = get_all_tables()
    created_tables = []
    skipped_tables = []
    errors = []
    
    for table_name, model_class in all_tables.items():
        if table_name in existing_tables:
            skipped_tables.append(table_name)
            print(f"[SKIP] Table already exists: {table_name}")
        else:
            try:
                model_class.__table__.create(bind=engine, checkfirst=True)
                created_tables.append(table_name)
                print(f"[OK] Created table: {table_name}")
            except Exception as e:
                error_msg = f"Error creating table {table_name}: {e}"
                errors.append(error_msg)
                print(f"[ERROR] {error_msg}")
    
    # Also create all tables using Base metadata (for any missed relationships)
    try:
        Base.metadata.create_all(bind=engine, checkfirst=True)
        print("[OK] Verified all tables via Base.metadata")
    except Exception as e:
        print(f"[WARNING] Base.metadata.create_all had issues: {e}")
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total tables expected: {len(all_tables)}")
    print(f"Created: {len(created_tables)} tables")
    print(f"Already existed: {len(skipped_tables)} tables")
    print(f"Errors: {len(errors)}")
    
    if created_tables:
        print(f"\n[OK] Created tables:")
        for table in created_tables:
            print(f"   - {table}")
    
    if skipped_tables:
        print(f"\n[OK] Existing tables ({len(skipped_tables)}):")
        for table in sorted(skipped_tables):
            print(f"   - {table}")
    
    if errors:
        print(f"\n[ERROR] Errors:")
        for error in errors:
            print(f"   - {error}")
    
    # Verify final state
    inspector = inspect(engine)
    final_tables = set(inspector.get_table_names())
    missing_tables = set(all_tables.keys()) - final_tables
    
    if missing_tables:
        print(f"\n[WARNING] {len(missing_tables)} tables are still missing:")
        for table in missing_tables:
            print(f"   - {table}")
        return False
    else:
        print(f"\n[SUCCESS] All {len(all_tables)} tables exist in database!")
        return True

if __name__ == "__main__":
    try:
        success = ensure_all_tables()
        if success:
            print("\n" + "=" * 60)
            print("[SUCCESS] ALL TABLES VERIFIED - DATABASE IS READY!")
            print("=" * 60)
        else:
            print("\n" + "=" * 60)
            print("[WARNING] SOME TABLES ARE MISSING - CHECK ERRORS ABOVE")
            print("=" * 60)
            sys.exit(1)
    except Exception as e:
        print(f"\n[FATAL ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

