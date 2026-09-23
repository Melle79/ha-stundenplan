"""Stundenplan Manager - Adapter fuer die WebUntis-HACS-Integration.

WebUntis (Domain 'webuntis') stellt den Stundenplan als HA-Kalender bereit:
  - calendar.<schueler>              -> Unterricht (summary=Fach, location=Raum,
                                        echte Uhrzeiten als dateTime)
  - calendar.<schueler>_hausaufgaben -> Hausaufgaben
  - calendar.<schueler>_prufungen    -> Pruefungen/Arbeiten

Anders als Schulmanager/Eltern-Portal gibt es kein Stundenraster - dieser
Adapter leitet Raster (Zeitslots) und Wochenplan aus den Kalender-Terminen ab
und bildet so das gemeinsame Quellen-Format nach. Vertretungen liefert die
Integration nur als HA-Event (nicht abfragbar), daher hier noch nicht.
"""
import json
import logging
import os
import re
import time
import urllib.request
from datetime import date, timedelta

from ferien import API_URL

log = logging.getLogger("stundenplan.untis")

TAGE = ["mo", "di", "mi", "do", "fr"]
_cache = {}          # basis -> (ts, (montag, raster, tage, details))
_CACHE_TTL = 45


def _token() -> str:
    t = os.environ.get("SUPERVISOR_TOKEN")
    if not t:
        raise RuntimeError("Kein SUPERVISOR_TOKEN")
    return t


def _hole_state(entity: str):
    req = urllib.request.Request(f"{API_URL}/states/{entity}",
                                 headers={"Authorization": f"Bearer {_token()}"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.load(r)


def _events(entity: str, von: date, bis: date) -> list:
    url = (f"{API_URL}/calendars/{entity}"
           f"?start={von.isoformat()}T00:00:00&end={bis.isoformat()}T00:00:00")
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {_token()}"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)


def _dt(feld):
    """Kalender-Zeitfeld -> (iso_datum, 'HH:MM'|''). Nimmt dateTime oder date."""
    if isinstance(feld, dict):
        if feld.get("dateTime"):
            s = str(feld["dateTime"])
            return s[:10], s[11:16]
        return str(feld.get("date", ""))[:10], ""
    s = str(feld or "")
    return s[:10], (s[11:16] if "T" in s else "")


def _kuerzel(summary: str) -> str:
    """Kurzes, stabiles Kuerzel aus dem Fachnamen ableiten (WebUntis liefert
    keine Kuerzel, nur den Klartext)."""
    s = (summary or "").strip()
    if not s:
        return "?"
    if len(s) <= 5 and " " not in s:
        return s.upper()
    worte = [w for w in re.split(r"[\s/\-]+", s) if w]
    if len(worte) >= 2:
        return "".join(w[0] for w in worte)[:4].upper()
    return s[:4].upper()


def _montag(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _woche_mit_stunden(basis: str, ab: date, wochen: int = 6):
    """Erste Woche (Mo-Fr) ab 'ab' mit Unterricht -> (montag, [events])."""
    start = _montag(ab)
    for w in range(wochen):
        mo = start + timedelta(weeks=w)
        fr = mo + timedelta(days=5)
        try:
            roh = _events(basis, mo, fr) or []
        except Exception as exc:
            log.debug("WebUntis-Kalender %s nicht abrufbar: %s", basis, exc)
            return None, []
        ev = []
        for e in roh:
            d0, v = _dt(e.get("start"))
            if not (d0 and v):
                continue
            try:
                if date.fromisoformat(d0).weekday() > 4:
                    continue
            except ValueError:
                continue
            ev.append(e)
        if ev:
            return mo, ev
    return None, []


def _plan_daten(basis: str):
    """(montag, raster[{nr,von,bis}], tage{iso:{nr:kz}}, details{KZ:{...}}).
    Gecacht, da Import mehrere Funktionen nacheinander aufruft."""
    hit = _cache.get(basis)
    if hit and time.monotonic() - hit[0] < _CACHE_TTL:
        return hit[1]
    mo, events = _woche_mit_stunden(basis, date.today())
    if not mo:
        ergebnis = (None, [], {}, {})
        _cache[basis] = (time.monotonic(), ergebnis)
        return ergebnis
    slots = {}
    for e in events:
        _, v = _dt(e.get("start"))
        _, b = _dt(e.get("end"))
        if v and b:
            slots[(v, b)] = True
    raster = [{"nr": i + 1, "von": v, "bis": b}
              for i, (v, b) in enumerate(sorted(slots.keys()))]
    slot_nr = {(r["von"], r["bis"]): r["nr"] for r in raster}
    tage, details = {}, {}
    for e in events:
        d0, v = _dt(e.get("start"))
        _, b = _dt(e.get("end"))
        nr = slot_nr.get((v, b))
        if not nr:
            continue
        summary = (e.get("summary") or "").strip()
        kz = _kuerzel(summary)
        tage.setdefault(d0, {})[nr] = kz
        det = details.setdefault(kz.upper(),
                                 {"raum": "", "lehrer": "", "name": "", "lehrer_name": ""})
        if not det["name"]:
            det["name"] = summary
        if not det["raum"] and e.get("location"):
            det["raum"] = str(e["location"]).strip()
    ergebnis = (mo, raster, tage, details)
    _cache[basis] = (time.monotonic(), ergebnis)
    return ergebnis


def liste_schueler() -> list:
    """WebUntis-Schueler: Haupt-Kalender, erkannt am _hausaufgaben-Geschwister.
    Rueckgabe: [{"entity_id","basis","name"}]."""
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        return []
    req = urllib.request.Request(f"{API_URL}/states",
                                 headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=10) as r:
        states = json.load(r)
    ids = {e.get("entity_id") for e in states}
    treffer = []
    for e in states:
        eid = e.get("entity_id", "")
        if not eid.startswith("calendar."):
            continue
        if any(eid.endswith(s) for s in ("_hausaufgaben", "_prufungen", "_pruefungen")):
            continue
        if f"{eid}_hausaufgaben" not in ids:
            continue
        name = (e.get("attributes") or {}).get("friendly_name") or eid[len("calendar."):]
        treffer.append({"entity_id": eid, "basis": eid, "name": str(name)})
    treffer.sort(key=lambda t: t["name"].lower())
    return treffer


def hole_wochenplan(basis: str) -> dict:
    """{"raster","plan","kuerzel","kw"} wie die anderen Quellen."""
    mo, raster, tage, _ = _plan_daten(basis)
    plan = {t: [None] * len(raster) for t in TAGE}
    kuerzel = []
    if mo:
        nr_idx = {r["nr"]: i for i, r in enumerate(raster)}
        for iso, stunden in tage.items():
            try:
                wd = date.fromisoformat(iso).weekday()
            except ValueError:
                continue
            if wd > 4:
                continue
            for nr, kz in stunden.items():
                i = nr_idx.get(nr)
                if i is not None:
                    plan[TAGE[wd]][i] = kz
                    if kz not in kuerzel:
                        kuerzel.append(kz)
    kw = f"KW {mo.isocalendar()[1]}" if mo else "WebUntis"
    return {"raster": raster, "plan": plan, "kuerzel": kuerzel, "kw": kw}


def hole_tagesplaene(basis: str) -> dict:
    """{iso_datum: {stunden_nr: kuerzel}} der Referenzwoche."""
    return _plan_daten(basis)[2]


def hole_zeitplan_bereich(basis: str, von: date, bis: date) -> dict:
    """Alle Unterrichtstermine im Zeitraum, datumsgenau (fuer den
    datumsgenauen Modus - jeder Block/jede Woche kann anders sein).

    Anders als hole_wochenplan/hole_tagesplaene wird hier nichts auf eine
    Referenzwoche zusammengefaltet: jede echte Kalenderstunde bleibt an ihrem
    Datum. Rueckgabe:
      {"tage": {iso: [{"von","bis","kz","name","raum"}, ...]},
       "details": {KZ_UPPER: {"raum","lehrer","name","lehrer_name"}}}
    """
    try:
        roh = _events(basis, von, bis) or []
    except Exception as exc:
        log.debug("WebUntis-Bereich %s nicht abrufbar: %s", basis, exc)
        return {"tage": {}, "details": {}}
    tage, details = {}, {}
    for e in roh:
        d0, v = _dt(e.get("start"))
        _, b = _dt(e.get("end"))
        if not (d0 and v and b) or b <= v:
            continue
        try:
            if date.fromisoformat(d0).weekday() > 4:
                continue
        except ValueError:
            continue
        summary = (e.get("summary") or "").strip()
        kz = _kuerzel(summary)
        raum = str(e.get("location") or "").strip()
        tage.setdefault(d0, []).append({"von": v, "bis": b, "kz": kz,
                                        "name": summary, "raum": raum})
        det = details.setdefault(kz.upper(),
                                 {"raum": "", "lehrer": "", "name": "", "lehrer_name": ""})
        if not det["name"]:
            det["name"] = summary
        if not det["raum"] and raum:
            det["raum"] = raum
    for iso in tage:
        tage[iso].sort(key=lambda s: (s["von"], s["bis"]))
    return {"tage": tage, "details": details}


def hole_fach_details(basis: str) -> dict:
    """{KUERZEL_UPPER: {"raum","lehrer","name","lehrer_name"}}.
    WebUntis liefert keinen Lehrer im Kalender - bleibt leer."""
    return _plan_daten(basis)[3]


def hole_aenderungen(basis: str, heute: date = None) -> list:
    """WebUntis meldet Vertretungen nur als HA-Event (nicht als Liste
    abfragbar) - daher hier (noch) keine Aenderungen."""
    return []


def hole_hausaufgaben_items(basis: str) -> list:
    """[{"due": iso, "titel": str}] aus dem Hausaufgaben-Kalender."""
    von = date.today() - timedelta(days=1)
    bis = date.today() + timedelta(days=28)
    try:
        ev = _events(f"{basis}_hausaufgaben", von, bis)
    except Exception:
        return []
    items = []
    for e in ev or []:
        d0, _ = _dt(e.get("start"))
        if d0:
            items.append({"due": d0, "titel": (e.get("summary") or "").strip()})
    return items


def hole_arbeiten(basis: str) -> list:
    """[{"datum","fach","kuerzel","typ"}] aus dem Pruefungs-Kalender."""
    von = date.today()
    bis = date.today() + timedelta(days=90)
    for suf in ("_prufungen", "_pruefungen"):
        try:
            ev = _events(f"{basis}{suf}", von, bis)
        except Exception:
            continue
        arbeiten = []
        for e in ev or []:
            d0, _ = _dt(e.get("start"))
            if d0:
                summary = (e.get("summary") or "").strip()
                arbeiten.append({"datum": d0, "fach": summary,
                                 "kuerzel": _kuerzel(summary), "typ": "Prüfung"})
        if arbeiten:
            return sorted(arbeiten, key=lambda x: x["datum"])
    return []


def hole_zusatzinfos(basis: str) -> dict:
    heute = date.today().isoformat()
    offen = [h for h in hole_hausaufgaben_items(basis) if h["due"] >= heute]
    arbeiten = hole_arbeiten(basis)
    naechste = None
    if arbeiten:
        a = arbeiten[0]
        naechste = {"datum": a["datum"], "typ": a["typ"], "fach": a["fach"]}
    return {"hausaufgaben_offen": len(offen) if offen else None,
            "naechste_arbeit": naechste}


def hole_datenstand(basis: str):
    """WebUntis liefert keinen verlaesslichen Abruf-Zeitstempel."""
    return None
