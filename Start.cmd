@echo off
cd /d "%~dp0"
if exist "dist\ETS-Loxone-Importer-v4.exe" (
  start "" "dist\ETS-Loxone-Importer-v4.exe"
) else if exist "dist\ETS-Loxone-Importer-v2.exe" (
  start "" "dist\ETS-Loxone-Importer-v2.exe"
) else if exist "dist\ETS-Loxone-Importer.exe" (
  start "" "dist\ETS-Loxone-Importer.exe"
) else (
  python app.py
  if errorlevel 1 pause
)
