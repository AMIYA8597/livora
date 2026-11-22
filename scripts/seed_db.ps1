# Apply the Alembic schema, then load idempotent development seed data.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Push-Location (Join-Path $root "apps/api")
try {
    Write-Host "Applying migrations (alembic upgrade head)..." -ForegroundColor Cyan
    python -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw "alembic upgrade failed" }
    Write-Host "Seeding development data..." -ForegroundColor Cyan
    python (Join-Path $root "database/seeds/seed.py") @args
    if ($LASTEXITCODE -ne 0) { throw "seed failed" }
} finally {
    Pop-Location
}
