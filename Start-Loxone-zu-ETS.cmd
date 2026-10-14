@echo off
cd /d "%~dp0"
if exist "dist\Loxone-ETS-Exporter-v5.exe" (
  start "" "dist\Loxone-ETS-Exporter-v5.exe"
) else if exist "dist\Loxone-ETS-Exporter.exe" (
  start "" "dist\Loxone-ETS-Exporter.exe"
) else (
  python reverse_app.py
  if errorlevel 1 pause
)
