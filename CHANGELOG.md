# Changelog

## 0.1.2 - 2026-02-03
### Added
- Persistente Einstellungen (config.json) im User-Config-Verzeichnis (XDG_CONFIG_HOME / ~/.config, macOS Application Support, Windows APPDATA).
- Autosave der GUI-Einstellungen (debounced), damit Drucker-Kalibrierwerte erhalten bleiben.
- Button "Config löschen": löscht config.json und setzt Standard-Preset-Werte zurück.

### Fixed
- Stabileres Laden/Speichern (fehlerhafte config bricht GUI nicht ab).