# ETS ↔ Loxone KNX-Werkzeuge

Ein Windows-Desktopprogramm mit zwei umschaltbaren Bereichen. Die beiden bisherigen Arbeitsoberflächen bleiben in eigenen Reitern erhalten; beim Start ist **ETS → Loxone** ausgewählt.

- **ETS → Loxone:** ETS-Gruppenadressen-XML einlesen, Sensoren/Aktoren und Datentypen zuordnen, Kategorien und Räume prüfen und in eine neue oder bestehende Loxone-Datei importieren.
- **Loxone → ETS:** KNX-Objekte aus einer Loxone-Datei auslesen, Adressen und Datentypen prüfen und als ETS-Gruppenadressen-XML exportieren.

Die Anwendungen laufen lokal unter Windows. Sie verbinden sich nicht mit einem Loxone Miniserver.

## Windows-Programme herunterladen und starten

Die fertigen Windows-Programme liegen als Downloads im [GitHub-Bereich „Releases“](https://github.com/flo14w/ets-loxone-tools/releases), nicht im Quellcode-Repository. Lade die gemeinsame Anwendung `ETS-Loxone-KNX-Werkzeuge-v1.0.8.exe` herunter.

`Start-ETS-Loxone-KNX.cmd` startet die gemeinsame EXE neben dem Skript oder eine lokal gebaute EXE in `dist`. Wenn noch keine EXE vorhanden ist, startet es den Quellcode mit Python 3.11 und Tkinter. Die bisherigen Startskripte für die einzelnen Anwendungen bleiben verfügbar.

## Dokumentation und Build

- [ETS → Loxone](README-ETS-zu-Loxone.md)
- [Loxone → ETS](README-Loxone-zu-ETS.md)

`ETS-Loxone-KNX-Werkzeuge.spec` baut das gemeinsame Programm mit PyInstaller. Die bisherigen `.spec`-Dateien für die einzelnen Anwendungen bleiben als ältere Build-Varianten erhalten. Fenstertitel beziehen ihre Produktversion aus `version.py`; Windows-Dateieigenschaften und EXE-Dateinamen verwenden dieselbe Version. `requirements-build.txt` enthält die Build-Abhängigkeit.

## Mitwirkung und Logo

Der vollständige Quellcode wurde mit OpenAI Codex erstellt. Das Logo wurde mit künstlicher Intelligenz (KI) erstellt.

## Projektdaten

ETS-Exporte, Loxone-Projektdateien (`.Loxone`) und erzeugte XML-Dateien gehören nicht in dieses Repository. `.gitignore` schließt diese Dateien aus. Die Typvorlagen in `type_profiles.json` enthalten nur allgemeine KNX-Objekteinstellungen.
