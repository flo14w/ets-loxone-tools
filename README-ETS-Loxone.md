# ETS → Loxone

Windows-Programm zum Einlesen von ETS-Gruppenadressen-XML und Übernehmen in Loxone Config.

1. ETS-XML und Loxone-Projekt laden.
2. Gruppenadressen auswählen und Sensor/Aktor zuordnen.
3. Loxone-Datentyp, Kategorie und Raum prüfen. Bekannte Typen werden anhand des ETS-DPT vorgeschlagen.
4. Importübersicht prüfen.
5. Eine neue Loxone-Datei erstellen oder in die aktuelle Datei importieren.

Beim Import in die aktuelle Datei werden vorhandene KNX-Objekte in der ausgewählten KNX-Extension anhand ihres Namens aktualisiert. Neue Namen werden angelegt. Mehrdeutige Treffer und widersprüchliche Funktionen werden als Konflikt angezeigt. Vor dem direkten Import wird eine Sicherungskopie erstellt.

Vorhandene Kategorie- und Raumzuordnungen bleiben erhalten, wenn für das Feld „Nicht zugeordnet“ oder „Nicht verwenden“ gewählt wurde. Eine konkret ausgewählte Kategorie oder ein konkreter Raum wird übernommen.

## Build

Python 3.11 mit Tkinter installieren und dann im Repository-Stamm:

```powershell
python -m pip install -r requirements-build.txt
python -m PyInstaller --noconfirm --onefile --windowed --add-data "type_profiles.json;." --add-data "output/logo/ets-loxone-logo-v1.png;assets" --icon "output/logo/ets-loxone-logo-v1.png" --name ETS-Loxone-Importer app.py
```
