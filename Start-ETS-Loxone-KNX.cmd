@echo off
cd /d "%~dp0"
if exist "ETS-Loxone-KNX-Werkzeuge-v1.0.8.exe" (
  start "" "ETS-Loxone-KNX-Werkzeuge-v1.0.8.exe"
) else if exist "dist\ETS-Loxone-KNX-Werkzeuge-v1.0.8.exe" (
  start "" "dist\ETS-Loxone-KNX-Werkzeuge-v1.0.8.exe"
) else (
  python combined_app.py
  if errorlevel 1 pause
)
