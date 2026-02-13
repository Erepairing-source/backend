# Run full seed (roles, locations, plans, platform admin, org admin, subscription) for AWS RDS (PostgreSQL). Not for local MySQL.
# Usage: $env:DATABASE_URL = "postgresql://user:pass@your-rds-host:5432/dbname"; .\scripts\run_seed_all_for_aws.ps1
param()
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..
if (-not $env:DATABASE_URL) {
    Write-Error "Set DATABASE_URL to your AWS RDS PostgreSQL URL"
    exit 1
}
Write-Host "Seeding all data on AWS (roles, locations, plans, users, subscription)..."
python scripts/seed_all.py
Write-Host "Done."
