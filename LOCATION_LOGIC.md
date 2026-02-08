# Country Admin & State Admin – Where State and City Names Come From

## Summary

- **All state names and city names** shown to Country Admin and State Admin **come from the database** only: tables `countries`, `states`, `cities`.
- There is **no** fallback to external APIs or static lists in the **admin** dashboards. If the DB has no rows (or only a few), admins will see empty or limited lists.

---

## 1. Country Admin – States in a Country

**Logic:** States for the logged-in country admin are loaded from the **`states`** table, filtered by the admin’s `country_id`.

**Code (country_admin.py):**

- Dashboard and states list:
  - `states = db.query(State).filter(State.country_id == current_user.country_id).all()`
- Each state’s **name** is `state.name` from the DB.
- Cities under that country are loaded from **`cities`**:
  - `cities = db.query(City).filter(City.state_id.in_(state_ids)).all()`
- City names come from `cities.name` in the DB.

So:

- **State names in country** = from `states` where `country_id = current_user.country_id`.
- **City names (for metrics)** = from `cities` where `state_id` is in that country’s states.

---

## 2. State Admin – Cities in a State

**Logic:** Cities for the logged-in state admin are loaded from the **`cities`** table, filtered by the admin’s `state_id`.

**Code (state_admin.py):**

- Dashboard and cities list:
  - `cities = db.query(City).filter(City.state_id == current_user.state_id).all()`
- Each city **name** is `city.name` from the DB.

So:

- **City names in state** = from `cities` where `state_id = current_user.state_id`.

---

## 3. Data Flow (DB only for admin views)

```
User (country_id / state_id)
    ↓
Country Admin → states = State.filter(country_id=user.country_id)   → state names from DB
             → cities = City.filter(state_id.in_(state_ids))         → city names from DB

State Admin   → cities = City.filter(state_id=user.state_id)         → city names from DB
```

No external API or in-memory list is used for these admin dropdowns/lists; they are 100% from the DB.

---

## 4. How to Get “Real” State and City Names in the DB

The **admin** side does not call the locations API or static data; it only reads from the DB. So to show real state/city names you must **populate** `countries`, `states`, and `cities` first.

**Option A – From local JSON (no API key)**

- Use the script that loads **India** states and districts from `app/data/india_states_cities.json` and inserts them into `countries`, `states`, and `cities` (districts are stored as cities).
- Run from the **backend** directory:
  - `python scripts/populate_locations_from_json.py`
- After this, Country Admin will see all Indian states and State Admin will see all districts (as cities) for their state.

**Option B – From external API**

- Use `scripts/populate_locations_from_api.py` with `COUNTRY_STATE_CITY_API_KEY` set.
- This fills the same tables from the CountryStateCity API so admins again see real data from the DB.

**Option C – Initial seed only**

- `scripts/init_db.py` creates India and a **small** set of states/cities (e.g. a few major cities per state). Good for a minimal seed; for full coverage use Option A or B.

---

## 5. Locations API vs Admin Dashboards

- **`/api/v1/locations/`** (countries, states, cities) can return data from **external APIs or static lists** (e.g. for signup/forms). That is separate from the admin logic.
- **Country Admin** and **State Admin** dashboards **do not** use that API; they only use the DB. So:
  - Real state names in country = must be in `states`.
  - Real city names in state = must be in `cities`.
  - Run one of the populate scripts above to get real data into the DB.
