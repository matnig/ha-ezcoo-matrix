# Changelog

## 1.0.1

- `build.yaml` ergänzt. Ohne diese Datei übergibt der Supervisor kein `BUILD_FROM`,
  wodurch der Docker-Build mit `base name (${BUILD_FROM}) should not be blank`
  abbrach. Basis ist jetzt `ghcr.io/home-assistant/<arch>-base:3.22` — die neueste
  Version, die für alle drei Architekturen inklusive armv7 verfügbar ist.

## 1.0.0

Erste Veröffentlichung.

- Eine einzige, serialisierte TCP-Verbindung zur Matrix (Firmware erlaubt nur zwei
  gleichzeitige Sockets und sendet Antworten an alle offenen Sockets).
- Vollständiger Zustand über einen einzigen `EZSTA`-Aufruf.
- MQTT Discovery: 21 Entities (4 Quellen-Selects, 1 Sammel-Select, 4 Stream-Switches,
  8 Binary-Sensors, 3 Diagnose-Sensoren, 1 Verbindungssensor).
- Frei wählbare Klarnamen für Ein- und Ausgänge.
- Automatischer Reconnect, sofortiges Nachlesen nach jedem Schaltbefehl.
