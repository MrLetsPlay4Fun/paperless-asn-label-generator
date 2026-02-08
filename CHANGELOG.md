# Changelog

## 0.1.4 - 2026-02-08
### Changed
- Vorschau für `CODE128` rendert jetzt als echter Barcode statt Platzhalter.
- Vorschau-Layout wurde neu ausbalanciert: QR kleiner, Text deutlich größer/lesbarer, kein Überlappen von CODE128 und Text.
- Fensterbreite und Vorschaufläche wurden vergrößert, damit alle UI-Elemente und der Vorschau-Text vollständig sichtbar bleiben.
- Statusmeldungen in der UI sind vereinheitlicht (`[INFO]`, `[OK]`, `[WARN]`, `[ERROR]`) und farblich klar getrennt.
- Layout verhält sich auf kleineren Displays robuster (reduzierte `minsize`, bessere Spalten-Gewichtung, umbrochene Hilfstexte/Statuszeilen).

## 0.1.3 - 2026-02-08
### Changed
- Kalibrierungs-Eingaben sind jetzt als sichtbare Delta-Werte ausgelegt (Default `0.0` in der UI), während intern weiterhin die Basiswerte genutzt werden.
- Persistierte Kalibrierung speichert den Modus explizit als `calibration_mode = "delta"`; bestehende Legacy-Configs ohne Marker werden kompatibel übernommen.
- GUI-Titel zeigt jetzt die aktuelle App-Version an.

### Fixed
- Doppelten `_build_ui()`-Aufruf entfernt, damit beim Start keine doppelten Widgets oder Event-Bindings entstehen.
- Fehler beim Laden/Speichern der `config.json` werden in der Oberfläche sichtbar angezeigt statt still ignoriert.

## 0.1.2 - 2026-02-03
### Added
- Persistente Einstellungen (config.json) im User-Config-Verzeichnis (XDG_CONFIG_HOME / ~/.config, macOS Application Support, Windows APPDATA).
- Autosave der GUI-Einstellungen (debounced), damit Drucker-Kalibrierwerte erhalten bleiben.
- Button "Config löschen": löscht config.json und setzt Standard-Preset-Werte zurück.

### Fixed
- Stabileres Laden/Speichern (fehlerhafte config bricht GUI nicht ab).
