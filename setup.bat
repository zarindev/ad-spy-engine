@echo off
setlocal EnableDelayedExpansion
title Ad Spy Engine - setup
cd /d "%~dp0"
echo.
echo   Ad Spy Engine - one-time setup
echo   ==============================
echo.

rem --- Python 3.11+ ----------------------------------------------------------
set "PY="
where py >nul 2>nul && (py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul && set "PY=py -3")
if not defined PY (
  where python >nul 2>nul && (python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul && set "PY=python")
)
if not defined PY (
  echo [x] Python 3.11 or newer was not found. Install it from https://www.python.org/downloads/
  echo     and tick "Add python.exe to PATH" during installation.
  goto :fail
)
for /f "delims=" %%v in ('%PY% -c "import platform; print(platform.python_version())"') do echo [ok] Python %%v

rem --- Node 20+ --------------------------------------------------------------
where node >nul 2>nul || (echo [x] Node.js 20+ was not found. Install the LTS from https://nodejs.org/ & goto :fail)
for /f "delims=" %%v in ('node -v') do echo [ok] Node %%v

rem --- Google Chrome (warning only) ------------------------------------------
set "CHROME="
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "CHROME=1"
if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set "CHROME=1"
if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" set "CHROME=1"
if defined CHROME (echo [ok] Google Chrome found) else (echo [!] Google Chrome not found - install it from https://www.google.com/chrome/ before scanning)

rem --- Python environment ----------------------------------------------------
if not exist ".venv\Scripts\python.exe" (
  echo.
  echo Creating virtual environment...
  %PY% -m venv .venv || goto :fail
)
echo Installing Python packages (first run takes a minute)...
".venv\Scripts\python.exe" -m pip install --upgrade pip --quiet || goto :fail
".venv\Scripts\python.exe" -m pip install -r requirements.txt --quiet || goto :fail
echo [ok] Python packages installed

rem --- Frontend --------------------------------------------------------------
echo Installing and building the dashboard...
pushd frontend
call npm install --no-fund --no-audit --loglevel=error || (popd & goto :fail)
call npm run build || (popd & goto :fail)
popd
echo [ok] Dashboard built

rem --- Config & database -----------------------------------------------------
if not exist ".env" copy ".env.example" ".env" >nul && echo [ok] Created .env (edit it to add optional API keys)
".venv\Scripts\python.exe" -c "import sys; sys.path.insert(0, 'backend'); from app.db.session import run_migrations; run_migrations()" || goto :fail
echo [ok] Database ready

echo.
echo   Setup complete. Run start.bat to launch Ad Spy Engine.
echo.
pause
exit /b 0

:fail
echo.
echo   Setup did not finish. Fix the message above and run setup.bat again.
pause
exit /b 1
