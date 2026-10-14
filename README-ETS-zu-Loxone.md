# ETS → Loxone

Windows-Programm zum Einlesen von ETS-Gruppenadressen-XML und Übernehmen in Loxone Config.

## Gruppenadressen in ETS5 als XML exportieren

1. Öffne das Projekt in ETS5 und wechsle in die Ansicht **Gruppenadressen**.
2. Klicke im Gruppenadressbaum mit der rechten Maustaste auf den obersten Eintrag **Gruppenadressen**.
3. Wähle **Gruppenadressen exportieren**.
4. Wähle **XML** als Format, gib Speicherort und Dateinamen an und starte den Export.
5. Wähle die erzeugte XML-Datei anschließend im Programm als ETS-Export aus.

Der XML-Export enthält die Gruppenadress-Struktur mit Namen und vorhandenen DPT-Angaben. Geräte- und Kommunikationsobjekt-Verknüpfungen werden nicht exportiert. [KNX beschreibt den Export hier](https://support.knx.org/hc/de/articles/360022237580-Gruppenadresse-und-Export).

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
python -m PyInstaller --noconfirm ETS-zu-Loxone.spec
```
