# Loxone → ETS

Eigenständiges Windows-Programm zum Auslesen der KNX-Objekte einer Loxone-Datei und Exportieren der Gruppenadressen als ETS-XML.

1. Loxone-Datei auswählen und Adressen einlesen.
2. Einträge anhand ihres Namens prüfen. Verschiedene Namen mit derselben Loxone-Adresse bleiben getrennte Einträge.
3. ETS-Zieladresse und Datentyp festlegen. Markierte Einträge können innerhalb einer gewählten Haupt- und Mittelgruppe aufsteigend neu nummeriert werden.
4. Exportübersicht prüfen und XML speichern.
5. XML in ETS importieren.

Die Loxone-Datei wird nur gelesen. Geräte- oder Kommunikationsobjektverknüpfungen werden nicht erstellt.

## Build

Python 3.11 mit Tkinter installieren und dann im Repository-Stamm:

```powershell
python -m pip install -r requirements-build.txt
python -m PyInstaller --noconfirm --onefile --windowed --add-data "output/logo/loxone-ets-exporter-logo-v1.png;assets" --icon "output/logo/loxone-ets-exporter-logo-v1.png" --name Loxone-ETS-Exporter reverse_app.py
```
