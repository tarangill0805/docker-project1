@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  python -m venv .venv
) else (
  py -m venv .venv
)
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
echo Choose your admin email and a password of at least 12 characters.
".venv\Scripts\python.exe" -m flask --app app:create_app set-admin
if errorlevel 1 goto failed
echo Setup complete. Now double-click RUN_WINDOWS.bat.
pause
exit /b 0
:failed
echo Setup failed. Read the error above. Python 3.11 or newer is required.
pause
exit /b 1
