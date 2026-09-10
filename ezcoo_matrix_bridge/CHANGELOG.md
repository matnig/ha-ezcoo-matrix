# Changelog

## 1.1.0

- **Serieller Betriebsmodus.** Die Bridge kann die Matrix jetzt wahlweise über
  Netzwerk (`verbindung: tcp`) oder über die Micro-USB-Buchse
  (`verbindung: seriell`) ansprechen. Protokoll und Entities sind identisch.

  Nützlich, wenn der Ethernet-Teil des Geräts ausfällt, während Hauptplatine und
  HDMI-Schaltung weiterarbeiten — ein Fehlerbild, das bei diesen Matrizen
  vorkommt. Der serielle Weg kennt außerdem die Zwei-Socket-Grenze des
  Netzwerkbetriebs nicht.

  Neue Optionen: `verbindung`, `serial_port` (Standard `/dev/ttyUSB0`),
  `serial_baud` (Standard 57600). Das Add-on erhält über `uart: true` Zugriff
  auf die seriellen Geräte des Hosts.

## 1.0.3

- Wartezeit verdoppelt sich, wenn die Matrix nicht antwortet — bis maximal
  300 Sekunden (`BACKOFF_MAX`). Vorher versuchte die Bridge auch bei einem
  tagelang abgeschalteten Gerät stur alle `poll_interval` Sekunden einen
  Neuaufbau; über zwölf Stunden Ausfall waren das rund 4300 Verbindungs-
  versuche, jetzt sind es knapp 150. Nach der ersten erfolgreichen Antwort
  gilt sofort wieder das normale Intervall.

## 1.0.2

- Umstellung auf die paho-mqtt-Callback-API v2. Version 1 ist seit paho 2.0
  veraltet und erzeugte beim Start eine `DeprecationWarning`. Der Rückgabewert
  von `on_connect` wird jetzt sowohl als `int` (paho 1.x) als auch als
  `ReasonCode` (paho 2.x) korrekt ausgewertet.

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
