# ETS ↔ Loxone KNX-Werkzeuge

Zwei eigenständige Windows-Desktopprogramme für den Austausch von KNX-Gruppenadressen mit Loxone Config:

- **ETS → Loxone:** ETS-Gruppenadressen-XML einlesen, Sensoren/Aktoren und Datentypen zuordnen, Kategorien und Räume prüfen und in eine neue oder bestehende Loxone-Datei importieren.
- **Loxone → ETS:** KNX-Objekte aus einer Loxone-Datei auslesen, Adressen und Datentypen prüfen und als ETS-Gruppenadressen-XML exportieren.

Die Anwendungen laufen lokal unter Windows. Sie verbinden sich nicht mit einem Loxone Miniserver.

## Starten

Die Windows-EXE-Dateien und Startskripte sind im Repository-Ordner `dist` beziehungsweise im Projektstamm verfügbar, sofern sie als Release heruntergeladen oder lokal gebaut wurden. Zum Starten aus dem Quellcode ist Python 3.11 mit Tkinter nötig. `Start.cmd` startet ETS → Loxone; `Start-Loxone-zu-ETS.cmd` startet Loxone → ETS.

## Dokumentation und Build

- [ETS → Loxone](README-ETS-Loxone.md)
- [Loxone → ETS](README-Loxone-ETS.md)

Die `.spec`-Dateien bauen beide Programme mit PyInstaller. `requirements-build.txt` enthält die Build-Abhängigkeit.

## Projektdaten

ETS-Exporte, Loxone-Projektdateien (`.Loxone`) und erzeugte XML-Dateien gehören nicht in dieses Repository. `.gitignore` schließt diese Dateien aus. Die Typvorlagen in `type_profiles.json` enthalten nur allgemeine KNX-Objekteinstellungen.
