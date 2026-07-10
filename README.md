# Stundenplan Manager

Home Assistant Add-on zur Verwaltung der Stundenpläne mehrerer Kinder – inklusive Blockunterricht-Unterstützung für Berufsschüler, MQTT-Discovery-Sensoren und Lovelace-Karte.

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-melle79-yellow)](https://buymeacoffee.com/melle79)

## Features (v1.0.0)

- Beliebig viele Kinder mit eigenem Wochenplan (Mo–Fr)
- Fächer mit Farben und Kürzeln
- Konfigurierbares Stundenraster (Standard + pro Kind überschreibbar)
- **Blockunterricht-Modus**: Blockzeiträume pflegen, außerhalb zeigt der Sensor „Betrieb"
- MQTT Discovery Sensoren pro Kind: aktuelle Stunde, nächste Stunde, erste Stunde morgen, Schulschluss heute
- Tägliches automatisches Backup

## Installation

1. In Home Assistant: **Einstellungen → Add-ons → Add-on Store → ⋮ → Repositories**
2. `https://github.com/Melle79/ha-stundenplan` hinzufügen
3. „Stundenplan Manager" installieren und starten

## Geplant (v1.1+)

- Integration mit dem [Schulferien & Feiertage Manager](https://github.com/Melle79) (Sensor zeigt „Schulfrei" an Ferientagen)
- Morgen-Push-Benachrichtigung
- Materialliste pro Fach
- Lovelace-Karte via HACS
