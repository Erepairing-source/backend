"""
Database initialization script
Creates initial data: countries, states, cities, default plans, platform admin
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy.orm import Session
from app.core.database import SessionLocal, engine, Base
from app.core.security import get_password_hash
from app.models.user import User, UserRole
from app.models.location import Country, State, City
from app.models.subscription import Plan, PlanType
from app.models.organization import Organization, OrganizationType

# Create all tables
Base.metadata.create_all(bind=engine)

db = SessionLocal()


def init_countries_states_cities():
    """Initialize India location data"""
    # Create India
    india = db.query(Country).filter(Country.code == "IND").first()
    if not india:
        india = Country(name="India", code="IND")
        db.add(india)
        db.commit()
        db.refresh(india)
        print("[OK] Created India")
    else:
        print("[OK] India already exists")
    
    # Major Indian states
    states_data = [
        ("Maharashtra", "MH", ["Mumbai", "Pune", "Nagpur", "Nashik"]),
        ("Tamil Nadu", "TN", ["Chennai", "Coimbatore", "Madurai"]),
        ("Gujarat", "GJ", ["Ahmedabad", "Surat", "Vadodara"]),
        ("Karnataka", "KA", ["Bengaluru", "Mysuru", "Mangaluru"]),
        ("Delhi", "DL", ["New Delhi"]),
        ("Uttar Pradesh", "UP", ["Lucknow", "Kanpur", "Agra"]),
        ("Rajasthan", "RJ", ["Jaipur", "Jodhpur", "Udaipur"]),
        ("Uttarakhand", "UK", ["Dehradun", "Baddi"]),
    ]
    
    for state_name, state_code, cities in states_data:
        state = db.query(State).filter(
            State.name == state_name,
            State.country_id == india.id
        ).first()
        
        if not state:
            state = State(name=state_name, code=state_code, country_id=india.id)
            db.add(state)
            db.commit()
            db.refresh(state)
            print(f"  [OK] Created state: {state_name}")
        
        # Create cities
        for city_name in cities:
            city = db.query(City).filter(
                City.name == city_name,
                City.state_id == state.id
            ).first()
            
            if not city:
                city = City(name=city_name, state_id=state.id)
                db.add(city)
                db.commit()
                print(f"    [OK] Created city: {city_name}")


def init_plans():
    """Initialize subscription plans"""
    plans_data = [
        {
            "name": "Starter",
            "plan_type": PlanType.STARTER,
            "monthly_price": 20000.0 / 12,  # ₹20,000/year = monthly equivalent
            "annual_price": 20000.0,
            "max_engineers": 2,
            "features": {
                "ai_triage": False,
                "demand_forecasting": False,
                "copilot": False,
                "multilingual_chatbot": True,
                "advanced_analytics": False
            },
            "description": "Perfect for small manufacturers"
        },
        {
            "name": "Growth",
            "plan_type": PlanType.GROWTH,
            "monthly_price": 200000.0 / 12,
            "annual_price": 200000.0,
            "max_engineers": 10,
            "features": {
                "ai_triage": True,
                "demand_forecasting": True,
                "copilot": True,
                "multilingual_chatbot": True,
                "advanced_analytics": False
            },
            "description": "For growing service networks"
        },
        {
            "name": "Enterprise",
            "plan_type": PlanType.ENTERPRISE,
            "monthly_price": 1000000.0 / 12,
            "annual_price": 1000000.0,
            "max_engineers": None,  # Unlimited
            "features": {
                "ai_triage": True,
                "demand_forecasting": True,
                "copilot": True,
                "multilingual_chatbot": True,
                "advanced_analytics": True,
                "api_access": True,
                "iot_integration": True,
                "sla_guarantees": True
            },
            "description": "Full-featured solution for large enterprises"
        }
    ]
    
    for plan_data in plans_data:
        plan = db.query(Plan).filter(Plan.name == plan_data["name"]).first()
        
        if not plan:
            plan = Plan(**plan_data)
            db.add(plan)
            db.commit()
            print(f"[OK] Created plan: {plan_data['name']}")
        else:
            print(f"[OK] Plan already exists: {plan_data['name']}")


def init_platform_admin():
    """Create default platform admin user"""
    admin = db.query(User).filter(User.email == "admin@erepairing.com").first()
    
    if not admin:
        admin = User(
            email="admin@erepairing.com",
            phone="+911234567890",
            password_hash=get_password_hash("admin123"),  # Change in production!
            full_name="Platform Administrator",
            role=UserRole.PLATFORM_ADMIN,
            is_active=True,
            is_verified=True
        )
        db.add(admin)
        db.commit()
        print("[OK] Created platform admin (admin@erepairing.com / admin123)")
    else:
        print("[OK] Platform admin already exists")
        print("[INFO] Existing admin password will NOT be overwritten")
        print("[INFO] To reset password, use: python scripts/verify_and_fix_password.py")


def main():
    """Run all initialization"""
    print("Initializing database...")
    print()
    
    init_countries_states_cities()
    print()
    init_plans()
    print()
    init_platform_admin()
    print()
    
    print("[OK] Database initialization complete!")
    print()
    print("Default credentials:")
    print("  Email: admin@erepairing.com")
    print("  Password: admin123")
    print()
    print("[WARNING] IMPORTANT: Change default password in production!")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()
