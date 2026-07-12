"""Stundenplan Manager - Schulmanager-Import als Backend-Logik.

Eine Merge-Funktion fuer beide Wege: den Import-Button in der Web-UI und den
optionalen taeglichen Auto-Import (pro Kind aktivierbar, kind["auto_import"]).

Merge-Regeln:
  - Nur in Schulmanager befuellte Tage ersetzen, leere bleiben unangetastet
  - Faecher: case-insensitives Kuerzel-Matching; neue Faecher werden mit
    Name/Raum/Lehrer aus den Detail-Sensoren angelegt, bei bestehenden werden
    nur leere Felder ergaenzt - nichts wird ueberschrieben
  - Zielversion ist die am Import-Tag gueltige Planversion
  - Das Stundenraster wird nur gesetzt, wenn das Kind noch keines hat
"""
import logging
import threading
from datetime import date, datetime

from schulmanager import hole_fach_details, hole_wochenplan

log = logging.getLogger("stundenplan.sync")

FARBPALETTE = ["#e05d5d", "#4a90d9", "#e0b34c", "#4caf7d", "#9b6dd6", "#26a69a",
               "#ec407a", "#5c6bc0", "#ef6c00", "#8d6e63", "#29b6f6", "#ab47bc",
               "#7cb342", "#90a4ae"]
TAG_NAMEN = {"mo": "Mo", "di": "Di", "mi": "Mi", "do": "Do", "fr": "Fr"}


def _zielplan(kind: dict, heute: date) -> dict:
    """Die am Stichtag gueltige Planversion (Objekt-Referenz aus kind)."""
    d = heute.isoformat()
    passend = sorted((p for p in kind.get("plaene", [])
                      if p.get("gueltig_ab", "9999") <= d),
                     key=lambda p: p["gueltig_ab"])
    return passend[-1]["plan"] if passend else kind.setdefault("plan", {})


def fuehre_import_aus(data: dict, kind: dict, heute: date = None) -> dict:
    """Mutiert data/kind. Rueckgabe-Stats:
    {geaendert, kw, importiert, uebersprungen, neue_faecher, ergaenzt,
     raster_gesetzt}"""
    heute = heute or date.today()
    wp = hole_wochenplan(f"{kind['schulmanager']}_wochenplan_json")
    try:
        details = hole_fach_details(kind["schulmanager"])
    except Exception:
        details = {}

    stats = {"geaendert": False, "kw": wp.get("kw", ""), "importiert": [],
             "uebersprungen": [], "neue_faecher": 0, "ergaenzt": 0,
             "raster_gesetzt": False}
    if not wp["raster"] or not wp["kuerzel"]:
        return stats

    faecher = data.setdefault("faecher", {})
    for kz in wp["kuerzel"]:
        det = details.get(kz.upper(), {})
        match = next((v for v in faecher if v.upper() == kz.upper()), None)
        if not match:
            faecher[kz] = {"name": det.get("name") or kz,
                           "farbe": FARBPALETTE[len(faecher) % len(FARBPALETTE)],
                           "raum": det.get("raum", ""),
                           "lehrer": det.get("lehrer", ""),
                           "material": ""}
            stats["neue_faecher"] += 1
            stats["geaendert"] = True
        else:
            f = faecher[match]
            if not f.get("raum") and det.get("raum"):
                f["raum"] = det["raum"]
                stats["ergaenzt"] += 1
                stats["geaendert"] = True
            if not f.get("lehrer") and det.get("lehrer"):
                f["lehrer"] = det["lehrer"]
                stats["ergaenzt"] += 1
                stats["geaendert"] = True
            if match != kz:
                for tag in wp["plan"]:
                    wp["plan"][tag] = [match if x == kz else x
                                       for x in wp["plan"][tag]]

    ziel = _zielplan(kind, heute)
    for tag, stunden in wp["plan"].items():
        if any(stunden):
            if ziel.get(tag) != stunden:
                ziel[tag] = stunden
                stats["geaendert"] = True
            stats["importiert"].append(TAG_NAMEN[tag])
        else:
            stats["uebersprungen"].append(TAG_NAMEN[tag])

    if not kind.get("stundenraster") and wp["raster"]:
        kind["stundenraster"] = wp["raster"]
        stats["raster_gesetzt"] = True
        stats["geaendert"] = True
    return stats


class AutoImportScheduler:
    """Fuehrt den Import taeglich (Default 05:30) fuer Kinder mit
    auto_import=true aus. Vor Aenderungen wird ein Backup angelegt."""

    def __init__(self, load_data_fn, save_data_fn, backup_fn, publish_fn=None):
        self._load = load_data_fn
        self._save = save_data_fn
        self._backup = backup_fn
        self._publish = publish_fn
        self._stop = threading.Event()
        self._zuletzt = None  # date

    def start(self):
        threading.Thread(target=self._loop, daemon=True).start()
        log.info("Auto-Import-Scheduler gestartet")

    def _loop(self):
        while not self._stop.wait(30):
            try:
                self._tick()
            except Exception:
                log.exception("Fehler im Auto-Import")

    def _tick(self):
        jetzt = datetime.now()
        data = self._load()
        zeit = (data.get("einstellungen", {}) or {}).get("auto_import_zeit") or "05:30"
        if jetzt.strftime("%H:%M") != zeit or self._zuletzt == jetzt.date():
            return
        self._zuletzt = jetzt.date()
        kandidaten = [k for k in data.get("kinder", [])
                      if k.get("auto_import") and k.get("schulmanager")]
        if not kandidaten:
            return
        backup_gemacht = False
        geaendert = False
        for kind in kandidaten:
            try:
                stats = fuehre_import_aus(data, kind, jetzt.date())
            except Exception as exc:
                log.warning("Auto-Import fuer %s fehlgeschlagen: %s",
                            kind["name"], exc)
                continue
            if stats["geaendert"] and not backup_gemacht:
                self._backup("autoimport")
                backup_gemacht = True
            geaendert = geaendert or stats["geaendert"]
            log.info("Auto-Import %s (%s): %s uebernommen, %d neue Faecher, %d ergaenzt%s",
                     kind["name"], stats["kw"],
                     ", ".join(stats["importiert"]) or "nichts",
                     stats["neue_faecher"], stats["ergaenzt"],
                     " (unveraendert)" if not stats["geaendert"] else "")
        if geaendert:
            self._save(data)
            if self._publish:
                self._publish()
