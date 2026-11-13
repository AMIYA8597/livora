Write-Host "🚀 Setting up Flatmate Platform Development Environment (Windows)..." -ForegroundColor Cyan

# 1. Check .env
if (-not (Test-Path ".env")) {
    Write-Host "📄 Creating .env from .env.example..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
}

# 2. Node Dependencies
Write-Host "📦 Installing Node dependencies via pnpm..." -ForegroundColor Yellow
pnpm install

# 3. Python Virtualenv
Write-Host "🐍 Setting up Python virtual environment..." -ForegroundColor Yellow
Set-Location "apps\api"
if (-not (Test-Path ".venv")) {
    python -m venv .venv
}
& ".\.venv\Scripts\Activate.ps1"
pip install --upgrade pip
pip install -e ".[dev]"
Set-Location "..\.."

# 4. Docker containers
Write-Host "🐳 Starting local database and cache containers..." -ForegroundColor Yellow
docker compose up -d postgres redis minio

Write-Host "🌱 Waiting 5 seconds for database readiness..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

& ".\scripts\seed_db.ps1"

Write-Host "🎉 Setup complete! Run 'pnpm dev' to start local development." -ForegroundColor Green
