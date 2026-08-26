# EZ-Protokoll der EZCOO EZ-MX44HAS2

Empirisch am Gerät ermittelt (Firmware Rev 1.11, Build 27.05.2022). Kein offizielles
Datenblatt — Abweichungen bei anderen Modellen oder Firmwareständen sind möglich.

## Zugangswege

| Weg | Parameter |
|---|---|
| Seriell (Micro-USB) | **57600 Baud**, 8N1, Zeilenende `CR+LF` |
| TCP | Standardport **23**, roher Socket, kein Telnet-Handshake |
| Web-UI | Port 80 |

Der USB-Anschluss ist eine UART-Brücke mit CH340-Chip (VID `0x1A86`, PID `0x7523`).
Unter Linux und macOS wird sie ohne Zusatztreiber erkannt.

## Fallstricke

Diese vier Punkte kosten beim Nachbau am meisten Zeit:

1. **57600 Baud, nicht 115200.** Bei falscher Baudrate kommt gar keine Antwort.
2. **`EZH` allein liefert `CMD ERR`.** Die Hilfe erscheint nur mit Ausrufezeichen:
   `EZH!`. Alle anderen Befehle funktionieren ohne `!`.
3. **Nur zwei gleichzeitige TCP-Verbindungen.** Die dritte wird sofort mit
   `Connection refused` abgewiesen.
4. **Antworten gehen an alle offenen Sockets**, nicht nur an den Absender. Zwei
   unabhängige Clients können Anfrage und Antwort deshalb nicht zuverlässig
   einander zuordnen. Genau ein Prozess sollte die Verbindung besitzen und alle
   Befehle serialisieren.

Der Webserver auf Port 80 hat einen eigenen Socket-Pool und bleibt auch dann
erreichbar, wenn beide TCP-Sockets belegt sind.

## Befehlssatz

Ausgabe von `EZH!`, gekürzt auf das Wesentliche.

### System

| Befehl | Wirkung |
|---|---|
| `EZH!` | Hilfe ausgeben |
| `EZSTA` | Vollständiger Systemstatus als formatierte Tabelle |
| `EZG STA` | Kompakter Status, eine Angabe pro Zeile |
| `EZS RST` | **Werksreset** |
| `EZS RBT` | Neustart |
| `EZS ADDR xx` / `EZG ADDR` | Systemadresse `00`–`99` (`00` = Einzelgerät) |

### Ausgänge

| Befehl | Wirkung |
|---|---|
| `EZS OUTx VS INy` | Ausgang `x` auf Eingang `y` (`x=0` bedeutet alle) |
| `EZS OUTx STREAM ON\|OFF` | Ausgabe an/aus |
| `EZS OUTx VIDEOy` | `y=1` BYPASS, `y=2` 4K→2K herunterskalieren |
| `EZS OUTx EXA EN\|DIS` | Externe Audioausgabe |
| `EZG OUTx VS` / `STREAM` / `VIDEO` / `EXA` | Jeweiligen Wert lesen |

### Eingänge

| Befehl | Wirkung |
|---|---|
| `EZS INx EDID y` | EDID-Vorgabe `y=0..35` setzen |
| `EZS INx EDID CY OUTy` | EDID von Ausgang `y` kopieren |
| `EZG INx EDID` | Gesetzten EDID-Index lesen |

### Netzwerk

Adressen werden dreistellig gepolstert erwartet (`xxx=[000-255]`), also
`192.168.001.050` statt `192.168.1.50`.

| Befehl | Wirkung |
|---|---|
| `EZS HIP xxx.xxx.xxx.xxx` | Host-IP |
| `EZS NMK xxx.xxx.xxx.xxx` | Subnetzmaske |
| `EZS RIP xxx.xxx.xxx.xxx` | **Gateway** („Route IP") |
| `EZS TIP zzzz` | TCP-Port (`0001`–`9999`) |
| `EZS DHCP y` | `0` = aus, `1` = an |
| `EZG HIP` / `NMK` / `RIP` / `TIP` / `DHCP` / `MAC` | Jeweiligen Wert lesen |

Für eine feste IP muss **`EZS DHCP 0`** gesetzt werden, sonst überschreibt das Gerät
die statischen Werte wieder. Netzwerkänderungen greifen erst nach `EZS RBT`.

## Antwortformate

`EZG STA` ist zeilenweise und leicht zu parsen:

```
ADDR 00
OUT1 VS IN2
OUT1 STREAM ON
OUT1 EXA EN
OUT1 VIDEO1
IN1 EDID 27
RIP 192.168.001.001
HIP 192.168.001.050
NMK 255.255.255.000
TIP 23
DHCP 0
MAC 00.08.dc.aa.bb.cc
```

`EZSTA` liefert eine Tabelle mit Rahmen, enthält als Einziges aber den
**Link-Status** von Ein- und Ausgängen:

```
= Input1   : EDID = 4K60Hz_3D_2CH_HDR    , Link = ON
= Output1  : Input =  2, EX-Audio = ON , Video Mode = BYPASS  , Link = ON , Out Stream = ON
```

Rund 3.900 Bytes, etwa 1,6 s über TCP. Ein einziger Aufruf genügt für den
kompletten Gerätezustand — deshalb nutzt die Bridge ausschließlich `EZSTA`.

## Kein Push, keine Automatik

Das Gerät meldet Änderungen **nicht** von sich aus. Schaltvorgänge über Frontpanel,
IR oder Web-UI werden erst beim nächsten Polling sichtbar.

Eine automatische Eingangsumschaltung bei eingeschalteter Quelle gibt es **nicht**:
weder ein Befehl in `EZH!` noch ein Schalter in der Web-UI, und im Test blieben
Ausgänge dauerhaft auf einem Eingang ohne Signal stehen, obwohl ein anderer
Eingang Signal führte.

## Web-UI

Die ausgelieferte HTML ist ein statischer Snapshot; die darin eingebetteten
Button-Zustände sind **nicht** der Live-Status. Dieser wird über CGI-Endpunkte
nachgeladen:

```
VIDDivSta.CGI  AUDDivSta.CGI  EDIDDivSta.CGI  NETDivSta.CGI  WEBDivSta.CGI
TimSendCmd.CGI  AudSendCmd.CGI  EdidsendCmd.CGI  NameSendCmd.CGI
NetSendCmd.CGI  NetDHCPSendCmd.CGI  SysSendCmd.CGI  IRSendCmd.CGI
```

Beispiel: `TimSendCmd.CGI?button=O1I3` schaltet Ausgang 1 auf Eingang 3.

## Firmware

Rev 1.11 (Build 27.05.2022) war Stand August 2026 die aktuelle Version. Das vom
Hersteller angebotene Update-Paket enthält denselben Build. Geflasht wird über den
UART-Bootloader eines STM32 mit dem Windows-Werkzeug „STM Flash Loader".
