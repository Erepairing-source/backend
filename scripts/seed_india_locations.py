"""
Seed India: 1 country (India, code IN), 35 states/UTs, and all cities (UP has 75+).
Uses single source of truth from app.data.india_locations.

Run from backend directory (with DATABASE_URL set and migrations applied):
    python scripts/seed_india_locations.py

Idempotent: existing country/states/cities are skipped.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.location import Country, State, City
from app.data.india_locations import INDIA_STATES, INDIA_CITIES_BY_STATE


def seed_india_locations(db: Session) -> None:
    """Create India (code IN), all 35 states, and all cities. Idempotent."""
    india = db.query(Country).filter(Country.code == "IN").first()
    if not india:
        india = Country(name="India", code="IN")
        db.add(india)
        db.commit()
        db.refresh(india)
        print("[OK] Created country: India (IN)")
    else:
        print("[OK] Country already exists: India (IN)")

    for s in INDIA_STATES:
        state_name = s["name"]
        state_code = s.get("code") or ""
        state = (
            db.query(State)
            .filter(State.name == state_name, State.country_id == india.id)
            .first()
        )
        if not state:
            state = State(name=state_name, code=state_code, country_id=india.id)
            db.add(state)
            db.commit()
            db.refresh(state)
            print(f"  [OK] Created state: {state_name} ({state_code})")
        else:
            print(f"  [OK] State already exists: {state_name}")

        cities = INDIA_CITIES_BY_STATE.get(state_name, [])
        for city_name in cities:
            existing = (
                db.query(City)
                .filter(City.name == city_name, City.state_id == state.id)
                .first()
            )
            if not existing:
                city = City(name=city_name, state_id=state.id)
                db.add(city)
                db.commit()
            # Don't print every city to avoid spam; summary at end
        print(f"    -> {len(cities)} cities for {state_name}")

    # Summary
    total_states = db.query(State).filter(State.country_id == india.id).count()
    total_cities = (
        db.query(City)
        .join(State, City.state_id == State.id)
        .filter(State.country_id == india.id)
        .count()
    )
    up_state = db.query(State).filter(State.country_id == india.id, State.code == "UP").first()
    up_cities = db.query(City).filter(City.state_id == up_state.id).count() if up_state else 0
    print("=" * 50)
    print(f"India: {total_states} states, {total_cities} cities (Uttar Pradesh: {up_cities} cities)")
    print("=" * 50)


def main():
    db = SessionLocal()
    try:
        seed_india_locations(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
