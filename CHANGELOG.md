# Changelog

## 1.1.1 - Juli 2026

- Pausen werden im Wochenplan-Raster dezent als schmale Trennzeilen angezeigt (mit Uhrzeit und Dauer)

## 1.1.0 - Juli 2026

### Neu
- MQTT Discovery Sensoren pro Kind: Aktuelle Stunde, Naechste Stunde, Erste Stunde morgen, Schulschluss heute
- Zustaende: Fach mit Kuerzel und Raum-Attributen, Pause, Kein Unterricht, Schulfrei (Wochenende/leerer Tag), Betrieb (Blockmodus ausserhalb der Bloecke)
- Sensoren aktualisieren sich alle 30s und sofort nach jeder Aenderung in der Web-UI
- Availability-Topic mit Last Will (Sensoren werden bei Add-on-Stopp als nicht verfuegbar markiert)
- Aufgeraeumte Entfernung: geloeschte Kinder verschwinden auch aus HA

## 1.0.3 - Juli 2026

- Auto-Save: Aenderungen werden automatisch gespeichert (0,8s nach letzter Eingabe, sofort bei Tab-/Seitenwechsel via sendBeacon)
- Fehlerbehandlung: bei fehlgeschlagenem Speichern automatischer Neuversuch nach 3s

## 1.0.2 - Juli 2026

- Fach-Kuerzel nachtraeglich editierbar (mit Kollisionspruefung, Plaene werden automatisch migriert)

## 1.0.1 - Juli 2026

- Aufraeumen: __pycache__ aus Repo entfernt, .gitignore ergaenzt
- Version-Bump, damit HA das Add-on neu baut (einklappbares Stundenraster + Standard-Faecher werden damit sichtbar)

## 1.0.0 - Juli 2026

- Erste Version: Add-on-Grundstruktur, Web-UI, Blockunterricht-Datenmodell
