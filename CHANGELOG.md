# Changelog

## Card 1.1.0 - Juli 2026

- Visueller Konfigurations-Editor fuer die Stundenplan Card: Entity-Auswahl, Ansicht-Dropdown (Woche/Heute), Pausen-Toggle und Titelfeld direkt im Dashboard-Editor, kein YAML noetig

## 1.2.0 - Juli 2026

### Neu
- Fuenfter Sensor "Wochenplan" pro Kind: State = Wochenstundenzahl, Attribute = kompletter Plan (Raster, Faecher, Bloecke) fuer die Lovelace-Karte
- Stundenplan Card (dist/stundenplan-card.js, via HACS als Dashboard-Repo installierbar): Wochenansicht mit Fachfarben, Pausen, Hervorhebung des heutigen Tags und der laufenden Stunde; Heute-Modus als kompakte Liste; Betriebsphasen-Banner im Blockmodus; nutzt HA-Theme-Variablen (hell/dunkel)

## 1.1.3 - Juli 2026

### Neu
- Druckoption pro Kind: heller A4-Querformat-Ausdruck mit vollen Fachnamen, Raeumen, Pausen und dezenten Fachfarben; im Blockmodus werden die Blockzeitraeume unter dem Plan aufgelistet

## 1.1.2 - Juli 2026

### Behoben
- Zeiteingabe im Stundenraster: Eingabefeld verlor bei jeder Ziffer den Fokus, weil das Panel komplett neu gerendert wurde. Zeitaenderungen aktualisieren jetzt nur noch gezielt die Plan-Tabelle und die Kurzinfos - der Editor bleibt stehen, der Collapse bleibt offen

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
