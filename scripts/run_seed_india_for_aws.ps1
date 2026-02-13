# Run India locations seed for AWS RDS (PostgreSQL). Not for local MySQL.
# Usage: $env:DATABASE_URL = "postgresql://user:pass@your-rds-host:5432/dbname"; .\scripts\run_seed_india_for_aws.ps1
param()
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..
if (-not $env:DATABASE_URL) {
    Write-Error "Set DATABASE_URL to your AWS RDS PostgreSQL URL"
    exit 1
}
Write-Host "Seeding India locations on AWS (35 states, all cities, UP 75+)..."
python scripts/seed_india_locations.py
Write-Host "Done."
