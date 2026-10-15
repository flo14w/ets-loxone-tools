# ETS ↔ Loxone KNX-Werkzeuge

Zwei eigenständige Windows-Desktopprogramme für den Austausch von KNX-Gruppenadressen mit Loxone Config:

- **ETS → Loxone:** ETS-Gruppenadressen-XML einlesen, Sensoren/Aktoren und Datentypen zuordnen, Kategorien und Räume prüfen und in eine neue oder bestehende Loxone-Datei importieren.
- **Loxone → ETS:** KNX-Objekte aus einer Loxone-Datei auslesen, Adressen und Datentypen prüfen und als ETS-Gruppenadressen-XML exportieren.

Die Anwendungen laufen lokal unter Windows. Sie verbinden sich nicht mit einem Loxone Miniserver.

## Windows-Programme herunterladen und starten

Die fertigen Windows-Programme liegen als Downloads im [GitHub-Bereich „Releases“](https://github.com/flo14w/ets-loxone-tools/releases), nicht im Quellcode-Repository. Lade dort `ETS-zu-Loxone-v1.0.7.exe` oder `Loxone-zu-ETS-v1.0.7.exe` herunter und starte die passende EXE direkt. `dist` wird erst beim lokalen Build angelegt und ist deshalb im Repository nicht vorhanden.

Die Startskripte starten eine heruntergeladene EXE neben dem Skript oder eine lokal gebaute EXE in `dist`. Andernfalls starten sie den Quellcode mit Python 3.11 und Tkinter. `Start-ETS-zu-Loxone.cmd` öffnet ETS → Loxone; `Start-Loxone-zu-ETS.cmd` öffnet Loxone → ETS.

## Dokumentation und Build

- [ETS → Loxone](README-ETS-zu-Loxone.md)
- [Loxone → ETS](README-Loxone-zu-ETS.md)

Die `.spec`-Dateien bauen beide Programme mit PyInstaller. Beide EXEs und Fenstertitel beziehen ihre Produktversion aus `version.py`; Windows-Dateieigenschaften und Release-Dateinamen verwenden dieselbe Version. `requirements-build.txt` enthält die Build-Abhängigkeit.

## Mitwirkung und Logo

Der vollständige Quellcode wurde mit OpenAI Codex erstellt. Das Logo wurde mit künstlicher Intelligenz (KI) erstellt.

## Projektdaten

ETS-Exporte, Loxone-Projektdateien (`.Loxone`) und erzeugte XML-Dateien gehören nicht in dieses Repository. `.gitignore` schließt diese Dateien aus. Die Typvorlagen in `type_profiles.json` enthalten nur allgemeine KNX-Objekteinstellungen.
