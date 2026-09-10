# EZCOO Matrix Bridge

## Voraussetzungen

- Home Assistant OS oder Supervised
- Ein MQTT-Broker, üblicherweise das **Mosquitto broker**-Add-on, plus die
  **MQTT**-Integration
- Eine EZCOO EZ-MX44HAS2 mit erreichbarer IP-Adresse im selben Netz

## Der Matrix eine feste IP geben

Ab Werk steht die Matrix auf DHCP mit einer statischen Ausweich-IP, die meist in
einem fremden Subnetz liegt — dann taucht sie im LAN nicht auf. Feste Adresse setzen
geht am zuverlässigsten über die serielle Schnittstelle (Micro-USB, **57600 Baud**,
8N1, Zeilenende `CR+LF`):

```
EZS DHCP 0
EZS HIP 192.168.001.050
EZS NMK 255.255.255.000
EZS RIP 192.168.001.001
EZS RBT
```

Adressen müssen dreistellig gepolstert werden. `EZS RIP` ist das **Gateway**.
Ohne `EZS DHCP 0` überschreibt das Gerät die statischen Werte wieder.
Ein Neustart (`EZS RBT`) ist nötig, damit die Änderung greift.

Kontrolle mit `EZG HIP`, `EZG NMK`, `EZG RIP`, `EZG DHCP`, `EZG TIP`.

## Konfiguration

| Option | Standard | Bedeutung |
|---|---|---|
| `verbindung` | `tcp` | `tcp` über Netzwerk oder `seriell` über Micro-USB |
| `matrix_host` | — | **Pflicht bei `tcp`.** IP-Adresse der Matrix |
| `serial_port` | `/dev/ttyUSB0` | Nur bei `seriell`: das serielle Gerät |
| `serial_baud` | `57600` | Nur bei `seriell`: Baudrate der Matrix |
| `matrix_port` | `23` | TCP-Port, auslesbar mit `EZG TIP` |
| `poll_interval` | `10` | Sekunden zwischen zwei Statusabfragen |
| `BACKOFF_MAX` | `300` | Obergrenze der Wartezeit, wenn die Matrix nicht antwortet |
| `base_topic` | `ezcoo/mx44has2` | Präfix der MQTT-Topics |
| `discovery_prefix` | `homeassistant` | Discovery-Präfix von Home Assistant |
| `input_names` | `IN1`…`IN4` | Klarnamen der Eingänge, z. B. `Apple TV` |
| `output_names` | `OUT1`…`OUT4` | Klarnamen der Ausgänge, z. B. `Wohnzimmer` |
| `log_level` | `info` | `debug` protokolliert jeden gesendeten Befehl |
| `mqtt_host`, `mqtt_port`, `mqtt_user`, `mqtt_password` | — | Nur für einen externen Broker nötig |

Läuft das Mosquitto-Add-on, holt sich die Bridge die Zugangsdaten automatisch vom
Supervisor. Die `mqtt_*`-Optionen bleiben dann leer.

Beispiel:

```yaml
matrix_host: 192.168.1.50
poll_interval: 10
input_names:
  - Apple TV
  - Spielkonsole
  - PC
  - Blu-ray
output_names:
  - Wohnzimmer
  - Küche
  - Schlafzimmer
  - Terrasse
```

Die Namen aus `input_names` werden zu den Auswahloptionen der `select`-Entities.

## Serieller Betrieb

Fällt der Netzwerkteil der Matrix aus, während sie über ihre Tasten
weiterarbeitet, ist die Micro-USB-Buchse der Rettungsweg. Sie spricht dasselbe
Protokoll, kennt die Zwei-Socket-Grenze nicht und ist vom Ethernet-Chip
vollständig unabhängig.

1. Micro-USB der Matrix mit einem USB-Anschluss des Home-Assistant-Rechners
   verbinden.
2. Unter **Einstellungen → System → Hardware → Alle Hardware** nachsehen, wie das
   Gerät heißt — meist `/dev/ttyUSB0`. Stabiler ist der Pfad unter
   `/dev/serial/by-id/…`, weil er sich beim Neustart nicht ändert.
3. In der Add-on-Konfiguration `verbindung: seriell` setzen und `serial_port`
   eintragen. `matrix_host` darf leer bleiben.

Findet das Add-on das angegebene Gerät nicht, schreibt es beim Start eine Liste
der tatsächlich vorhandenen seriellen Geräte ins Protokoll.

Die Matrix verwendet **57600 Baud**, 8N1 — nicht die oft vermuteten 115200.

## Entities

| Typ | Anzahl | Beschreibung |
|---|---|---|
| `select` | 4 | Quelle je Ausgang |
| `select` | 1 | „Alle Ausgänge Quelle" — schaltet alle gleichzeitig |
| `switch` | 4 | Stream an/aus je Ausgang |
| `binary_sensor` | 4 | Signal am Eingang: ist die Quelle eingeschaltet? |
| `binary_sensor` | 4 | Display am Ausgang verbunden (Diagnose) |
| `binary_sensor` | 1 | Verbindung der Bridge zur Matrix (Diagnose) |
| `sensor` | 3 | Firmware, IP, MAC (Diagnose) |
| `button` | 1 | Neustart der Matrix (`EZS RBT`) |

## MQTT-Topics

```
<base_topic>/status            online | offline   (LWT, retained)
<base_topic>/state             JSON mit dem Gesamtzustand (retained)
<base_topic>/out1/source/set   "Apple TV" | "IN2" | "2"
<base_topic>/out1/stream/set   ON | OFF
<base_topic>/all/source/set    schaltet alle Ausgänge
```

Auf den Command-Topics werden Klarname, `IN2`, `in 2` und `2` gleichermaßen
akzeptiert. Unbekannte Werte werden verworfen und protokolliert.

Aufbau von `state`:

```json
{
  "outputs": {"1": {"source": "IN2", "source_name": "Apple TV", "stream": "ON",
                    "link": "ON", "ex_audio": "ON", "video_mode": "BYPASS"}},
  "inputs":  {"1": {"signal": "ON", "edid": "4K60Hz_3D_2CH_HDR"}},
  "device":  {"firmware": "1.11", "ip": "192.168.1.50",
              "mac": "00:08:dc:aa:bb:cc", "tcp_port": 23, "dhcp": "DISABLE"},
  "bridge":  {"connected": true, "host": "192.168.1.50"}
}
```

## Beispielautomation

```yaml
automation:
  - alias: Beim Einschalten des Apple TV im Wohnzimmer umschalten
    triggers:
      - trigger: state
        entity_id: binary_sensor.apple_tv_signal
        to: "on"
    actions:
      - action: select.select_option
        target:
          entity_id: select.wohnzimmer_quelle
        data:
          option: Apple TV
```

Damit lässt sich die Automatik nachbilden, die das Gerät selbst nicht mitbringt —
mit dem Vorteil, dass du die Regeln bestimmst.

## Funktionsweise

Der Zustand wird per `EZSTA` gelesen. Ein Aufruf liefert Routing, Stream-Status,
Link-Status aller Ein- und Ausgänge sowie die Netzwerkkonfiguration — rund 3.900
Bytes in etwa 1,6 s. Nach jedem Schaltbefehl wird sofort nachgelesen, statt auf den
nächsten Zyklus zu warten.

Bricht die Verbindung ab, wird sie beim nächsten Befehl neu aufgebaut; scheitert
das, meldet der Diagnosesensor „Bridge-Verbindung" den Ausfall.

Antwortet die Matrix nicht, verdoppelt sich die Wartezeit bis zum nächsten
Versuch — 20 s, 40 s, 80 s und so weiter bis maximal `BACKOFF_MAX`. Damit klopft
die Bridge nicht stundenlang im Sekundentakt an ein abgeschaltetes Gerät. Sobald
eine Antwort kommt, gilt sofort wieder das normale `poll_interval`.

**Zur Abfragehäufigkeit:** Mit dem Standardwert 10 s sind es 360 Abfragen pro
Stunde. Wer das Gerät schonen will, setzt `poll_interval` auf 30 oder 60 — der
einzige Nachteil ist, dass Schaltvorgänge am Frontpanel oder per IR entsprechend
später in Home Assistant erscheinen. Eigene Schaltbefehle werden davon nicht
verzögert, denn danach wird sofort nachgelesen.

## Grenzen und Stolperfallen

- **Kein Push vom Gerät.** Schaltvorgänge über Frontpanel, IR oder Web-UI erscheinen
  erst beim nächsten Poll. `poll_interval` bestimmt die Verzögerung.
- **Nur zwei TCP-Verbindungen gleichzeitig.** Läuft parallel ein weiteres Werkzeug
  auf Port 23, kann die Bridge ausgesperrt werden. Die Web-UI auf Port 80 stört nicht.
- **„Alle Ausgänge Quelle" hat keine Rückmeldung.** Der angezeigte Wert veraltet,
  sobald einzelne Ausgänge danach separat umgeschaltet werden.
- **EDID, HDCP und Netzwerkeinstellungen werden bewusst nicht angeboten.** Diese
  Befehle bleiben der seriellen Schnittstelle und der Web-UI vorbehalten, weil ein
  Fehlgriff dort ein funktionierendes Setup zerlegen kann.

## Fehlersuche

| Symptom | Ursache |
|---|---|
| `matrix_host ist nicht gesetzt` | IP-Adresse in der Konfiguration eintragen |
| `Kein MQTT-Broker gefunden` | Mosquitto-Add-on installieren oder `mqtt_host` setzen |
| `Connection refused` | Beide TCP-Sockets belegt, oder falsche IP/falscher Port |
| `Unvollstaendige Statusantwort` | Antwort abgeschnitten — anderes Modell oder gestörte Verbindung |
| Keine Entities in HA | MQTT-Integration prüfen; `<base_topic>/state` mit einem MQTT-Client mitlesen |

`log_level: debug` protokolliert jeden gesendeten Befehl und jede Antwort.
