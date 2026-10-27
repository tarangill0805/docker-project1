@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo First run SETUP_WINDOWS.bat.
  pause
  exit /b 1
)
echo Website: http://127.0.0.1:5000
echo Admin: http://127.0.0.1:5000/admin
echo Keep this window open. Press Ctrl+C to stop the website.
".venv\Scripts\python.exe" -m flask --app app:create_app run
pause
