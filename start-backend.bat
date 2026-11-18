@echo off
title DYPCOE Campus Navigator - Backend
cd /d %~dp0backend
call venv\Scripts\activate.bat
echo.
echo ========================================
echo  DYPCOE Smart Campus Navigator - Backend
echo  http://localhost:8000
echo  API Docs: http://localhost:8000/api/docs
echo ========================================
echo.
venv\Scripts\uvicorn.exe main:app --reload --port 8000
