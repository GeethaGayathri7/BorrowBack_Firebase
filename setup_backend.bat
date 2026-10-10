@echo off
setlocal
cd /d "%~dp0backend"
if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv
  if errorlevel 1 goto fail
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
if not exist ".env" (
  copy .env.example .env
  echo.
  echo Created backend\.env. Edit it with your MySQL password and optional SMTP settings, then run this script again.
  pause
  exit /b 0
)
python -m uvicorn app:app --reload --host 0.0.0.0 --port 8000
exit /b 0
:fail
echo Could not create the Python virtual environment. Install Python 3.10+ and try again.
pause
exit /b 1
