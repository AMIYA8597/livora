Write-Host "🌱 Running Flatmate Platform Database Migrations & Seeds (Windows)..." -ForegroundColor Cyan

Set-Location "database\seeds"
python seed.py
Set-Location "..\.."

Write-Host "✅ Database seeded successfully." -ForegroundColor Green
