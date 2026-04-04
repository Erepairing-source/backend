"""
Resolve Country / State / City IDs from numeric IDs and/or API-style names and codes.
Used when the frontend uses static location lists (id=null) but the DB needs FK integers.
"""
from typing import Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.location import Country, State, City


def _strip(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    t = str(s).strip()
    return t or None


def materialize_user_location_ids(
    db: Session,
    *,
    country_id: Optional[int] = None,
    country_code: Optional[str] = None,
    state_id: Optional[int] = None,
    state_name: Optional[str] = None,
    state_code: Optional[str] = None,
    city_id: Optional[int] = None,
    city_name: Optional[str] = None,
) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    """
    Returns (country_id, state_id, city_id) with missing rows created when possible.
    """
    cid = country_id
    cc = _strip(country_code)
    if not cid and cc:
        row = db.query(Country).filter(func.upper(Country.code) == cc.upper()).first()
        if row:
            cid = row.id

    sid = state_id
    ctid = city_id
    sn = _strip(state_name)
    sc = _strip(state_code)
    cn = _strip(city_name)

    if ctid:
        city = db.query(City).filter(City.id == ctid).first()
        if city:
            st = db.query(State).filter(State.id == city.state_id).first()
            co_id = st.country_id if st else cid
            return co_id, st.id if st else sid, city.id

    if cid and not sid and (sn or sc):
        q = db.query(State).filter(State.country_id == cid)
        if sc:
            hit = q.filter(func.upper(State.code) == sc.upper()).first()
            if hit:
                sid = hit.id
        if not sid and sn:
            hit = q.filter(func.lower(State.name) == sn.lower()).first()
            if hit:
                sid = hit.id
            else:
                new_st = State(name=sn, code=sc, country_id=cid)
                db.add(new_st)
                db.flush()
                sid = new_st.id

    if sid and not ctid and cn:
        hit = (
            db.query(City)
            .filter(City.state_id == sid, func.lower(City.name) == cn.lower())
            .first()
        )
        if hit:
            ctid = hit.id
        else:
            new_c = City(name=cn, state_id=sid)
            db.add(new_c)
            db.flush()
            ctid = new_c.id

    return cid, sid, ctid


def int_or_none(value) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def resolve_location_ids(db: Session, data: dict) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    """Resolve (country_id, state_id, city_id) from dict keys used by inventory and org admin APIs."""
    return materialize_user_location_ids(
        db,
        country_id=int_or_none(data.get("country_id")),
        country_code=data.get("country_code"),
        state_id=int_or_none(data.get("state_id")),
        state_name=data.get("state_name"),
        state_code=data.get("state_code"),
        city_id=int_or_none(data.get("city_id")),
        city_name=data.get("city_name"),
    )
