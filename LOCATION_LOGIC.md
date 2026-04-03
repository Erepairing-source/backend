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

**Single source of truth for India:** `app/data/india_locations.py` (35 states, all cities; UP 75+). All India location logic uses this module.

**To populate the DB (recommended):**

- Run from the **backend** directory (set `DATABASE_URL` for AWS RDS):
  - `python scripts/seed_india_locations.py` – India only (country IN, 35 states, all cities).
  - `python scripts/seed_all.py` – Full seed (India + plans + platform admin + org admin + subscription).
- These scripts use `app.data.india_locations`. After running, Country Admin and State Admin see full state/city data from the DB.

---

## 5. Locations API vs Admin Dashboards

- **`/api/v1/locations/`** (countries, states, cities): **India** data comes from `app.data.india_locations` (static in code); if DB is seeded, API returns from DB first. No external India API.
- **Country Admin** uses `INDIA_STATES_FULL` from `app.data.india_locations` for India state count/list; state/city metrics come from the DB.
- **State Admin** uses `INDIA_CITIES_BY_STATE` from `app.data.india_locations` for India city list when state is India; metrics come from the DB.
- Run `seed_india_locations.py` or `seed_all.py` to populate the DB so admins and signup have real IDs.
