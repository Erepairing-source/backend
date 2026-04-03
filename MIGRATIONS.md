# Database migrations (Alembic)

From the **`backend`** folder, use the Python module (works when `alembic` is not on PATH):

```powershell
cd C:\Project\eRepairingNew\backend
python -m alembic upgrade head
```

Other useful commands:

```powershell
python -m alembic current
python -m alembic history
```

Ensure `DATABASE_URL` in `backend/.env` (or defaults in `app/core/config.py`) points at the same MySQL database you use for the app.

**Note:** Migrations `d6e7` (email verification) and `f1a2` (reminder logs) skip creating tables if they already exist (e.g. created by app startup), so `upgrade head` can sync `alembic_version` safely.
