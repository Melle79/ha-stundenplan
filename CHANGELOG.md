# Changelog

## 1.15.0 - Juli 2026

### Neu (Web-UI)
- Wochenplan-Raster zeigt Raum und Lehrer klein in jeder Stunde
- Statusbox 'Schulmanager heute/morgen' im Kind-Panel: Aenderungen (Entfall rot, Vertretung orange - betroffene Stunden werden auch direkt im Raster markiert), faellige Hausaufgaben und anstehende Arbeiten
- Einstellungs-Card 'Schulmanager Auto-Import': Import-Zeiten als Komma-Liste direkt in der Web-UI einstellbar (mit Validierung)

### Behoben
- Versions-Bump fehlte im vorigen Patch, daher bot Home Assistant kein Update an

## 1.14.4 - Juli 2026

### Verbessert
- Import baut den Stammplan jetzt primaer aus den originalbereinigten Tages-Sensoren (heute/morgen): Bei Fach-Vertretungen landet das Original-Fach im Plan statt des Vertretungsfachs, Entfall-Stunden behalten ihr Stammfach. Der Wochenplan-JSON dient nur noch als Basis-Geruest
- Damit setzt sich der Original-Stundenplan per Auto-Import Tag fuer Tag ueber die Woche zusammen - auch wenn die Schule (wie bei Luna) keinen Wochenplan pflegt, sondern nur den jeweils naechsten Tag

## 1.14.3 - Juli 2026

### Behoben
- Altlasten-Heilung: Importe vor v1.14.2 konnten Vertretungswerte (Springer-Lehrer, Ausweichraum) als regulaere Fach-Daten speichern. Eine einmalige Migration markiert Bestandswerte als Schulmanager-gelernt, sodass der naechste Import sie aus den original-Daten korrigiert (z.B. Physik zurueck auf 'Ph 2 / her' statt '126 / rei')
- Stundentyp 'changedLesson' (Geaenderter Unterricht) wird jetzt ueberall erkannt

## 1.14.2 - Juli 2026

### Verbessert
- Raum/Lehrer-Lernen ist jetzt vertretungssicher: Nur regulaere Stunden werden ausgewertet; bei Vertretungen wird der regulaere Stand aus den original-Daten gelernt statt Springer-Lehrer oder Ausweichraum zu uebernehmen
- Selbstpflegender Stundenplan: Aus Schulmanager gelernte Raeume/Lehrer werden bei regulaeren Aenderungen (z.B. Raumwechsel zum Halbjahr) automatisch aktualisiert - handgepflegte Werte gewinnen dagegen immer (Herkunfts-Merker sm_raum/sm_lehrer je Fach)

## 1.14.1 - Juli 2026

- Auto-Import laeuft jetzt mehrmals morgens vor Schulbeginn: 06:30, 07:00 und 07:15 Uhr (statt einmal 05:30) - so werden auch Vertretungen erfasst, die das Sekretariat erst am Morgen eintraegt. Konfigurierbar als Liste ueber auto_import_zeiten; jeder Zeitpunkt laeuft genau einmal pro Tag

## 1.14.0 - Juli 2026

### Neu
- Optionaler Auto-Import: Pro Kind aktivierbare Checkbox - der Schulmanager-Plan wird taeglich (Default 05:30, einstellbar via auto_import_zeit) automatisch uebernommen. Gleiche Regeln wie der Button: nur befuellte Tage, Raum/Lehrer nur ergaenzen, eigenes Stundenraster bleibt unangetastet; vor Aenderungen entsteht ein Backup (autoimport-Prefix)

### Verbessert
- Import-Logik ins Backend verlagert (sync.py): Button und Auto-Import nutzen exakt dieselbe Merge-Funktion (Single Source of Truth), der Import landet immer in der aktuell gueltigen Planversion

## 1.13.0 - Juli 2026 (Card 1.14.0)

### Neu
- Faecher haben ein optionales Lehrer-Feld (Faecher-Tab); Karte zeigt Raum und Lehrer in der Wochenzelle ('126 - rei') und in der Heute-Liste
- Schulmanager-Import uebernimmt Raum, Lehrer und vollen Fachnamen aus den Stundenplan-heute/morgen-Sensoren: Neue Faecher heissen 'Physik' statt 'Ph' und sind komplett befuellt; bei bestehenden Faechern werden nur leere Felder ergaenzt (nichts wird ueberschrieben). Da die Quelle nur heute/morgen abdeckt, vervollstaendigen sich die Angaben ueber mehrere Importe inkrementell

## 1.12.1 - Juli 2026 (Card 1.13.1)

### Behoben
- Vertretungs-Overlay zeigt jetzt alle gelieferten Details: Lehrerkuerzel und Grund werden uebernommen ('Geaenderter Unterricht - Ph - rei - 126'), der Aenderungstyp wird wie von der Integration geliefert angezeigt (die Integration lokalisiert bereits auf Deutsch, das englische Code-Mapping griff daher nie)
- Entfall-Erkennung robust fuer deutsche und englische Typbezeichnungen; Grund/Notiz erscheint im Tooltip und im Morgen-Push

## 1.12.0 - Juli 2026 (Card 1.13.0)

### Neu
- Klassenarbeiten direkt im Stundenplan: Die Wochenansicht markiert Arbeiten am Tag (roter Vermerk im Spaltenkopf, z.B. '📝 M' mit Typ als Tooltip) und umrandet die passende Fachstunde - beim Blaettern in kuenftige Wochen inklusive
- Heute-Ansicht listet alle Arbeiten der naechsten 14 Tage (statt nur der naechsten), Quelle: upcoming_exams des Schulmanager-Sensors

## 1.11.2 - Juli 2026

### Behoben
- Hausaufgaben-Liste blieb leer: Die Schulmanager-Todo-Eintraege haben kein due-Feld (supported_features 4), das Datum steht im Titel ('[2026-07-13] Mathe: ...'). Das Datum wird jetzt aus dem Titel geparst (ISO- und deutsches Format), das Praefix fuer die Anzeige entfernt
- Ueberfaellige Aufgaben werden auf die letzten 7 Tage begrenzt (Push: 3 Tage), damit alte nie abgehakte Eintraege die Anzeige nicht fluten

## 1.11.1 - Juli 2026 (Card 1.12.1)

### Neu
- Konkrete Hausaufgaben statt nur Anzahl: Die Heute-Ansicht listet demnaechst faellige Aufgaben (bis 3 Tage voraus, ueberfaellige rot markiert) mit Faelligkeits-Label (heute/morgen/Wochentag). Quelle: todo.get_items der Schulmanager-Todo-Liste
- Morgen-Push nennt die bis morgen faelligen Aufgaben beim Namen ('Bis morgen: Mathe AB S. 12; Englisch Vokabeln' + Zaehler bei mehr als drei) statt nur der Gesamtzahl

## 1.11.0 - Juli 2026 (Card 1.12.0)

### Neu (nur bei Schulmanager-Verknuepfung, optional)
- Offene Hausaufgaben: Anzahl aus der Schulmanager-Todo-Liste in der Heute-Ansicht, als Badge in der Schulschluss-Ansicht, im Morgen-Push und als Sensor-Attribut hausaufgaben_offen
- Naechste Klassenarbeit: Heute-Ansicht zeigt anstehende Arbeiten (bis 14 Tage im Voraus, z.B. 'Schulaufgabe Mathematik in 3 Tagen'), der Morgen-Push warnt am Vorabend ('Schulaufgabe Mathematik morgen!'), Sensor-Attribut naechste_arbeit
- Wochenansicht bleibt bewusst clean (nur der Plan); Noten werden bewusst nicht angezeigt

## 1.10.1 - Juli 2026

### Neu
- Backup-System: Die seit v1.0.0 vorhandenen Add-on-Optionen backup_zeit/backup_anzahl sind jetzt tatsaechlich implementiert - taegliches Backup der Daten nach /data/backups mit Rotation, dazu Endpoints /api/backups, /api/backup/snapshot und /api/backup/restore (mit Dateinamen-Validierung)
- Schulmanager-Import uebernimmt nur in Schulmanager befuellte Tage - leere Tage bleiben unangetastet. Damit laesst sich der Plan inkrementell fuellen, wenn die Integration (Option schedule_weeks) nur wenige Tage liefert
- Import rueckgaengig: Vor jedem Import wird automatisch ein Server-Snapshot angelegt; der Button 'Import rueckgaengig' stellt den kompletten Vorher-Stand wieder her (bis zum Neuladen der Seite, danach greifen die Backups)

### Behoben
- Race-Condition beim Import-Undo: Ein noch laufender Auto-Save-Timer haette den Import-Stand nach dem Restore erneut speichern koennen

## 1.10.0 - Juli 2026 (Card 1.11.0)

### Neu: Schulmanager-Online-Anbindung (optional)
- Voraussetzung: HACS-Integration MrIcemanLE/Schulmanager-homeassistant - der Stundenplan-Manager konsumiert deren Entities, keine eigenen Zugangsdaten noetig
- Verknuepfung pro Kind: Dropdown 'Schulmanager' im Kind-Panel (automatisch gefundene Schueler)
- Plan-Import: Button 'Plan importieren' uebernimmt den Wochenplan aus dem Wochenplan-JSON-Sensor in die gewaehlte Planversion; unbekannte Faecher werden mit Farbpalette angelegt, vorhandene Kuerzel (case-insensitive) wiederverwendet, Stundenraster optional als kind-eigenes Raster uebernommen
- Vertretungs-Overlay in der Karte: Entfall durchgestrichen und gedimmt, Vertretung/Lehrerwechsel/Sonderstunde mit gestricheltem Rahmen und Detail-Badge (Fach, Raum) - in Wochen- und Heute-Ansicht, fuer heute und morgen
- Morgen-Push warnt bei Aenderungen: '5. Std Vertretung Mathe (Raum 204)'
- Gekapselt in eigenem Adapter-Modul (schulmanager.py) - bei API-Aenderungen der Quelle muss nur dieses Modul angepasst werden

## 1.9.1 - Juli 2026

- Schulferien-Einstellungen auf ein einziges Kalender-Sensor-Feld vereinfacht. Ein noch gesetztes zweites Feld (Legacy-Einzelsensoren) wird im Hintergrund weiterhin ausgewertet

## 1.9.0 - Juli 2026

### Verbessert
- Unterstuetzung fuer den neuen Kalender-Sensor des Schulferien-Managers (Attribute schulferien/feiertage mit allen Zeitraeumen): ein einziges Dropdown-Feld genuegt, das Wochen-Blaettern der Karte zeigt damit weit in die Zukunft korrekte Ferien- und Feiertags-Markierungen (z.B. Herbstferien, Buss- und Bettag, Weihnachtsferien)
- Format-Erkennung automatisch am Attribut-Set - die bisherigen Einzelsensoren funktionieren unveraendert weiter
- Auto-Migration: Ist ein Kalender-Sensor mit gleichem Praefix vorhanden, wird die Konfiguration beim Start automatisch umgestellt

## 1.8.0 - Juli 2026 (Card 1.10.0)

### Neu (beides optional)
- Morgen-Push: In den Einstellungen aktivierbar (Standard: aus) - sendet zur konfigurierten Uhrzeit (Standard 19:00) eine gesammelte Benachrichtigung ueber den morgigen Schultag aller Kinder an einen HA-Notify-Service (Geraete-Dropdown wird automatisch geladen, Test-Button inklusive). An freien Tagen bleibt der Push stumm; Blockmodus und Planversionen werden beruecksichtigt
- Materialliste pro Fach: Optionales Material-Feld im Faecher-Tab (z.B. Sportbeutel). Erscheint im Morgen-Push, als Attribut material_morgen am Sensor 'Erste Stunde morgen' und in der Heute-Ansicht der Karte ('Heute dabei: ...') - nur wenn Material eingetragen ist

## 1.7.2 - Juli 2026 (Card 1.9.1)

- Schulschluss-Ansicht nutzt jetzt die vorhandenen Backend-Sensoren als primaere Quelle (schulschluss_heute fuer die Uhrzeit, aktuelle_stunde fuer den Frei-Grund) statt doppelter Berechnung - Karte und Automationen zeigen garantiert dasselbe. Lokale Berechnung bleibt als Fallback, wenn die Sensoren deaktiviert sind; das 'zuletzt {Fach}'-Detail wird weiterhin lokal angereichert

## 1.7.1 - Juli 2026 (Card 1.9.0)

### Neu
- Dritte Kartenansicht 'Schulschluss heute': alle Kinder in einer kompakten Liste mit grosser Schluss-Uhrzeit, Hinweis 'noch bis ... - zuletzt {Fach}' bzw. 'Schule ist aus', an freien Tagen der Grund (Ferien/Feiertag/Wochenende/Betrieb). Beruecksichtigt Planversionen und wird komplett in der Karte berechnet

## 1.7.0 - Juli 2026 (Card 1.8.0)

### Neu
- Karte: Wochenkopf mit Kalenderwoche und Datumsbereich (KW 29 - 13.07.-17.07.2026), Tagesdatum unter jedem Wochentag, Blaettern mit Pfeiltasten und Heute-Button zurueck
- Planversionen fuer den Schuljahreswechsel: Pro Kind 'Neuer Plan ab...' mit Gueltig-ab-Datum anlegen (startet als Kopie), Sensoren und Karte wechseln am Stichtag automatisch, beim Vorblaettern zeigt die Karte bereits den kuenftigen Plan
- Schulfrei-Markierung gilt jetzt fuer jede geblaetterte Woche (Karte erhaelt die Zeitraeume statt nur der aktuellen Woche)
- Blockmodus: Betriebstage werden beim Blaettern pro Tag markiert (Betrieb-Vermerk im Spaltenkopf, gedimmte Spalte) - das Betriebsphasen-Banner entfaellt
- Fach loeschen/umbenennen wirkt jetzt auf alle Planversionen

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
