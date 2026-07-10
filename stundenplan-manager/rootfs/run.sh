#!/usr/bin/with-contenv bashio

export LOG_LEVEL=$(bashio::config 'log_level')
export BACKUP_ZEIT=$(bashio::config 'backup_zeit')
export BACKUP_ANZAHL=$(bashio::config 'backup_anzahl')

if bashio::services.available "mqtt"; then
    export MQTT_HOST=$(bashio::services "mqtt" "host")
    export MQTT_PORT=$(bashio::services "mqtt" "port")
    export MQTT_USER=$(bashio::services "mqtt" "username")
    export MQTT_PASSWORD=$(bashio::services "mqtt" "password")
    bashio::log.info "MQTT-Broker gefunden: ${MQTT_HOST}:${MQTT_PORT}"
else
    bashio::log.warning "Kein MQTT-Service verfuegbar - Sensoren werden nicht publiziert"
fi

export DATA_DIR=/data

if [ -d /homeassistant ]; then
    mkdir -p /homeassistant/www
    cp /card/stundenplan-card.js /homeassistant/www/stundenplan-card.js
    bashio::log.info "Stundenplan Card nach /config/www kopiert (Ressource: /local/stundenplan-card.js)"
fi

bashio::log.info "Starte Stundenplan Manager..."
cd /app
exec python3 -m server
