"""Stundenplan Manager - optionale Ausfall-/Vertretungsstatistik pro Kind.

Schulmanager/Eltern-Portal liefern nur die Aenderungen fuer heute/morgen (keine
Historie). Dieser Sammler schreibt deshalb ab Aktivierung fortlaufend mit: er
holt periodisch die Aenderungen, klassifiziert sie und summiert sie
dedupliziert je Schuljahr in kind["statistik"].

Geplante ganztaegige Sachen (Wandertag, Exkursion, Projekttag ... bzw. Tage mit
einem schulweiten Termin) zaehlen bewusst NICHT als Ausfall - das ist geplanter
Unterricht/Lehrstoff, kein Stundenausfall.
"""
import logging
import threading
from datetime import date, datetime

import quellen
from mqtt_publisher import (TAGE, belegte_stunden, plan_fuer_datum, raum_lehrer,
                            tages_details, _nr)

log = logging.getLogger("stundenplan.statistik")

# Gruende, die einen Entfall als "geplant" markieren (nicht als Ausfall zaehlen)
GEPLANT_WOERTER = [
    "wandertag", "wandern", "exkursion", "ausflug", "schulausflug", "projekt",
    "praktikum", "betriebs", "studienfahrt", "klassenfahrt", "schullandheim",
    "feiertag", "ferien", "schulfrei", "unterrichtsfrei", "brueckentag",
    "brückentag", "sporttag", "sportfest", "bundesjugendspiele", "theater",
    "schulfest", "elternsprechtag",
]

FELDER = ["entfall", "vertretung", "raumwechsel", "lehrerwechsel", "fachwechsel",
          "randstunden"]


def schuljahr(d: date) -> str:
    """'2026/2027' - Schuljahr beginnt am 1. August."""
    return f"{d.year}/{d.year + 1}" if d.month >= 8 else f"{d.year - 1}/{d.year}"


def _termin_daten(schultermine: list) -> set:
    """Alle Datumsangaben (ISO) aus den schulweiten Terminen."""
    tage = set()
    for t in schultermine or []:
        for wert in (t or {}).values():
            s = str(wert)
            if len(s) >= 10 and s[4] == "-" and s[7] == "-":
                tage.add(s[:10])
    return tage


def _ist_geplant(aend: dict, termin_tage: set) -> bool:
    text = f"{aend.get('grund', '')} {aend.get('label', '')}".lower()
    if any(w in text for w in GEPLANT_WOERTER):
        return True
    return str(aend.get("datum", ""))[:10] in termin_tage


def _raster(kind: dict, data: dict) -> list:
    return kind.get("stundenraster") \
        or (data.get("einstellungen", {}) or {}).get("stundenraster_standard") or []


def erfassen(data: dict, kind: dict, aenderungen: list, schultermine: list,
             heute: date = None) -> bool:
    """Traegt neue Aenderungen dedupliziert in kind['statistik'] ein.
    Rueckgabe True, wenn sich etwas geaendert hat."""
    heute = heute or date.today()
    stat = kind.setdefault("statistik", {})
    jahre = stat.setdefault("jahre", {})
    raster = _raster(kind, data)
    if not raster:
        return False
    nr_index = {_nr(st): i for i, st in enumerate(raster)}
    faecher = quellen.faecher_fuer_kind(data.get("faecher", {}), kind)
    termin_tage = _termin_daten(schultermine)
    geaendert = False

    for a in aenderungen or []:
        datum_s = str(a.get("datum", ""))[:10]
        if len(datum_s) != 10:
            continue
        try:
            d = date.fromisoformat(datum_s)
        except ValueError:
            continue
        entfall = bool(a.get("entfall") or a.get("typ") == "cancelledLesson")
        if entfall and _ist_geplant(a, termin_tage):
            continue  # geplanter Ausfall (Wandertag/Exkursion/...) - nicht zaehlen
        kat = "entfall" if entfall else "vertretung"
        stunde = a.get("stunde")
        key = f"{datum_s}|{stunde}|{kat}"

        sj = schuljahr(d)
        eintrag = jahre.setdefault(sj, {"seit": heute.isoformat(),
                                        "keys": [], **{f: 0 for f in FELDER}})
        if key in eintrag["keys"]:
            continue  # schon gezaehlt

        # geplanter Unterricht dieses Tages (fuer Vergleich / Randstunde)
        planobj = plan_fuer_datum(kind, d)
        tag = TAGE[d.weekday()] if d.weekday() < 5 else None
        plan = planobj.get(tag, []) if tag else []
        try:
            idx = nr_index.get(int(stunde))
        except (TypeError, ValueError):
            idx = None

        eintrag[kat] += 1
        if kat == "entfall":
            # Randstunde? (erste/letzte belegte Stunde des Tages entfaellt)
            belegte = belegte_stunden(plan, raster)
            if belegte and idx is not None and idx in (belegte[0], belegte[-1]):
                eintrag["randstunden"] += 1
        else:
            # Vertretung: aufschluesseln, was sich gegenueber dem Plan aendert
            kz = plan[idx] if (idx is not None and idx < len(plan)) else None
            det = tages_details(planobj, tag) if tag else []
            raum_p, lehrer_p = raum_lehrer(kz, faecher, det, idx) if idx is not None else ("", "")
            neu_fach = (a.get("fach") or "").strip()
            neu_raum = (a.get("raum") or "").strip()
            neu_lehrer = (a.get("lehrer") or "").strip()
            if neu_fach and kz and neu_fach.upper() != str(kz).upper():
                eintrag["fachwechsel"] += 1
            if neu_raum and neu_raum != (raum_p or ""):
                eintrag["raumwechsel"] += 1
            if neu_lehrer and neu_lehrer.lower() != (lehrer_p or "").lower():
                eintrag["lehrerwechsel"] += 1

        eintrag["keys"].append(key)
        geaendert = True

    return geaendert


class StatistikCollector:
    """Sammelt stuendlich die Aenderungen der Kinder mit aktiver Statistik."""

    def __init__(self, load_data_fn, save_data_fn):
        self._load = load_data_fn
        self._save = save_data_fn
        self._stop = threading.Event()

    def start(self):
        threading.Thread(target=self._loop, daemon=True).start()
        log.info("Statistik-Sammler gestartet")

    def _loop(self):
        # kurz nach Start einmal, danach stuendlich
        while not self._stop.wait(90):
            try:
                self._tick()
            except Exception:
                log.exception("Fehler im Statistik-Sammler")
            self._stop.wait(3600)

    def _tick(self):
        data = self._load()
        heute = date.today()
        kandidaten = [k for k in data.get("kinder", [])
                      if (k.get("statistik") or {}).get("aktiv")
                      and k.get("schulmanager")]
        if not kandidaten:
            return
        quellen.aktualisiere_quellen(kandidaten)
        geaendert = False
        for kind in kandidaten:
            try:
                aenderungen = quellen.hole_aenderungen(kind, heute)
                schultermine = quellen.hole_schultermine(kind)
            except Exception as exc:
                log.debug("Statistik: Quelle fuer %s nicht abrufbar (%s)",
                          kind.get("name"), exc)
                continue
            if erfassen(data, kind, aenderungen, schultermine, heute):
                geaendert = True
        if geaendert:
            self._save(data)
            log.info("Statistik aktualisiert")
