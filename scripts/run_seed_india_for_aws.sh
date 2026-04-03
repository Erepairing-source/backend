#!/bin/bash
# Run India locations seed for AWS RDS (PostgreSQL). Not for local MySQL.
# Usage: DATABASE_URL="postgresql://user:pass@your-rds-host:5432/dbname" ./scripts/run_seed_india_for_aws.sh
set -e
cd "$(dirname "$0")/.."
if [ -z "$DATABASE_URL" ]; then
  echo "Error: set DATABASE_URL to your AWS RDS PostgreSQL URL"
  exit 1
fi
echo "Seeding India locations on AWS (35 states, all cities, UP 75+)..."
python scripts/seed_india_locations.py
echo "Done."
