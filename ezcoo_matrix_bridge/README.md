# EZCOO Matrix Bridge

Bindet eine **EZCOO EZ-MX44HAS2** (4x4-HDMI-2.0-Matrix, baugleich ROFAVEZCO MX44-HAS2)
per MQTT in Home Assistant ein.

Nach dem Start erscheint automatisch ein Gerät mit 21 Entities: Eingangswahl je
Ausgang, Stream an/aus, Signalerkennung an den Eingängen und Diagnosewerte.

Die Bridge hält genau eine TCP-Verbindung zur Matrix und serialisiert alle Befehle —
notwendig, weil die Firmware nur zwei gleichzeitige Sockets zulässt und Antworten an
alle offenen Sockets sendet.

Voraussetzung: ein MQTT-Broker (z. B. das Mosquitto-broker-Add-on).

Vollständige Anleitung im Reiter **Dokumentation**.

> Dieses Add-on wurde mit KI-Unterstützung (Claude, Anthropic) erstellt. Das
> Protokoll wurde empirisch am Gerät ermittelt. Details im
> [Repository](https://github.com/matnig/ha-ezcoo-matrix).
