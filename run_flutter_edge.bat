@echo off
setlocal
cd /d "%~dp0frontend"
where flutter >nul 2>nul
if errorlevel 1 (
  echo Flutter was not found in PATH. Install Flutter and restart this terminal.
  pause
  exit /b 1
)
flutter pub get
if errorlevel 1 goto fail
flutter run -d edge
exit /b 0
:fail
echo Flutter setup failed. Check the error above.
pause
exit /b 1
