"""
Populate database with real India location data from india_states_cities.json.
No API key required. Use this so Country Admin and State Admin see real state/city names from DB.

Usage (from backend directory):
    set PYTHONPATH=%CD%
    python scripts/populate_locations_from_json.py

Or:
    cd backend && python scripts/populate_locations_from_json.py
"""
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.models.location import Country, State, City

# Path to JSON (in app/data)
JSON_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "app", "data", "india_states_cities.json"
)


def main():
    if not os.path.exists(JSON_PATH):
        print(f"ERROR: JSON not found: {JSON_PATH}")
        sys.exit(1)

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    states_data = data.get("states") or []
    if not states_data:
        print("ERROR: No 'states' key in JSON")
        sys.exit(1)

    db = SessionLocal()
    try:
        # Ensure India exists
        india = db.query(Country).filter(Country.code == "IND").first()
        if not india:
            india = db.query(Country).filter(Country.name == "India").first()
        if not india:
            india = Country(name="India", code="IND")
            db.add(india)
            db.commit()
            db.refresh(india)
            print("[OK] Created country: India (IND)")
        else:
            print("[OK] Country India already exists")

        states_added = 0
        cities_added = 0

        for s in states_data:
            state_name = (s.get("name") or "").strip()
            state_code = (s.get("code") or "").strip() or None
            districts = s.get("districts") or []

            if not state_name:
                continue

            state = db.query(State).filter(
                State.country_id == india.id,
                State.name == state_name
            ).first()

            if not state:
                state = State(
                    name=state_name,
                    code=state_code,
                    country_id=india.id
                )
                db.add(state)
                db.commit()
                db.refresh(state)
                states_added += 1
                print(f"  [OK] State: {state_name}")

            # Use districts as "cities" so State Admin sees real locations
            for dist_name in districts:
                if not dist_name or not isinstance(dist_name, str):
                    continue
                dist_name = dist_name.strip()
                if not dist_name:
                    continue
                existing = db.query(City).filter(
                    City.state_id == state.id,
                    City.name == dist_name
                ).first()
                if not existing:
                    city = City(name=dist_name, state_id=state.id)
                    db.add(city)
                    cities_added += 1

            if districts:
                db.commit()

        print()
        print(f"[OK] States added: {states_added} (total states in DB for India: {db.query(State).filter(State.country_id == india.id).count()})")
        print(f"[OK] Cities (districts) added: {cities_added} (total cities: {db.query(City).join(State).filter(State.country_id == india.id).count()})")
        print()
        print("Country Admin and State Admin will now see real state and city (district) names from DB.")
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    main()
