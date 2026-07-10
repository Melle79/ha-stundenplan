# Changelog

## 1.6.0 - Juli 2026 (Card 1.7.0)

### Verbessert
- Ferien-Integration auf Zeitraum-Sensoren umgestellt: statt heute/morgen-Binaersensoren jetzt 'Naechste Schulferien' (beginn/ende + laufende Ferien) und 'Naechster Feiertag' (Datum + 14-Tage-Vorschau)
- Die Karte markiert damit ALLE schulfreien Tage der Woche (z.B. Feiertag am Donnerstag schon montags sichtbar, Ferienwochen komplett gedimmt), jeweils mit Grund im Spaltenkopf
- Sensoren zeigen 'Schulfrei (Grund)' fuer beliebige Tage, inkl. 'Erste Stunde morgen' am Vorabend eines Feiertags
- Bestehende Konfiguration mit Binaersensoren wird automatisch auf die Zeitraum-Sensoren migriert (gleicher Geraete-Praefix)

## 1.5.2 - Juli 2026 (Card 1.6.1)

- Fix: Heute-Punkt im Spaltenkopf steht jetzt direkt hinter dem Tageskuerzel statt verloren unter dem Schulfrei-Vermerk

## 1.5.1 - Juli 2026 (Card 1.6.0)

- Schulfrei-Anzeige direkt am Tag statt Banner: Spaltenkopf zeigt klein den Grund (z.B. Sommerferien), die Stunden des freien Tags werden gedimmt; gilt fuer heute und morgen. Die Markierung der laufenden Stunde pausiert an freien Tagen. Heute-Modus zeigt weiterhin den Ferien-Hinweis

## 1.5.0 - Juli 2026

### Verbessert
- Schulferien-Integration jetzt direkt in der Web-UI unter Einstellungen konfigurierbar: Dropdowns mit automatisch gefundenen schulfrei-Sensoren (binary_sensor mit schulfrei/ferien/feiertag/holiday im Namen) statt Entity-IDs in den Add-on-Optionen
- Bereits gesetzte Add-on-Optionen ferien_heute/ferien_morgen werden beim ersten Start automatisch in die App-Einstellungen uebernommen

## 1.4.0 - Juli 2026 (Card 1.5.0)

### Neu
- Schulferien-Integration: Zwei neue Add-on-Optionen ferien_heute / ferien_morgen (binary_sensor-Entities des Schulferien & Feiertage Managers, z.B. binary_sensor.schulferien_bayern_heute_schulfrei). Bei schulfrei zeigen die Sensoren "Schulfrei (Grund)" - inkl. Erste Stunde morgen am letzten Ferientag
- Karte zeigt an schulfreien Tagen ein Ferien-Banner (Wochenansicht) bzw. nur den Ferien-Hinweis (Heute-Modus)
- Blockmodus ignoriert Schulferien bewusst: Azubis haben in den Ferien Betrieb
- Ohne konfigurierte Entities verhaelt sich alles unveraendert; Abfrage via HA-REST-API mit 60s-Cache

## 1.3.0 - Juli 2026

### Neu
- Automatische Lovelace-Ressourcen-Registrierung: Das Add-on registriert /local/stundenplan-card.js?v={Kartenversion} beim Start selbst ueber die HA-API und aktualisiert die Version nach jedem Karten-Update - kein manuelles ?v=X-Hochzaehlen mehr, nur noch normaler Browser-Reload
- Bestehende /local-Ressourcen (auch mit altem ?v=) werden erkannt und aktualisiert; bei YAML-Dashboards erscheint ein Hinweis im Log

## 1.2.6 - Juli 2026 (Card 1.4.0)

- Tabs/Chips generell groesser (.92rem, mehr Padding)
- Neue Editor-Option 'Schriftgroesse' (Normal/Gross): skaliert die gesamte Karte - Tabs, Wochentage, Fachbloecke, Zeiten, Kindernamen, Heute-Liste

## 1.2.5 - Juli 2026 (Card 1.3.1)

- Layout 'untereinander': Kindernamen deutlich groesser (1.35rem, fett) und nach rechts eingerueckt, buendig mit den Wochentag-Spalten

## 1.2.4 - Juli 2026 (Card 1.3.0)

### Neu
- Layout-Option fuer mehrere Kinder: Tabs (Chips) oder alle untereinander mit Namens-Ueberschriften - waehlbar im Editor
- Deutlichere Markierung der laufenden Stunde: farbige Pill in der Zeitspalte zusaetzlich zum Glow um die Fachzelle; laufende Pausen werden ebenfalls hervorgehoben (mit Hinweis 'laeuft')

## 1.2.3 - Juli 2026 (Card 1.2.1)

### Design-Ueberarbeitung der Karte
- Luft zwischen den Fachbloecken (4px Abstand, abgerundete Bloecke mit mehr Hoehe) statt gequetschter Streifen
- Zeitspalte fix schmal (54px) - kein riesiger Leerraum mehr auf breiten Dashboards
- Auf breiten Karten (ab 620px) wird der volle Fachname unter dem Kuerzel eingeblendet (Container Query)
- Pausen als klar lesbare Trennzeile mit gestrichelten Linien links und rechts
- Freie Stunden als dezente Platzhalter-Flaechen statt Gedankenstrich
- Heutiger Tag: Punkt-Markierung im Spaltenkopf, laufende Stunde mit sanftem Glow

## 1.2.2 - Juli 2026 (Card 1.2.0)

- Editor findet Wochenplan-Sensoren automatisch und zeigt die Kinder als Checkbox-Liste zum Anhaken (statt Entity-Suchfeld)
- Mehrere Kinder in einer Karte: Umschalt-Chips mit den Namen oben in der Karte
- Ohne Konfiguration zeigt die Karte automatisch alle gefundenen Kinder
- entity (alt) wird automatisch zu entities migriert, bestehende Konfigurationen laufen weiter

## 1.2.1 - Juli 2026

- Add-on liefert die Stundenplan Card jetzt selbst aus: beim Start wird sie nach /config/www kopiert, einmalig als Ressource /local/stundenplan-card.js registrieren - Karten-Updates kommen dann automatisch mit jedem Add-on-Update (HACS weiterhin als Alternative moeglich)
- README ueberarbeitet (Karten-Doku war zuvor durch stilles Replace-Fehlschlagen nicht gelandet)

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
