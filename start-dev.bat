@echo off
echo ============================================================
echo   DYPCOE Smart Campus Navigator — Development Startup
echo ============================================================
echo.

echo [1/2] Starting Backend (FastAPI on port 8000)...
start "DYPCOE Backend" cmd /k "cd /d %~dp0backend && venv\Scripts\uvicorn main:app --reload --port 8000"

echo [2/2] Starting Frontend (Vite on port 5173)...
start "DYPCOE Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo Both servers are starting in separate windows.
echo.
echo   Backend:  http://localhost:8000
echo   API Docs: http://localhost:8000/api/docs
echo   Frontend: http://localhost:5173
echo   Admin:    http://localhost:5173/admin/login
echo             Email: admin@dypcoe.ac.in / Password: dypcoe@2024
echo.
echo Press any key to exit this launcher...
pause > nul
