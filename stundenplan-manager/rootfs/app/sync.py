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

import quellen

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
     raster_gesetzt}

    Planquelle je Tag: originalbereinigter Tagesplan (heute/morgen-Sensoren,
    bei Aenderungen zaehlt das Original-Fach) - Tage ohne Tagesdaten kommen
    aus dem Wochenplan-JSON. Nur tatsaechlich verwendete Kuerzel werden als
    Faecher angelegt; Vertretungsfaecher landen weder im Plan noch in der
    Faecherliste."""
    heute = heute or date.today()
    wp = quellen.hole_wochenplan(kind)
    try:
        details = quellen.hole_fach_details(kind)
    except Exception:
        details = {}
    try:
        tagesplaene = quellen.hole_tagesplaene(kind)
    except Exception:
        tagesplaene = {}

    stats = {"geaendert": False, "kw": wp.get("kw", ""), "importiert": [],
             "uebersprungen": [], "neue_faecher": 0, "ergaenzt": 0,
             "raster_gesetzt": False}
    raster = kind.get("stundenraster") or wp["raster"] \
        or (data.get("einstellungen", {}) or {}).get("stundenraster_standard") or []
    if not raster:
        return stats

    faecher = data.setdefault("faecher", {})

    def fach_sicherstellen(kz):
        """Kanonisches Kuerzel; legt das globale Fach (Name/Farbe/Material)
        bei Bedarf an. Raum/Lehrer sind kindspezifisch und wandern mit
        Merker-Prinzip nach kind["fach_details"]."""
        det = details.get(kz.upper(), {})
        match = next((v for v in faecher if v.upper() == kz.upper()), None)
        if not match:
            match = kz
            faecher[kz] = {"name": det.get("name") or kz,
                           "farbe": FARBPALETTE[len(faecher) % len(FARBPALETTE)],
                           "material": ""}
            stats["neue_faecher"] += 1
            stats["geaendert"] = True
        eintrag = kind.setdefault("fach_details", {}).setdefault(match, {})
        for feld in ("raum", "lehrer"):
            neu_wert = det.get(feld)
            if not neu_wert:
                continue
            darf = not eintrag.get(feld) \
                or eintrag.get(feld) == eintrag.get(f"sm_{feld}")
            if darf and eintrag.get(feld) != neu_wert:
                eintrag[feld] = neu_wert
                stats["ergaenzt"] += 1
                stats["geaendert"] = True
            if eintrag.get(f"sm_{feld}") != neu_wert:
                eintrag[f"sm_{feld}"] = neu_wert
                stats["geaendert"] = True
        return match

    # Finalen Plan je Tag bestimmen: Tagesplan schlaegt Wochen-JSON
    nr_index = {st["nr"]: i for i, st in enumerate(raster)}
    tage_namen = ["mo", "di", "mi", "do", "fr"]
    final = {}
    for datum, stunden in tagesplaene.items():
        wd = date.fromisoformat(datum).weekday()
        if wd > 4:
            continue
        neu_tag = [None] * len(raster)
        for nr, kz in stunden.items():
            idx = nr_index.get(nr)
            if idx is not None:
                neu_tag[idx] = kz
        if any(neu_tag):
            final[tage_namen[wd]] = neu_tag
    for tag, stunden in wp["plan"].items():
        if tag not in final and any(stunden):
            final[tag] = list(stunden)

    ziel = _zielplan(kind, heute)
    for tag in tage_namen:
        if tag not in final:
            stats["uebersprungen"].append(TAG_NAMEN[tag])
            continue
        neu_tag = [fach_sicherstellen(kz) if kz else None for kz in final[tag]]
        if ziel.get(tag) != neu_tag:
            ziel[tag] = neu_tag
            stats["geaendert"] = True
        stats["importiert"].append(TAG_NAMEN[tag])

    # Stundenraster: eigenes Raster automatisch anlegen, wenn die
    # Schulmanager-Zeiten vom Standard abweichen. Merker-Prinzip wie bei
    # Raum/Lehrer: ein vom Import gesetztes Raster folgt spaeteren
    # Aenderungen der Schule, ein handgepflegtes bleibt unangetastet.
    sm_raster = wp["raster"]
    if sm_raster:
        std = (data.get("einstellungen", {}) or {}).get("stundenraster_standard") or []
        eigenes = kind.get("stundenraster")
        if eigenes is None:
            if sm_raster != std:
                kind["stundenraster"] = sm_raster
                kind["sm_raster"] = sm_raster
                stats["raster_gesetzt"] = True
                stats["geaendert"] = True
        elif eigenes == kind.get("sm_raster") and sm_raster != eigenes:
            kind["stundenraster"] = sm_raster
            kind["sm_raster"] = sm_raster
            stats["raster_gesetzt"] = True
            stats["geaendert"] = True
        elif eigenes == sm_raster and kind.get("sm_raster") != sm_raster:
            kind["sm_raster"] = sm_raster
            stats["geaendert"] = True
    return stats


DEFAULT_ZEITEN = ["06:30", "07:00", "07:15"]


def _import_zeiten(einstellungen: dict) -> list:
    """Konfigurierte Auto-Import-Zeiten (Liste oder Komma-String),
    Default kurz vor Schulbeginn."""
    roh = einstellungen.get("auto_import_zeiten") \
        or einstellungen.get("auto_import_zeit") \
        or DEFAULT_ZEITEN
    if isinstance(roh, str):
        roh = roh.split(",")
    zeiten = [z.strip() for z in roh if z and z.strip()]
    return zeiten or list(DEFAULT_ZEITEN)


class AutoImportScheduler:
    """Fuehrt den Import mehrmals morgens vor Schulbeginn aus (Default
    06:30, 07:00, 07:15) fuer Kinder mit auto_import=true - so werden auch
    kurzfristig eingetragene Vertretungen noch erfasst. Jeder Zeitpunkt
    laeuft genau einmal pro Tag; vor Aenderungen wird ein Backup angelegt."""

    def __init__(self, load_data_fn, save_data_fn, backup_fn, publish_fn=None):
        self._load = load_data_fn
        self._save = save_data_fn
        self._backup = backup_fn
        self._publish = publish_fn
        self._stop = threading.Event()
        self._gelaufen = set()  # {(date, "HH:MM")}

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
        zeiten = _import_zeiten(data.get("einstellungen", {}) or {})
        zeit = jetzt.strftime("%H:%M")
        if zeit not in zeiten or (jetzt.date(), zeit) in self._gelaufen:
            return
        self._gelaufen = {(d, z) for d, z in self._gelaufen if d == jetzt.date()}
        self._gelaufen.add((jetzt.date(), zeit))
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
