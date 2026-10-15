@echo off
cd /d "%~dp0"
if exist "ETS-zu-Loxone-v1.0.7.exe" (
  start "" "ETS-zu-Loxone-v1.0.7.exe"
) else if exist "dist\ETS-zu-Loxone-v1.0.7.exe" (
  start "" "dist\ETS-zu-Loxone-v1.0.7.exe"
) else (
  python app.py
  if errorlevel 1 pause
)
