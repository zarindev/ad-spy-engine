@echo off
title Ad Spy Engine
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Ad Spy Engine is not set up yet - running setup first...
  call setup.bat || exit /b 1
)
if not exist "frontend\dist\index.html" (
  echo Dashboard build missing - building...
  pushd frontend & call npm run build & popd
)
".venv\Scripts\python.exe" backend\run.py %*
pause
