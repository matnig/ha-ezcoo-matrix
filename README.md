# EZCOO Add-ons für Home Assistant

Ein Home-Assistant-Add-on-Repository für **EZCOO-HDMI-Matrizen**.

## Enthaltene Add-ons

| Add-on | Beschreibung |
|---|---|
| [EZCOO Matrix Bridge](./ezcoo_matrix_bridge) | Steuert eine EZ-MX44HAS2 (4x4 HDMI 2.0) per MQTT — über Netzwerk oder serielle Schnittstelle |

## Installation

1. In Home Assistant: **Einstellungen → Add-ons → Add-on Store**
2. Oben rechts **⋮ → Repositories**
3. Diese URL hinzufügen:

   ```
   https://github.com/matnig/ha-ezcoo-matrix
   ```

4. Das Add-on erscheint anschließend im Store und kann installiert werden.

Voraussetzungen: Home Assistant OS oder Supervised, ein MQTT-Broker
(z. B. das Mosquitto-broker-Add-on) und die MQTT-Integration.

## Unterstützte Geräte

Entwickelt und getestet mit der **EZCOO EZ-MX44HAS2**, Firmware Rev 1.11
(baugleich verkauft als ROFAVEZCO MX44-HAS2).

Andere EZCOO-Modelle mit demselben `EZ`-Befehlssatz (`EZS`/`EZG`) funktionieren
mit hoher Wahrscheinlichkeit ebenfalls, sofern sie 4 Ein- und 4 Ausgänge haben.
Modelle mit abweichender Portzahl brauchen Anpassungen im Parser.

Eine ausführliche Beschreibung des Protokolls inklusive der Eigenheiten der
Firmware steht in [PROTOCOL.md](./PROTOCOL.md).

## Mit KI erstellt

**Dieses Repository wurde vollständig von einer KI (Claude, Anthropic) im Dialog
mit dem Repository-Inhaber erstellt** — Code, Dokumentation und die
Protokoll-Analyse.

Was das konkret heißt:

- Das Protokoll wurde **empirisch am realen Gerät** ermittelt: serielle Verbindung,
  Auslesen der eingebauten Hilfe (`EZH!`), Messung des TCP-Verhaltens. Es stammt
  nicht aus einem offiziellen Datenblatt.
- **Getestet am echten Gerät:** die serielle und die TCP-Kommunikation, der
  `EZSTA`-Parser (liefert alle 4 Ein- und Ausgänge korrekt), das Verbindungs- und
  Socket-Verhalten sowie die Umsetzung von MQTT-Nachrichten in `EZ`-Befehle.
- **Nicht in einer echten Home-Assistant-Installation erprobt:** der Add-on-Build,
  die MQTT-Discovery-Registrierung und der Dauerbetrieb. Wer das Add-on einsetzt,
  ist der erste Praxistest.

Fehlerberichte sind willkommen. Prüfe den Code vor dem Einsatz selbst — er greift
schreibend auf deine Hardware zu.

## Lizenz

[MIT](./LICENSE)
