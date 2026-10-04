@echo off
rem Development mode: API with auto-reload on :8000 + Vite dev server on :5173
cd /d "%~dp0"
start "Ad Spy Engine API" cmd /k ".venv\Scripts\python.exe backend\run.py --reload --no-browser"
cd frontend
call npm run dev -- --open
