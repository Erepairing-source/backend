"""
Resolve location from id or code/name so signup, inventory, and user flows
all use the same locations API and DB. Used when API returns id: null (e.g. India static).
"""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.location import Country, State, City
from app.data.india_locations import INDIA_STATES, INDIA_CITIES_BY_STATE, state_code_to_name


def int_or_none(v):
    if v is None:
        return None
    try:
        n = int(v)
        return n if n else None
    except (TypeError, ValueError):
        return None


def resolve_country_id(db: Session, data: dict) -> int:
    """Resolve country_id from data (country_id or country_code)."""
    cid = int_or_none(data.get("country_id"))
    if cid:
        country = db.query(Country).filter(Country.id == cid).first()
        if country:
            return country.id
    code = (data.get("country_code") or "").strip().upper() or None
    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing location: provide country_id or country_code (e.g. IN)"
        )
    country = db.query(Country).filter(Country.code == code).first()
    if country:
        return country.id
    if code == "IN":
        country = db.query(Country).filter(Country.name == "India").first()
        if country:
            return country.id
        country = db.query(Country).filter(Country.code == "IN").first()
        if country:
            return country.id
        country = Country(name="India", code="IN")
        db.add(country)
        db.flush()
        return country.id
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Country not found for code: {code}. Only India (IN) can be auto-created."
    )


def resolve_state_id(db: Session, data: dict, country_id: int) -> int:
    """Resolve state_id from data (state_id or state_code or state_name)."""
    sid = int_or_none(data.get("state_id"))
    if sid:
        state = db.query(State).filter(State.id == sid, State.country_id == country_id).first()
        if state:
            return state.id
    code = (data.get("state_code") or "").strip().upper() or None
    name = (data.get("state_name") or "").strip() or None
    if not code and not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing location: provide state_id or state_code/state_name"
        )
    if code and not name:
        name = state_code_to_name(code)
    if name:
        state = db.query(State).filter(State.country_id == country_id).filter(
            (State.name == name) | (State.code == (code or name))
        ).first()
        if state:
            return state.id
        # Avoid duplicate: state may exist by name with different/missing code
        state = db.query(State).filter(State.country_id == country_id, State.name == name).first()
        if state:
            return state.id
        for s in INDIA_STATES:
            if (s.get("name") == name) or ((s.get("code") or "").upper() == (code or "")):
                state = State(name=s["name"], code=s.get("code"), country_id=country_id)
                db.add(state)
                db.flush()
                return state.id
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="State not found for given state_code/state_name"
    )


def resolve_city_id(db: Session, data: dict, state_id: int) -> int:
    """Resolve city_id from data (city_id or city_name)."""
    cid = int_or_none(data.get("city_id"))
    if cid:
        city = db.query(City).filter(City.id == cid, City.state_id == state_id).first()
        if city:
            return city.id
    name = (data.get("city_name") or "").strip() or None
    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing location: provide city_id or city_name"
        )
    city = db.query(City).filter(City.state_id == state_id, City.name == name).first()
    if city:
        return city.id
    state = db.query(State).filter(State.id == state_id).first()
    if state:
        # Avoid duplicate: city may exist under another state row (same country)
        city = db.query(City).join(State).filter(State.country_id == state.country_id, City.name == name).first()
        if city:
            return city.id
        if state.name and state.name in INDIA_CITIES_BY_STATE and name in INDIA_CITIES_BY_STATE[state.name]:
            city = City(name=name, state_id=state_id)
            db.add(city)
            db.flush()
            return city.id
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="City not found for given city_name"
    )


def resolve_location_ids(db: Session, data: dict) -> tuple:
    """Resolve (country_id, state_id, city_id) from data (ids or code/name). Returns (int, int, int)."""
    country_id = resolve_country_id(db, data)
    state_id = resolve_state_id(db, data, country_id)
    city_id = resolve_city_id(db, data, state_id)
    return country_id, state_id, city_id
