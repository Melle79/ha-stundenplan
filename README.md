# Stundenplan Manager

Home Assistant Add-on zur Verwaltung der Stundenpläne mehrerer Kinder – inklusive Blockunterricht-Unterstützung für Berufsschüler, MQTT-Discovery-Sensoren und Lovelace-Karte.

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-melle79-yellow)](https://buymeacoffee.com/melle79)

## Features

- Beliebig viele Kinder mit eigenem Wochenplan (Mo–Fr), Web-UI mit Auto-Save
- 21 vordefinierte Standard-Schulfächer, eigene Fächer mit Farben, Kürzeln und Räumen
- Konfigurierbares Stundenraster (Standard + pro Kind überschreibbar), Pausen automatisch aus Rasterlücken
- **Blockunterricht-Modus**: Blockzeiträume pflegen, außerhalb zeigen Sensoren und Karte „Betrieb"
- Druckansicht (A4 quer) mit vollen Fachnamen, Räumen und Pausen
- **5 MQTT Discovery Sensoren pro Kind**: Aktuelle Stunde, Nächste Stunde, Erste Stunde morgen, Schulschluss heute, Wochenplan (mit kompletten Plandaten als Attribute)
- Lovelace-Karte mit Wochen- und Heute-Ansicht sowie visuellem Editor

## Installation

1. In Home Assistant: **Einstellungen → Add-ons → Add-on Store → ⋮ → Repositories**
2. `https://github.com/Melle79/ha-stundenplan` hinzufügen
3. „Stundenplan Manager" installieren und starten

## Lovelace-Karte

Die Stundenplan Card zeigt Wochen- oder Tagesansicht direkt im Dashboard – mit Fachfarben, Pausen, Hervorhebung der laufenden Stunde und Betriebsphasen-Banner im Blockmodus. Sie ist rein sensorbasiert und funktioniert daher auch extern via Nabu Casa.

### Installation (empfohlen: über das Add-on)

Das Add-on kopiert die Karte beim Start automatisch nach `/config/www/stundenplan-card.js` – Karten-Updates kommen damit automatisch mit jedem Add-on-Update. Einmalig registrieren:

Ab v1.3.0 registriert das Add-on die Dashboard-Ressource automatisch (inkl. Versions-Cache-Buster) - es ist nichts weiter zu tun. Nach einem Karten-Update genuegt ein normaler Browser-Reload. Nur bei Dashboards im YAML-Modus muss die Ressource manuell eingebunden werden (Hinweis erscheint im Add-on-Log).

### Alternativ: Installation via HACS

1. HACS → ⋮ → Benutzerdefinierte Repositories
2. Repository: `https://github.com/Melle79/ha-stundenplan`, Kategorie: **Dashboard**
3. „Stundenplan Card" herunterladen

### Konfiguration

Über den visuellen Editor („Karte hinzufügen" → „Stundenplan Card") oder per YAML:

Der Editor listet alle gefundenen Kinder als Checkboxen - einfach anhaken. Kein Haken = alle Kinder automatisch. Bei mehreren Kindern erscheinen Umschalt-Chips in der Karte. Per YAML:

```yaml
type: custom:stundenplan-card
entities:                # weglassen = alle Kinder automatisch
  - sensor.stundenplan_max_wochenplan
layout: tabs             # tabs | untereinander (bei mehreren Kindern)
modus: woche             # woche | heute | schulschluss
schrift: normal          # normal | gross
zeige_pausen: true
titel: ""                # optional, Standard: "Stundenplan {Name}"
```

## Schulferien-Integration

In der Web-UI unter **Einstellungen -> Schulferien-Integration** den Kalender-Sensor des Schulferien & Feiertage Managers auswaehlen (alle Ferien und Feiertage in einer Entity - ein Feld genuegt). Alternativ werden die Einzelsensoren "Naechste Schulferien" und "Naechster Feiertag" unterstuetzt. Die Karte markiert alle schulfreien Tage mit Grund - auch beim Blaettern weit in die Zukunft.

An schulfreien Tagen zeigen die Sensoren dann „Schulfrei (Grund)" und die Karte ein Ferien-Banner. Kinder im Blockmodus sind bewusst ausgenommen (Azubis haben in Schulferien Betrieb).

## Schulmanager Online (optional)

Mit der HACS-Integration [Schulmanager-homeassistant](https://github.com/MrIcemanLE/Schulmanager-homeassistant) laesst sich pro Kind ein Schulmanager-Schueler verknuepfen (Dropdown im Kind-Panel):

- **Plan-Import**: Wochenplan samt Stundenraster per Knopfdruck uebernehmen, Faecher werden automatisch angelegt
- **Vertretungs-Overlay**: Entfall und Vertretungen (heute/morgen) werden in der Karte markiert und im Morgen-Push gewarnt

## Morgen-Push & Materialliste (optional)

In den Einstellungen laesst sich ein taeglicher Push aktivieren (Uhrzeit + Geraet waehlbar, Test-Button): "Luna: Sport um 08:00, Schluss 13:10 - Sportbeutel". An freien Tagen wird nichts gesendet. Im Faecher-Tab kann pro Fach optional Material hinterlegt werden - es erscheint im Push, am Sensor 'Erste Stunde morgen' (Attribut material_morgen) und in der Heute-Ansicht der Karte.
