# Email reminders

## Contract renewal

- **Who:** Active organization subscriptions (`subscriptions.status = active`).
- **When:** Emails go to all **organization admins** on days **30, 14, 7, and 1** before `end_date` (UTC calendar day).
- **Deduping:** One email per subscription per window (e.g. `30d`) stored in `reminder_logs`.

## Service visit

- **Who:** Customers on open tickets (`created`, `assigned`, `in_progress`, `waiting_parts`, `escalated`).
- **When:** **The day before** (UTC):
  - `follow_up_preferred_date` falls on tomorrow, or
  - `engineer_eta_start` falls on tomorrow.
- **Deduping:** One email per ticket per type/day bucket in `reminder_logs`.

## Requirements

- Configure **SMTP** in `.env` (same as other transactional email).
- Set **`FRONTEND_URL`** so dashboard and ticket links work.

## How to run (daily)

**Option A – CLI**

```bash
cd backend
python scripts/run_reminders.py
```

**Option B – HTTP (cron / Hostinger)**

1. Set `REMINDER_JOB_SECRET` in `.env` (long random string).
2. Daily request:

```bash
curl -X POST "https://your-api.com/api/v1/jobs/reminders/run" \
  -H "X-Reminder-Secret: YOUR_SECRET"
```

**Option C – Platform admin**

`POST /api/v1/jobs/reminders/run-as-admin` with a platform-admin Bearer token (same as other admin APIs).

## Database

Apply migration:

```bash
cd backend && alembic upgrade head
```

Or rely on app startup table creation for `reminder_logs` if you use `create_all` for that table.
