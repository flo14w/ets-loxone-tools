@echo off
cd /d "%~dp0"
if exist "ETS-zu-Loxone-v1.0.2.exe" (
  start "" "ETS-zu-Loxone-v1.0.2.exe"
) else if exist "dist\ETS-zu-Loxone-v1.0.2.exe" (
  start "" "dist\ETS-zu-Loxone-v1.0.2.exe"
) else (
  python app.py
  if errorlevel 1 pause
)
