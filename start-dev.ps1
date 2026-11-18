# DYPCOE Smart Campus Navigator — PowerShell Dev Startup
# Run: .\start-dev.ps1

$root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  DYPCOE Smart Campus Navigator — Development Startup" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[1/2] Starting Backend (FastAPI on port 8000)..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$root\backend'; .\venv\Scripts\uvicorn main:app --reload --port 8000"

Start-Sleep -Seconds 2

Write-Host "[2/2] Starting Frontend (Vite on port 5173)..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$root\frontend'; npm run dev"

Write-Host ""
Write-Host "Both servers starting in separate windows." -ForegroundColor Yellow
Write-Host ""
Write-Host "  Backend:  http://localhost:8000" -ForegroundColor White
Write-Host "  API Docs: http://localhost:8000/api/docs" -ForegroundColor White
Write-Host "  Frontend: http://localhost:5173" -ForegroundColor White
Write-Host "  Admin:    http://localhost:5173/admin/login" -ForegroundColor White
Write-Host "            Email: admin@dypcoe.ac.in / Password: dypcoe@2024" -ForegroundColor Gray
