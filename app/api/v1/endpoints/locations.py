"""
Location endpoints (Countries, States, Cities).
India: single source of truth from app.data.india_locations (35 states, all cities; UP 75+).
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import httpx
import os

from app.core.database import get_db
from app.models.location import Country, State, City
from app.data.india_locations import (
    INDIA_STATES,
    state_code_to_name,
    get_cities_for_state,
)

router = APIRouter()

# API configurations (for non-India countries only)
COUNTRY_STATE_CITY_API_KEY = os.getenv("COUNTRY_STATE_CITY_API_KEY", "")
COUNTRY_STATE_CITY_BASE_URL = "https://api.countrystatecity.in/v1"


async def fetch_from_api(url: str, headers: dict = None, timeout: float = 10.0):
    """Fetch data from any API (used for non-India countries)."""
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                return None
            return None
    except Exception:
        return None


@router.get("/countries", response_model=List[dict])
async def list_countries(
    use_api: bool = Query(False, description="Use external API if available"),
    india_only: bool = Query(False, description="Return only India (for signup/India-only flows); works with or without DB seed"),
    db: Session = Depends(get_db)
):
    """List all countries. india_only=True returns only India (from DB if seeded, else static) for AWS/signup."""
    # India-only: same behaviour on AWS and local; no external API
    if india_only:
        india = db.query(Country).filter(Country.code == "IN").first()
        if india:
            return [{"id": india.id, "name": india.name, "code": india.code, "from_api": False}]
        return [{"id": None, "name": "India", "code": "IN", "from_api": True, "api_source": "static"}]

    # Try API first if requested and API key is available
    if use_api and COUNTRY_STATE_CITY_API_KEY:
        headers = {"X-CSCAPI-KEY": COUNTRY_STATE_CITY_API_KEY}
        api_url = f"{COUNTRY_STATE_CITY_BASE_URL}/countries"
        api_data = await fetch_from_api(api_url, headers)
        if api_data:
            return [
                {
                    "id": None,
                    "name": country.get("name", ""),
                    "code": country.get("iso2", ""),
                    "iso3": country.get("iso3", ""),
                    "phone_code": country.get("phonecode", ""),
                    "currency": country.get("currency", ""),
                    "currency_symbol": country.get("currency_symbol", ""),
                    "region": country.get("region", ""),
                    "subregion": country.get("subregion", ""),
                    "latitude": country.get("latitude", ""),
                    "longitude": country.get("longitude", ""),
                    "emoji": country.get("emoji", ""),
                    "from_api": True
                }
                for country in api_data
            ]

    # Fallback to database
    countries = db.query(Country).order_by(Country.name).all()
    return [
        {"id": c.id, "name": c.name, "code": c.code, "from_api": False}
        for c in countries
    ]


@router.get("/states", response_model=List[dict])
async def list_states(
    country_id: Optional[int] = Query(None, description="Country ID from database"),
    country_code: Optional[str] = Query(None, description="Country ISO2 code (e.g., 'IN', 'US')"),
    use_api: bool = Query(True, description="Use external API if available"),
    db: Session = Depends(get_db)
):
    """List states for a country. India: app.data.india_locations (35 states); others: API or DB."""
    
    # Determine country code - prioritize code, but get from database if needed
    country_code_to_use = country_code
    country_name = None
    
    if not country_code_to_use and country_id:
        # Get country code from database
        country = db.query(Country).filter(Country.id == country_id).first()
        if country:
            country_code_to_use = country.code
            country_name = country.name
    
    is_india = False
    if country_code_to_use and str(country_code_to_use).upper() == "IN":
        is_india = True
    elif country_id:
        country = db.query(Country).filter(Country.id == country_id).first()
        if country and ((country.code and country.code.upper() == "IN") or (country.name and country.name.lower() == "india")):
            is_india = True
            country_code_to_use = "IN"
    
    # India: single source of truth from app.data.india_locations (35 states)
    if is_india:
        # Prefer DB if we have seeded states for India
        india = db.query(Country).filter(Country.code == "IN").first()
        if india:
            states_in_db = db.query(State).filter(State.country_id == india.id).order_by(State.name).all()
            if states_in_db:
                return [
                    {"id": s.id, "name": s.name, "code": s.code, "country_id": s.country_id, "country_code": "IN", "country_name": "India", "from_api": False}
                    for s in states_in_db
                ]
        return [
            {
                "id": None,
                "name": s.get("name", ""),
                "code": s.get("code", ""),
                "country_id": country_id,
                "country_code": "IN",
                "country_name": "India",
                "capital": s.get("capital", ""),
                "from_api": True,
                "api_source": "static",
            }
            for s in INDIA_STATES
        ]
    
    # Try CountryStateCity API for other countries
    if use_api and COUNTRY_STATE_CITY_API_KEY and country_code_to_use:
        headers = {"X-CSCAPI-KEY": COUNTRY_STATE_CITY_API_KEY}
        api_url = f"{COUNTRY_STATE_CITY_BASE_URL}/countries/{country_code_to_use}/states"
        api_data = await fetch_from_api(api_url, headers)
        
        if api_data:
            # Return comprehensive API data
            return [
                {
                    "id": None,
                    "name": state.get("name", ""),
                    "code": state.get("iso2", ""),
                    "country_id": country_id,
                    "country_code": country_code_to_use,
                    "latitude": state.get("latitude", ""),
                    "longitude": state.get("longitude", ""),
                    "type": state.get("type", ""),
                    "from_api": True,
                    "api_source": "countrystatecity"
                }
                for state in api_data
            ]
    
    # Fallback to database
    if not country_id:
        raise HTTPException(status_code=400, detail="Either country_id or country_code is required")
    
    states = db.query(State).filter(State.country_id == country_id).order_by(State.name).all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "code": s.code,
            "country_id": s.country_id,
            "from_api": False
        }
        for s in states
    ]


def _parse_state_id(state_id_raw: Optional[str]) -> tuple:
    """Parse state_id query: (int_id or None, name_or_code_str or None)."""
    if state_id_raw is None or (isinstance(state_id_raw, str) and state_id_raw.strip() in ("", "null")):
        return None, None
    s = str(state_id_raw).strip()
    try:
        return int(s), None
    except ValueError:
        return None, s


@router.get("/cities", response_model=List[dict])
async def list_cities(
    state_id: Optional[str] = Query(None, description="State ID (number) or state code/name for India"),
    country_code: Optional[str] = Query(None, description="Country ISO2 code"),
    state_code: Optional[str] = Query(None, description="State ISO2 code"),
    state_name: Optional[str] = Query(None, description="State name (for India)"),
    use_api: bool = Query(False, description="Use external API if available"),
    db: Session = Depends(get_db)
):
    """List cities for a state. India: app.data.india_locations (all cities; UP 75+); others: API or DB."""
    state_id_int, state_name_from_id = _parse_state_id(state_id)
    name_for_india = state_name or state_name_from_id

    if state_id_int is None and not name_for_india:
        return []

    # India: single source of truth from app.data.india_locations (all cities; UP 75+)
    if country_code and country_code.upper() == "IN":
        state_name_resolved = (state_code_to_name(name_for_india) if name_for_india else None) or name_for_india
        state_row = None
        india = db.query(Country).filter(Country.code == "IN").first()
        if india:
            if state_id_int is not None:
                state_row = db.query(State).filter(State.id == state_id_int, State.country_id == india.id).first()
            if state_row is None and state_name_resolved:
                state_row = db.query(State).filter(
                    State.country_id == india.id,
                    (State.name == state_name_resolved) | (State.code == (name_for_india or "").strip().upper()),
                ).first()
        if state_row:
            cities_in_db = db.query(City).filter(City.state_id == state_row.id).order_by(City.name).all()
            if cities_in_db:
                return [
                    {"id": c.id, "name": c.name, "state_id": c.state_id, "country_code": "IN", "state_code": state_row.code, "from_api": False}
                    for c in cities_in_db
                ]
        if not state_name_resolved and state_row:
            state_name_resolved = state_row.name
        if not state_name_resolved:
            return []
        static_cities = get_cities_for_state(state_name_resolved)
        return [
            {
                "id": None,
                "name": c.get("name", c.get("city", "")),
                "state_id": state_id_int,
                "country_code": "IN",
                "state_code": state_code,
                "state_name": state_name_resolved,
                "from_api": True,
                "api_source": "static",
            }
            for c in static_cities
        ]

    # Try CountryStateCity API for other countries
    if use_api and COUNTRY_STATE_CITY_API_KEY and country_code and state_code:
        headers = {"X-CSCAPI-KEY": COUNTRY_STATE_CITY_API_KEY}
        api_url = f"{COUNTRY_STATE_CITY_BASE_URL}/countries/{country_code}/states/{state_code}/cities"
        api_data = await fetch_from_api(api_url, headers)
        
        if api_data:
            return [
                {
                    "id": None,
                    "name": city.get("name", ""),
                    "state_id": state_id_int,
                    "country_code": country_code,
                    "state_code": state_code,
                    "latitude": city.get("latitude", ""),
                    "longitude": city.get("longitude", ""),
                    "from_api": True,
                    "api_source": "countrystatecity",
                }
                for city in api_data
            ]

    if state_id_int is not None:
        cities = db.query(City).filter(City.state_id == state_id_int).order_by(City.name).all()
        return [
            {"id": c.id, "name": c.name, "state_id": c.state_id, "latitude": c.latitude, "longitude": c.longitude, "from_api": False}
            for c in cities
        ]
    return []


@router.get("/countries/{country_code}/states", response_model=List[dict])
async def get_states_by_country_code(
    country_code: str,
    use_api: bool = Query(True, description="Use external API"),
    db: Session = Depends(get_db)
):
    """Get states by country ISO2 code - optimized for API usage"""
    return await list_states(country_code=country_code.upper(), use_api=use_api, db=db)


@router.get("/countries/{country_code}/states/{state_code}/cities", response_model=List[dict])
async def get_cities_by_state_code(
    country_code: str,
    state_code: str,
    state_name: Optional[str] = Query(None, description="State name (for India)"),
    use_api: bool = Query(True, description="Use external API"),
    db: Session = Depends(get_db)
):
    """Get cities by country and state ISO2 codes - optimized for API usage
    For India, can also use state_name for Bharat API
    """
    return await list_cities(
        country_code=country_code.upper(), 
        state_code=state_code.upper(),
        state_name=state_name,
        use_api=use_api, 
        db=db
    )


@router.get("/india/states", response_model=List[dict])
async def get_india_states(
    use_api: bool = Query(True, description="Use static data when True"),
    db: Session = Depends(get_db)
):
    """Get all Indian states (35). From DB if seeded, else from static."""
    india = db.query(Country).filter(Country.code == "IN").first()
    if india:
        states_in_db = db.query(State).filter(State.country_id == india.id).order_by(State.name).all()
        if states_in_db:
            return [
                {"id": s.id, "name": s.name, "code": s.code, "country_code": "IN", "country_id": s.country_id, "from_api": False}
                for s in states_in_db
            ]
    return [
        {"id": None, "name": s.get("name", ""), "code": s.get("code", ""), "country_code": "IN", "from_api": True, "api_source": "static"}
        for s in INDIA_STATES
    ]


@router.get("/india/states/{state_name}/cities", response_model=List[dict])
async def get_india_cities_by_state(
    state_name: str,
    use_api: bool = Query(True, description="Use static data when True"),
    db: Session = Depends(get_db)
):
    """Get cities for an Indian state. From DB if seeded, else from static (UP 75+)."""
    state_name_resolved = state_code_to_name(state_name) or state_name
    india = db.query(Country).filter(Country.code == "IN").first()
    if india:
        state_row = db.query(State).filter(
            State.country_id == india.id,
            (State.name == state_name_resolved) | (State.code == (state_name or "").strip().upper()),
        ).first()
        if state_row:
            cities_in_db = db.query(City).filter(City.state_id == state_row.id).order_by(City.name).all()
            if cities_in_db:
                return [{"id": c.id, "name": c.name, "state_name": state_name_resolved, "state_id": c.state_id, "from_api": False} for c in cities_in_db]
    static_cities = get_cities_for_state(state_name_resolved)
    return [
        {"id": None, "name": c.get("name", c.get("city", "")), "state_name": state_name_resolved, "from_api": True, "api_source": "static"}
        for c in static_cities
    ]
