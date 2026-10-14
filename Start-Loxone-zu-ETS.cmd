@echo off
cd /d "%~dp0"
if exist "Loxone-zu-ETS-v1.0.1.exe" (
  start "" "Loxone-zu-ETS-v1.0.1.exe"
) else if exist "dist\Loxone-zu-ETS-v1.0.1.exe" (
  start "" "dist\Loxone-zu-ETS-v1.0.1.exe"
) else (
  python reverse_app.py
  if errorlevel 1 pause
)
