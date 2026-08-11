# Stundenplan Manager

Home Assistant Add-on zur Verwaltung der Stundenpläne mehrerer Kinder – inklusive Blockunterricht-Unterstützung für Berufsschüler, MQTT-Discovery-Sensoren und Lovelace-Karte.

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-melle79-yellow)](https://buymeacoffee.com/melle79)

> 📖 Ausführliche Schritt-für-Schritt-Anleitung: **[HANDBUCH.md](HANDBUCH.md)**

![Wochenansicht der Stundenplan Card mit Vertretung und Entfall](docs/img/woche.png)

## Features

- Beliebig viele Kinder mit eigenem Wochenplan (Mo–Fr), Web-UI mit Auto-Save
- 21 vordefinierte Standard-Schulfächer, eigene Fächer mit Farben, Kürzeln und Räumen
- Konfigurierbares Stundenraster (Standard + pro Kind überschreibbar), Pausen automatisch aus Rasterlücken
- **Datenquellen** (optional, pro Kind): **Schulmanager Online** und **Eltern-Portal** – Plan-Import per Knopfdruck oder täglicher Auto-Import
- **Vertretungen & Entfall** (Schulmanager): Overlay auf der Karte; entfallene Randstunden verschieben Schulbeginn/-schluss
- **Lehrer-Klarnamen**: Kürzel zu vollen Namen auflösen (von Hand oder automatisch vom Eltern-Portal), Anzeige auf der Karte nach Platz
- **Blockunterricht-Modus**: Blockzeiträume pflegen, außerhalb zeigen Sensoren und Karte „Betrieb"
- Druckansicht (A4 quer) mit vollen Fachnamen, Räumen und Pausen
- **5 MQTT Discovery Sensoren pro Kind**: Aktuelle Stunde, Nächste Stunde, Erste Stunde morgen, Schulschluss heute, Wochenplan (mit kompletten Plandaten als Attribute)
- Lovelace-Karte mit Wochen-, Heute- und Schulschluss-Ansicht sowie visuellem Editor

## Installation

1. In Home Assistant: **Einstellungen → Add-ons → Add-on Store → ⋮ → Repositories**
2. `https://github.com/Melle79/ha-stundenplan` hinzufügen
3. „Stundenplan Manager" installieren und starten

## Lovelace-Karte

Die Stundenplan Card zeigt Wochen-, Tages- oder Schulschluss-Ansicht direkt im Dashboard – mit Fachfarben, Pausen, Hervorhebung der laufenden Stunde und Betriebsphasen-Banner im Blockmodus. Sie ist rein sensorbasiert und funktioniert daher auch extern via Nabu Casa.

Die **Heute-Ansicht** listet den Tag mit Räumen und Lehrer-Klarnamen, Vertretungen, Entfall, Material und Hausaufgaben:

![Heute-Ansicht mit Lehrer-Klarnamen, Vertretung und Entfall](docs/img/heute.png)

Die **Schulschluss-Ansicht** fasst für alle Kinder zusammen, wie lange die Schule heute geht – entfallene Randstunden verschieben das Ende:

![Schulschluss-Ansicht für mehrere Kinder](docs/img/schulschluss.png)

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

- **Plan-Import**: Wochenplan samt Stundenraster per Knopfdruck uebernehmen, Faecher werden automatisch angelegt. Es werden nur befuellte Tage ersetzt (inkrementeller Import moeglich); vor jedem Import entsteht ein Snapshot, der Import laesst sich per Knopfdruck rueckgaengig machen. Taegliche Backups nach /data/backups (Optionen backup_zeit/backup_anzahl). Optional laesst sich pro Kind ein taeglicher Auto-Import aktivieren (Default 06:30, 07:00 und 07:15 Uhr, Liste via auto_import_zeiten)
- **Vertretungs-Overlay**: Entfall und Vertretungen (heute/morgen) werden in der Karte markiert und im Morgen-Push gewarnt. Entfallene Rand­stunden verschieben Schulbeginn und Schulschluss - Sensoren, Karte und Push zeigen das echte Ende ("noch bis 11:20 · statt 15:00")
- **Lehrer-Klarnamen**: Pro Kind lassen sich unter „👩‍🏫 Lehrernamen" die Kürzel zu vollen Namen auflösen (von Hand pflegbar). Das Eltern-Portal füllt sie automatisch, Schulmanager liefert nur Kürzel. Die Karte zeigt den Klarnamen, sobald genug Platz ist, sonst das Kürzel. Kürzel, die im aktuellen Plan nicht mehr vorkommen, werden als „nicht mehr im Plan" markiert und sind per ✕ von Hand löschbar
- **Hausaufgaben & Klassenarbeiten**: Offene Hausaufgaben (Todo-Liste) und die naechste Arbeit erscheinen in Heute-/Schulschluss-Ansicht und im Morgen-Push

## Eltern-Portal (optional)

Alternativ zu Schulmanager lässt sich pro Kind ein Kind aus dem [Eltern-Portal](https://eltern-portal.org) verknüpfen (HACS-Integration [workFLOw42/Elternportal_API](https://github.com/workFLOw42/Elternportal_API)). Import, Auto-Import und Statusbox funktionieren identisch; das Eltern-Portal liefert zusätzlich Fachnamen, Räume und die **Klarnamen der Lehrkräfte** (füllt das Lehrerverzeichnis automatisch) sowie anstehende Arbeiten. Vertretungen und Hausaufgaben liefert das Eltern-Portal nicht. Details siehe [HANDBUCH.md](HANDBUCH.md#datenquellen).

## Morgen-Push & Materialliste (optional)

In den Einstellungen laesst sich ein taeglicher Push aktivieren (Uhrzeit + Geraet waehlbar, Test-Button): "Luna: Sport um 08:00, Schluss 13:10 - Sportbeutel". An freien Tagen wird nichts gesendet. Im Faecher-Tab kann pro Fach optional Material hinterlegt werden - es erscheint im Push, am Sensor 'Erste Stunde morgen' (Attribut material_morgen) und in der Heute-Ansicht der Karte.
