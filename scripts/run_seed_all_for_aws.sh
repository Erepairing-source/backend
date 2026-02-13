#!/bin/bash
# Run full seed (roles, locations, plans, platform admin, org admin, subscription) for AWS RDS (PostgreSQL). Not for local MySQL.
# Usage: DATABASE_URL="postgresql://user:pass@your-rds-host:5432/dbname" ./scripts/run_seed_all_for_aws.sh
set -e
cd "$(dirname "$0")/.."
if [ -z "$DATABASE_URL" ]; then
  echo "Error: set DATABASE_URL to your AWS RDS PostgreSQL URL"
  exit 1
fi
echo "Seeding all data on AWS (roles, locations, plans, users, subscription)..."
python scripts/seed_all.py
echo "Done."
