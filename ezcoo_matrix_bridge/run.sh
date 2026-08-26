#!/usr/bin/with-contenv bashio
set -e

bashio::config.require 'matrix_host' "Ohne die IP-Adresse der Matrix kann die Bridge nicht starten."

export MATRIX_HOST="$(bashio::config 'matrix_host')"
export MATRIX_PORT="$(bashio::config 'matrix_port')"
export POLL_INTERVAL="$(bashio::config 'poll_interval')"
export BASE_TOPIC="$(bashio::config 'base_topic')"
export DISCOVERY_PREFIX="$(bashio::config 'discovery_prefix')"
export LOG_LEVEL="$(bashio::config 'log_level')"

# Listen als Pipe-getrennte Strings weiterreichen
export INPUT_NAMES="$(jq -r '[.input_names // [] | .[]] | join("|")' /data/options.json)"
export OUTPUT_NAMES="$(jq -r '[.output_names // [] | .[]] | join("|")' /data/options.json)"

# MQTT: eigene Angaben haben Vorrang, sonst der Broker aus dem Supervisor
if bashio::config.has_value 'mqtt_host'; then
    export MQTT_HOST="$(bashio::config 'mqtt_host')"
    export MQTT_PORT="$(bashio::config 'mqtt_port' || echo 1883)"
    export MQTT_USER="$(bashio::config 'mqtt_user' || echo '')"
    export MQTT_PASSWORD="$(bashio::config 'mqtt_password' || echo '')"
    bashio::log.info "Nutze konfigurierten MQTT-Broker ${MQTT_HOST}:${MQTT_PORT}"
elif bashio::services.available 'mqtt'; then
    export MQTT_HOST="$(bashio::services 'mqtt' 'host')"
    export MQTT_PORT="$(bashio::services 'mqtt' 'port')"
    export MQTT_USER="$(bashio::services 'mqtt' 'username')"
    export MQTT_PASSWORD="$(bashio::services 'mqtt' 'password')"
    bashio::log.info "Nutze MQTT-Broker aus dem Supervisor: ${MQTT_HOST}:${MQTT_PORT}"
else
    bashio::exit.nok "Kein MQTT-Broker gefunden. Mosquitto-Add-on installieren oder mqtt_host setzen."
fi

bashio::log.info "Starte EZCOO Matrix Bridge fuer ${MATRIX_HOST}:${MATRIX_PORT}"
exec python3 /ezcoo_bridge.py
