# India locations on AWS – same behaviour everywhere

Locations use **one source of truth** (`app.data.india_locations`): **35 states** and **all cities** (Uttar Pradesh has **75+**). Seeds are for **AWS (RDS)**, not local/MySQL.

## 1. Run the seed on your AWS database (RDS, PostgreSQL)

After migrations are applied on your AWS DB (`alembic upgrade head`), run the seed **against your RDS** (PostgreSQL):

```bash
cd backend
# Set DATABASE_URL to your AWS RDS PostgreSQL connection string
export DATABASE_URL="postgresql://user:pass@your-rds-host:5432/yourdb"
python scripts/seed_all.py
```

This seeds: roles (reference), India + 35 states + all cities, plans, platform admin, org admin, demo subscription. Idempotent.

From a shell script (set DATABASE_URL first):

```bash
./scripts/run_seed_all_for_aws.sh    # full seed
./scripts/run_seed_india_for_aws.sh   # India locations only
```

India-only (locations only, no users):

```bash
python scripts/seed_india_locations.py
```

Result:

- **Country**: India (code `IN`)
- **35 states/UTs** with codes (e.g. UP, MH, DL)
- **All cities** per state (UP has 76)

Idempotent: safe to run again; existing rows are skipped.

## 2. Point frontend to your AWS API

Set the API base URL so all location calls hit your backend:

- **Build time**: `NEXT_PUBLIC_API_URL=https://your-api-domain.com/api/v1` before `npm run build`
- **Runtime**: in `frontend/public/config.js` set  
  `window.__API_BASE__ = 'https://your-api-domain.com/api/v1'`

All location flows use the same backend:

- **Signup** – `/locations/countries?india_only=true`, then states/cities
- **Get started** – `/locations/countries`, states, cities
- **Platform admin (users)** – countries, states, cities
- **Organization admin (dashboard)** – countries, India states (`/locations/india/states`), India cities (`/locations/india/states/{state}/cities`), or generic states/cities

No external India APIs: data comes from **static** (`app.data.india_locations`) or from the **DB** after seed.

## 3. Without running the seed

If you don’t run the seed:

- **Countries** with `?india_only=true`: API still returns India from static (so signup works).
- **States/cities**: API returns static data (35 states, all cities, UP 75+).
- You won’t have DB IDs for country/state/city until you run the seed.

For full behaviour (IDs, consistency with other features), run the seed on AWS as in step 1.
