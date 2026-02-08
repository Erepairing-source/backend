"""
Script to populate database with comprehensive location data from CountryStateCity API
Run this script to populate your database with all countries, states, and cities

Usage:
    python -m scripts.populate_locations_from_api

Requirements:
    - Set COUNTRY_STATE_CITY_API_KEY environment variable
    - Or get free API key from: https://countrystatecity.in/
"""
import os
import sys
import asyncio
import httpx
from sqlalchemy.orm import Session

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal, engine
from app.models.location import Country, State, City, Base

# Create tables if they don't exist
Base.metadata.create_all(bind=engine)

COUNTRY_STATE_CITY_API_KEY = os.getenv("COUNTRY_STATE_CITY_API_KEY", "")
COUNTRY_STATE_CITY_BASE_URL = "https://api.countrystatecity.in/v1"

if not COUNTRY_STATE_CITY_API_KEY:
    print("⚠️  WARNING: COUNTRY_STATE_CITY_API_KEY not set!")
    print("   Get a free API key from: https://countrystatecity.in/")
    print("   Then set it as environment variable: export COUNTRY_STATE_CITY_API_KEY=your_key")
    print("\n   Continuing with limited functionality...")


async def fetch_data(url: str, headers: dict = None):
    """Fetch data from API"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                print(f"❌ API Authentication failed. Check your API key.")
                return None
            else:
                print(f"❌ API Error: {response.status_code} - {response.text}")
                return None
    except Exception as e:
        print(f"❌ Error fetching data: {str(e)}")
        return None


def populate_countries(db: Session):
    """Populate countries from API"""
    if not COUNTRY_STATE_CITY_API_KEY:
        print("⏭️  Skipping countries (no API key)")
        return
    
    print("🌍 Fetching countries from API...")
    headers = {"X-CSCAPI-KEY": COUNTRY_STATE_CITY_API_KEY}
    url = f"{COUNTRY_STATE_CITY_BASE_URL}/countries"
    
    async def fetch():
        return await fetch_data(url, headers)
    
    countries_data = asyncio.run(fetch())
    
    if not countries_data:
        print("❌ Failed to fetch countries")
        return
    
    print(f"📥 Found {len(countries_data)} countries")
    
    added = 0
    updated = 0
    
    for country_data in countries_data:
        country_name = country_data.get("name", "").strip()
        country_code = country_data.get("iso2", "").strip().upper()
        
        if not country_name or not country_code:
            continue
        
        # Check if country exists
        existing = db.query(Country).filter(
            (Country.code == country_code) | (Country.name == country_name)
        ).first()
        
        if existing:
            # Update if needed
            if existing.code != country_code:
                existing.code = country_code
                updated += 1
        else:
            # Create new
            country = Country(
                name=country_name,
                code=country_code
            )
            db.add(country)
            added += 1
    
    db.commit()
    print(f"✅ Countries: {added} added, {updated} updated")


def populate_states_for_country(db: Session, country_code: str, country_id: int):
    """Populate states for a specific country"""
    if not COUNTRY_STATE_CITY_API_KEY:
        return []
    
    headers = {"X-CSCAPI-KEY": COUNTRY_STATE_CITY_API_KEY}
    url = f"{COUNTRY_STATE_CITY_BASE_URL}/countries/{country_code}/states"
    
    async def fetch():
        return await fetch_data(url, headers)
    
    states_data = asyncio.run(fetch())
    
    if not states_data:
        return []
    
    state_ids = []
    for state_data in states_data:
        state_name = state_data.get("name", "").strip()
        state_code = state_data.get("iso2", "").strip().upper()
        
        if not state_name:
            continue
        
        # Check if state exists
        existing = db.query(State).filter(
            State.country_id == country_id,
            State.name == state_name
        ).first()
        
        if existing:
            if state_code and existing.code != state_code:
                existing.code = state_code
                db.commit()
            state_ids.append(existing.id)
        else:
            state = State(
                name=state_name,
                code=state_code if state_code else None,
                country_id=country_id
            )
            db.add(state)
            db.commit()
            db.refresh(state)
            state_ids.append(state.id)
    
    return state_ids


def populate_cities_for_state(db: Session, country_code: str, state_code: str, state_id: int):
    """Populate cities for a specific state"""
    if not COUNTRY_STATE_CITY_API_KEY:
        return
    
    headers = {"X-CSCAPI-KEY": COUNTRY_STATE_CITY_API_KEY}
    url = f"{COUNTRY_STATE_CITY_BASE_URL}/countries/{country_code}/states/{state_code}/cities"
    
    async def fetch():
        return await fetch_data(url, headers)
    
    cities_data = asyncio.run(fetch())
    
    if not cities_data:
        return
    
    added = 0
    for city_data in cities_data:
        city_name = city_data.get("name", "").strip()
        latitude = city_data.get("latitude", "")
        longitude = city_data.get("longitude", "")
        
        if not city_name:
            continue
        
        # Check if city exists
        existing = db.query(City).filter(
            City.state_id == state_id,
            City.name == city_name
        ).first()
        
        if not existing:
            city = City(
                name=city_name,
                state_id=state_id,
                latitude=str(latitude) if latitude else None,
                longitude=str(longitude) if longitude else None
            )
            db.add(city)
            added += 1
    
    if added > 0:
        db.commit()
        return added
    return 0


def main():
    """Main function to populate all location data"""
    db = SessionLocal()
    
    try:
        print("🚀 Starting location data population...")
        print("=" * 60)
        
        # Step 1: Populate countries
        populate_countries(db)
        
        # Step 2: Populate states for each country
        print("\n🗺️  Fetching states...")
        countries = db.query(Country).all()
        total_states = 0
        
        for country in countries:
            states_data = populate_states_for_country(db, country.code, country.id)
            total_states += len(states_data)
            if len(states_data) > 0:
                print(f"   ✓ {country.name}: {len(states_data)} states")
        
        print(f"✅ Total states: {total_states}")
        
        # Step 3: Populate cities for each state (this might take a while)
        print("\n🏙️  Fetching cities (this may take several minutes)...")
        states = db.query(State).join(Country).all()
        total_cities = 0
        processed = 0
        
        for state in states:
            cities_added = populate_cities_for_state(
                db, 
                state.country.code, 
                state.code or "", 
                state.id
            )
            total_cities += cities_added
            processed += 1
            
            if processed % 10 == 0:
                print(f"   Progress: {processed}/{len(states)} states processed, {total_cities} cities added...")
        
        print(f"✅ Total cities added: {total_cities}")
        
        print("\n" + "=" * 60)
        print("✨ Location data population completed!")
        print(f"   Countries: {len(countries)}")
        print(f"   States: {total_states}")
        print(f"   Cities: {total_cities}")
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    main()



