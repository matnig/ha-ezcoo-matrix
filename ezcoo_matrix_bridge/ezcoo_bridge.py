#!/usr/bin/env python3
"""EZCOO EZ-MX44HAS2 <-> MQTT Bridge fuer Home Assistant.

Die Matrix nimmt nur zwei gleichzeitige TCP-Verbindungen an und sendet Antworten
an *alle* offenen Sockets. Deshalb haelt dieser Prozess genau eine Verbindung und
serialisiert saemtliche Befehle darueber.
"""
from __future__ import annotations

import json
import logging
import os
import re
import signal
import socket
import sys
import threading
import time

import paho.mqtt.client as mqtt

LOG = logging.getLogger("ezcoo")

# ---------------------------------------------------------------- Konfiguration


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    return value if value not in (None, "") else default


def _names(raw: str | None, fallback: list[str]) -> list[str]:
    if not raw:
        return fallback
    parts = [p.strip() for p in raw.split("|") if p.strip()]
    if len(parts) != len(fallback):
        LOG.warning("Erwarte %d Namen, %d bekommen - nutze Standardnamen",
                    len(fallback), len(parts))
        return fallback
    return parts


MATRIX_HOST = _env("MATRIX_HOST", "")
MATRIX_PORT = int(_env("MATRIX_PORT", "23"))
POLL_INTERVAL = float(_env("POLL_INTERVAL", "10"))
BASE_TOPIC = (_env("BASE_TOPIC", "ezcoo/mx44has2") or "").rstrip("/")
DISCOVERY_PREFIX = (_env("DISCOVERY_PREFIX", "homeassistant") or "").rstrip("/")

MQTT_HOST = _env("MQTT_HOST", "core-mosquitto")
MQTT_PORT = int(_env("MQTT_PORT", "1883"))
MQTT_USER = _env("MQTT_USER")
MQTT_PASSWORD = _env("MQTT_PASSWORD")

INPUT_NAMES = _names(_env("INPUT_NAMES"), ["IN1", "IN2", "IN3", "IN4"])
OUTPUT_NAMES = _names(_env("OUTPUT_NAMES"), ["OUT1", "OUT2", "OUT3", "OUT4"])

STATE_TOPIC = f"{BASE_TOPIC}/state"
AVAIL_TOPIC = f"{BASE_TOPIC}/status"

# ------------------------------------------------------------------- Parsing

RE_FW = re.compile(r"F/W Version\s*:\s*([\d.]+)")
RE_ADDR = re.compile(r"System Address\s*=\s*(\d+)")
RE_HIP = re.compile(r"Host IP Address\s*=\s*([\d.]+)")
RE_RIP = re.compile(r"Router IP Address\s*=\s*([\d.]+)")
RE_NMK = re.compile(r"Net Mask\s*=\s*([\d.]+)")
RE_MAC = re.compile(r"MAC Address\s*=\s*([0-9A-Fa-f.:-]+)")
RE_TIP = re.compile(r"TCP Port\s*=\s*(\d+)")
RE_DHCP = re.compile(r"DHCP\s*=\s*(ENABLE|DISABLE)")
RE_INPUT = re.compile(
    r"Input(\d)\s*:\s*EDID\s*=\s*(\S+)\s*,\s*Link\s*=\s*(ON|OFF)")
RE_OUTPUT = re.compile(
    r"Output(\d)\s*:\s*Input\s*=\s*(\d)\s*,\s*EX-Audio\s*=\s*(\w+)\s*,"
    r"\s*Video Mode\s*=\s*(\S+)\s*,\s*Link\s*=\s*(ON|OFF)\s*,"
    r"\s*Out Stream\s*=\s*(\w+)")


def _unpad_ip(value: str) -> str:
    """192.168.001.050 -> 192.168.1.50"""
    try:
        return ".".join(str(int(o)) for o in value.split("."))
    except ValueError:
        return value


def _norm_mac(value: str) -> str:
    hexes = re.findall(r"[0-9A-Fa-f]{2}", value)
    return ":".join(h.lower() for h in hexes) if len(hexes) == 6 else value


def parse_status(text: str) -> dict:
    """Zerlegt die EZSTA-Ausgabe in ein State-Dict."""
    outputs: dict[str, dict] = {}
    for m in RE_OUTPUT.finditer(text):
        idx, src, exa, video, link, stream = m.groups()
        outputs[idx] = {
            "source": f"IN{src}",
            "source_name": INPUT_NAMES[int(src) - 1],
            "stream": stream.upper(),
            "link": link.upper(),
            "ex_audio": "ON" if exa.upper() in ("ON", "EN") else "OFF",
            "video_mode": video,
        }

    inputs: dict[str, dict] = {}
    for m in RE_INPUT.finditer(text):
        idx, edid, link = m.groups()
        inputs[idx] = {"signal": link.upper(), "edid": edid}

    def _one(rx, conv=lambda v: v):
        m = rx.search(text)
        return conv(m.group(1)) if m else None

    device = {
        "firmware": _one(RE_FW),
        "address": _one(RE_ADDR),
        "ip": _one(RE_HIP, _unpad_ip),
        "gateway": _one(RE_RIP, _unpad_ip),
        "netmask": _one(RE_NMK, _unpad_ip),
        "mac": _one(RE_MAC, _norm_mac),
        "tcp_port": _one(RE_TIP, int),
        "dhcp": _one(RE_DHCP),
    }
    return {"outputs": outputs, "inputs": inputs, "device": device}


def resolve_input(payload: str) -> int | None:
    """Akzeptiert 'IN2', 'in 2', '2' oder einen konfigurierten Namen."""
    text = payload.strip()
    for idx, label in enumerate(INPUT_NAMES, 1):
        if text.casefold() == label.casefold():
            return idx
    m = re.fullmatch(r"(?:IN\s*)?([1-4])", text, re.IGNORECASE)
    return int(m.group(1)) if m else None


# ------------------------------------------------------------- Matrix-Link


class MatrixLink:
    """Haelt genau eine TCP-Verbindung zur Matrix und serialisiert Befehle."""

    def __init__(self, host: str, port: int, connect_timeout: float = 5.0):
        self.host = host
        self.port = port
        self.connect_timeout = connect_timeout
        self._sock: socket.socket | None = None
        self._lock = threading.Lock()
        self.connected = False

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
        self._sock = None
        self.connected = False

    def _connect(self) -> None:
        LOG.info("Verbinde zu %s:%s", self.host, self.port)
        sock = socket.create_connection((self.host, self.port),
                                        timeout=self.connect_timeout)
        sock.settimeout(0.3)
        self._drain(sock)          # Begruessungs-CRLF verwerfen
        self._sock = sock
        self.connected = True
        LOG.info("Verbindung steht")

    @staticmethod
    def _drain(sock: socket.socket) -> None:
        sock.settimeout(0.05)
        try:
            while sock.recv(65536):
                pass
        except (socket.timeout, BlockingIOError):
            pass
        finally:
            sock.settimeout(0.3)

    def send(self, command: str, quiet: float = 0.4,
             deadline: float = 5.0) -> str:
        """Sendet einen Befehl und liest, bis 'quiet' Sekunden nichts mehr kommt."""
        with self._lock:
            last_error: Exception | None = None
            for attempt in (1, 2):
                try:
                    if self._sock is None:
                        self._connect()
                    sock = self._sock
                    assert sock is not None
                    self._drain(sock)
                    sock.sendall((command + "\r\n").encode("ascii"))

                    buf = b""
                    started = time.monotonic()
                    last_data = started
                    while True:
                        try:
                            chunk = sock.recv(65536)
                            if not chunk:
                                raise ConnectionError("Gegenstelle hat geschlossen")
                            buf += chunk
                            last_data = time.monotonic()
                        except socket.timeout:
                            pass
                        now = time.monotonic()
                        if buf and now - last_data >= quiet:
                            break
                        if now - started >= deadline:
                            break
                    return buf.decode("utf-8", "replace")
                except (OSError, ConnectionError) as err:
                    last_error = err
                    LOG.warning("Befehl %r fehlgeschlagen (Versuch %d): %s",
                                command, attempt, err)
                    self.close()
                    if attempt == 1:
                        time.sleep(0.5)
            raise ConnectionError(str(last_error))


# ---------------------------------------------------------------- Discovery


def device_block(state: dict) -> dict:
    dev = state.get("device", {})
    mac = dev.get("mac") or "unknown"
    return {
        "identifiers": [f"ezcoo_mx44has2_{mac.replace(':', '')}"],
        "name": "EZCOO MX44HAS2",
        "manufacturer": "EZCOO",
        "model": "EZ-MX44HAS2 (HDMI 2.0 Matrix 4x4)",
        "sw_version": dev.get("firmware"),
        "configuration_url": f"http://{dev.get('ip')}" if dev.get("ip") else None,
    }


def uid_prefix(state: dict) -> str:
    mac = (state.get("device", {}).get("mac") or "unknown").replace(":", "")
    return f"ezcoo_{mac}"


def discovery_payloads(state: dict) -> list[tuple[str, dict]]:
    """Liefert (topic, payload)-Paare fuer MQTT Discovery."""
    dev = device_block(state)
    uid = uid_prefix(state)
    common = {
        "availability_topic": AVAIL_TOPIC,
        "payload_available": "online",
        "payload_not_available": "offline",
        "device": dev,
    }
    items: list[tuple[str, dict]] = []

    for i in range(1, 5):
        out_name = OUTPUT_NAMES[i - 1]

        items.append((
            f"{DISCOVERY_PREFIX}/select/{uid}/out{i}_source/config",
            {**common,
             "name": f"{out_name} Quelle",
             "unique_id": f"{uid}_out{i}_source",
             "state_topic": STATE_TOPIC,
             "value_template": "{{ value_json.outputs['%d'].source_name }}" % i,
             "command_topic": f"{BASE_TOPIC}/out{i}/source/set",
             "options": INPUT_NAMES,
             "icon": "mdi:video-input-hdmi"},
        ))

        items.append((
            f"{DISCOVERY_PREFIX}/switch/{uid}/out{i}_stream/config",
            {**common,
             "name": f"{out_name} Stream",
             "unique_id": f"{uid}_out{i}_stream",
             "state_topic": STATE_TOPIC,
             "value_template": "{{ value_json.outputs['%d'].stream }}" % i,
             "command_topic": f"{BASE_TOPIC}/out{i}/stream/set",
             "payload_on": "ON", "payload_off": "OFF",
             "state_on": "ON", "state_off": "OFF",
             "icon": "mdi:television-play"},
        ))

        items.append((
            f"{DISCOVERY_PREFIX}/binary_sensor/{uid}/out{i}_link/config",
            {**common,
             "name": f"{out_name} Display verbunden",
             "unique_id": f"{uid}_out{i}_link",
             "state_topic": STATE_TOPIC,
             "value_template": "{{ value_json.outputs['%d'].link }}" % i,
             "payload_on": "ON", "payload_off": "OFF",
             "device_class": "connectivity",
             "entity_category": "diagnostic"},
        ))

        in_name = INPUT_NAMES[i - 1]
        items.append((
            f"{DISCOVERY_PREFIX}/binary_sensor/{uid}/in{i}_signal/config",
            {**common,
             "name": f"{in_name} Signal",
             "unique_id": f"{uid}_in{i}_signal",
             "state_topic": STATE_TOPIC,
             "value_template": "{{ value_json.inputs['%d'].signal }}" % i,
             "payload_on": "ON", "payload_off": "OFF",
             "device_class": "connectivity",
             "icon": "mdi:hdmi-port"},
        ))

    # Optimistischer "alles auf eine Quelle"-Schalter (EZS OUT0 VS INy)
    items.append((
        f"{DISCOVERY_PREFIX}/select/{uid}/all_source/config",
        {**common,
         "name": "Alle Ausgaenge Quelle",
         "unique_id": f"{uid}_all_source",
         "command_topic": f"{BASE_TOPIC}/all/source/set",
         "options": INPUT_NAMES,
         "icon": "mdi:call-split"},
    ))

    for key, label, icon in (("firmware", "Firmware", "mdi:chip"),
                             ("ip", "IP-Adresse", "mdi:ip-network"),
                             ("mac", "MAC-Adresse", "mdi:ethernet")):
        items.append((
            f"{DISCOVERY_PREFIX}/sensor/{uid}/{key}/config",
            {**common,
             "name": label,
             "unique_id": f"{uid}_{key}",
             "state_topic": STATE_TOPIC,
             "value_template": "{{ value_json.device.%s }}" % key,
             "entity_category": "diagnostic",
             "icon": icon},
        ))

    items.append((
        f"{DISCOVERY_PREFIX}/binary_sensor/{uid}/link/config",
        {**common,
         "name": "Bridge-Verbindung",
         "unique_id": f"{uid}_bridge_link",
         "state_topic": STATE_TOPIC,
         "value_template": "{{ 'ON' if value_json.bridge.connected else 'OFF' }}",
         "payload_on": "ON", "payload_off": "OFF",
         "device_class": "connectivity",
         "entity_category": "diagnostic"},
    ))
    return items


# --------------------------------------------------------------------- Main


class Bridge:
    def __init__(self):
        self.link = MatrixLink(MATRIX_HOST, MATRIX_PORT)
        self.state: dict = {}
        self.stop = threading.Event()
        self.refresh_now = threading.Event()
        self._discovery_sent = False

        self.mqtt = mqtt.Client(
            **({"callback_api_version": mqtt.CallbackAPIVersion.VERSION1}
               if hasattr(mqtt, "CallbackAPIVersion") else {}),
            client_id="ezcoo-matrix-bridge",
        )
        if MQTT_USER:
            self.mqtt.username_pw_set(MQTT_USER, MQTT_PASSWORD or None)
        self.mqtt.will_set(AVAIL_TOPIC, "offline", qos=1, retain=True)
        self.mqtt.on_connect = self._on_connect
        self.mqtt.on_message = self._on_message

    # ------------------------------------------------------------- MQTT

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        if rc != 0:
            LOG.error("MQTT-Verbindung abgelehnt (rc=%s)", rc)
            return
        LOG.info("MQTT verbunden mit %s:%s", MQTT_HOST, MQTT_PORT)
        client.subscribe(f"{BASE_TOPIC}/+/source/set", qos=1)
        client.subscribe(f"{BASE_TOPIC}/+/stream/set", qos=1)
        client.publish(AVAIL_TOPIC, "online", qos=1, retain=True)
        self._discovery_sent = False
        self.refresh_now.set()

    def _on_message(self, client, userdata, msg):
        payload = msg.payload.decode("utf-8", "replace").strip()
        parts = msg.topic[len(BASE_TOPIC) + 1:].split("/")
        LOG.debug("MQTT %s = %r", msg.topic, payload)
        if len(parts) != 3:
            return
        target, kind, _ = parts
        try:
            if kind == "source":
                self._handle_source(target, payload)
            elif kind == "stream":
                self._handle_stream(target, payload)
        except Exception:
            LOG.exception("Befehl aus %s fehlgeschlagen", msg.topic)

    def _handle_source(self, target: str, payload: str) -> None:
        src = resolve_input(payload)
        if src is None:
            LOG.warning("Unbekannte Quelle %r", payload)
            return
        out = 0 if target == "all" else self._out_index(target)
        if out is None:
            return
        self._send(f"EZS OUT{out} VS IN{src}")

    def _handle_stream(self, target: str, payload: str) -> None:
        out = 0 if target == "all" else self._out_index(target)
        if out is None:
            return
        value = "ON" if payload.strip().upper() in ("ON", "TRUE", "1") else "OFF"
        self._send(f"EZS OUT{out} STREAM {value}")

    @staticmethod
    def _out_index(target: str) -> int | None:
        m = re.fullmatch(r"out([1-4])", target, re.IGNORECASE)
        if not m:
            LOG.warning("Unbekanntes Ziel %r", target)
            return None
        return int(m.group(1))

    def _send(self, command: str) -> None:
        LOG.info("-> %s", command)
        reply = self.link.send(command)
        LOG.debug("<- %r", reply.strip())
        self.refresh_now.set()

    # ------------------------------------------------------------ Polling

    def poll(self) -> None:
        try:
            raw = self.link.send("EZSTA", quiet=0.5, deadline=6.0)
        except ConnectionError as err:
            LOG.error("Status nicht lesbar: %s", err)
            self._publish_state(connected=False)
            return

        parsed = parse_status(raw)
        if len(parsed["outputs"]) != 4 or len(parsed["inputs"]) != 4:
            LOG.warning("Unvollstaendige Statusantwort (%d Ausgaenge, %d Eingaenge)",
                        len(parsed["outputs"]), len(parsed["inputs"]))
            return

        self.state = parsed
        if not self._discovery_sent:
            for topic, payload in discovery_payloads(parsed):
                self.mqtt.publish(topic, json.dumps(payload), qos=1, retain=True)
            self._discovery_sent = True
            LOG.info("MQTT-Discovery veroeffentlicht")
        self._publish_state(connected=True)

    def _publish_state(self, connected: bool) -> None:
        if not self.state:
            return
        payload = dict(self.state)
        payload["bridge"] = {"connected": connected, "host": MATRIX_HOST}
        self.mqtt.publish(STATE_TOPIC, json.dumps(payload), qos=1, retain=True)

    # --------------------------------------------------------------- Lauf

    def run(self) -> int:
        self.mqtt.connect_async(MQTT_HOST, MQTT_PORT, keepalive=60)
        self.mqtt.loop_start()
        try:
            while not self.stop.is_set():
                self.poll()
                # Nach einem Schaltbefehl sofort nachlesen statt zu warten
                if self.refresh_now.wait(timeout=POLL_INTERVAL):
                    self.refresh_now.clear()
                    time.sleep(0.4)
        finally:
            LOG.info("Beende Bridge")
            self.mqtt.publish(AVAIL_TOPIC, "offline", qos=1, retain=True)
            time.sleep(0.3)
            self.mqtt.loop_stop()
            self.mqtt.disconnect()
            self.link.close()
        return 0

    def shutdown(self, *_args) -> None:
        self.stop.set()
        self.refresh_now.set()


def main() -> int:
    logging.basicConfig(
        level=getattr(logging, (_env("LOG_LEVEL", "info") or "info").upper(),
                      logging.INFO),
        format="%(asctime)s %(levelname)-7s %(message)s",
        stream=sys.stdout,
    )
    if not MATRIX_HOST:
        LOG.error("matrix_host ist nicht gesetzt. Bitte die IP-Adresse der Matrix "
                  "in der Add-on-Konfiguration eintragen.")
        return 1
    LOG.info("EZCOO Matrix Bridge - Matrix %s:%s, MQTT %s:%s, Poll %ss",
             MATRIX_HOST, MATRIX_PORT, MQTT_HOST, MQTT_PORT, POLL_INTERVAL)
    bridge = Bridge()
    signal.signal(signal.SIGTERM, bridge.shutdown)
    signal.signal(signal.SIGINT, bridge.shutdown)
    return bridge.run()


if __name__ == "__main__":
    sys.exit(main())
