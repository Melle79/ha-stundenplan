"""Stundenplan Manager - Adapter fuer die Schulmanager-Online-HACS-Integration.

Konsumiert ausschliesslich die von der Integration (MrIcemanLE/
Schulmanager-homeassistant) bereitgestellten Entities ueber die HA-REST-API:
  - sensor.schule_{name}_wochenplan_json   -> Plan-Import (attrs.plan)
  - sensor.schule_{name}_stundenplan_anderungen -> Vertretungen/Entfall

Der Adapter kapselt das Format; sollte sich die Datenquelle aendern, muss nur
dieses Modul angepasst werden.
"""
import json
import logging
import os
import re
import urllib.request
from datetime import date, timedelta

from ferien import API_URL

log = logging.getLogger("stundenplan.schulmanager")

DUE_IM_TITEL = re.compile(r"^\[(\d{4}-\d{2}-\d{2}|\d{2}\.\d{2}\.\d{4})\]\s*")
WOCHENPLAN_MUSTER = re.compile(r"^sensor\.schule_.+_wochenplan_json$")
STUNDE_MUSTER = re.compile(r"^(\d+)\.\s*(\d{2}:\d{2}):\d{2}\s*-\s*(\d{2}:\d{2})")
TAG_KEYS = [("Mo", "mo"), ("Di", "di"), ("Mi", "mi"), ("Do", "do"), ("Fr", "fr")]

TYP_LABELS = {
    "cancelledLesson": "Entfall",
    "substitution": "Vertretung",
    "teacherChange": "Lehrerwechsel",
    "specialLesson": "Sonderstunde",
    "irregularLesson": "Änderung",
}


def _hole_state(entity: str):
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        raise RuntimeError("Kein SUPERVISOR_TOKEN")
    req = urllib.request.Request(f"{API_URL}/states/{entity}",
                                 headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.load(r)


def liste_schueler() -> list:
    """Alle Schulmanager-Schueler: [{"entity_id", "basis", "name"}]."""
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        return []
    req = urllib.request.Request(f"{API_URL}/states",
                                 headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=10) as r:
        states = json.load(r)
    treffer = []
    for s in states:
        eid = s.get("entity_id", "")
        if WOCHENPLAN_MUSTER.match(eid):
            name = ((s.get("attributes") or {}).get("friendly_name") or eid)
            name = re.sub(r"\s*Wochenplan JSON\s*$", "", name)
            treffer.append({"entity_id": eid,
                            "basis": eid[:-len("_wochenplan_json")],
                            "name": name})
    treffer.sort(key=lambda t: t["name"].lower())
    return treffer


def hole_wochenplan(entity: str) -> dict:
    """Parst attrs.plan des Wochenplan-JSON-Sensors.

    Rueckgabe: {"raster": [{nr, von, bis}], "plan": {mo..fr: [kuerzel|None]},
                "kuerzel": [alle verwendeten], "kw": state}
    """
    d = _hole_state(entity)
    zeilen = (d.get("attributes") or {}).get("plan") or []
    raster, plan = [], {t: [] for _, t in TAG_KEYS}
    kuerzel = []
    for zeile in zeilen:
        m = STUNDE_MUSTER.match(str(zeile.get("Stunde", "")))
        if not m:
            continue
        raster.append({"nr": int(m.group(1)), "von": m.group(2), "bis": m.group(3)})
        for key, tag in TAG_KEYS:
            kz = (zeile.get(key) or "").strip() or None
            plan[tag].append(kz)
            if kz and kz not in kuerzel:
                kuerzel.append(kz)
    return {"raster": raster, "plan": plan, "kuerzel": kuerzel,
            "kw": d.get("state", "")}


def hole_aenderungen(basis: str, heute: date = None) -> list:
    """Normalisierte Aenderungen aus dem Aenderungs-Sensor.

    Rueckgabe: [{"datum": iso, "stunde": int|None, "typ": raw type,
                 "label": deutsch, "fach": str, "raum": str, "grund": str}]
    """
    heute = heute or date.today()
    try:
        d = _hole_state(f"{basis}_stundenplan_anderungen")
    except Exception as exc:
        log.debug("Aenderungs-Sensor fuer %s nicht abrufbar: %s", basis, exc)
        return []
    changes = (d.get("attributes") or {}).get("changes") or {}
    ergebnis = []
    for day_name, offset in (("today", 0), ("tomorrow", 1)):
        for c in changes.get(day_name) or []:
            datum = c.get("date") or (heute + timedelta(days=offset)).isoformat()
            try:
                stunde = int(c.get("hour"))
            except (TypeError, ValueError):
                stunde = None
            typ = (c.get("type") or "").strip()
            label = TYP_LABELS.get(typ) or typ or "Änderung"
            entfall = typ == "cancelledLesson" or \
                any(w in typ.lower() for w in ("entfall", "entfällt", "ausfall", "fällt aus"))
            ergebnis.append({
                "datum": str(datum)[:10],
                "stunde": stunde,
                "typ": typ,
                "label": label,
                "entfall": entfall,
                "fach": c.get("new_subject") or "",
                "lehrer": c.get("new_teacher") or "",
                "raum": c.get("new_room") or "",
                "grund": c.get("reason") or c.get("note") or "",
            })
    return ergebnis


def hole_zusatzinfos(basis: str) -> dict:
    """Offene Hausaufgaben (todo-Entity) und naechste Klassenarbeit.

    Rueckgabe: {"hausaufgaben_offen": int|None,
                "naechste_arbeit": {"datum","in_tagen","fach","typ"}|None}
    """
    info = {"hausaufgaben_offen": None, "naechste_arbeit": None}
    todo_entity = basis.replace("sensor.", "todo.", 1) + "_hausaufgaben"
    try:
        d = _hole_state(todo_entity)
        if d.get("state") not in (None, "unknown", "unavailable"):
            info["hausaufgaben_offen"] = int(d["state"])
    except Exception as exc:
        log.debug("Hausaufgaben fuer %s nicht abrufbar: %s", basis, exc)
    try:
        d = _hole_state(f"{basis}_tage_bis_nachste_arbeit")
        ne = (d.get("attributes") or {}).get("next_exam")
        if ne and ne.get("date"):
            info["naechste_arbeit"] = {
                "datum": str(ne["date"])[:10],
                "in_tagen": ne.get("days_from_now"),
                "fach": ne.get("subject") or ne.get("subject_abbr") or "",
                "typ": ne.get("type") or "Arbeit",
            }
    except Exception as exc:
        log.debug("Arbeiten fuer %s nicht abrufbar: %s", basis, exc)
    return info


def hole_hausaufgaben_items(basis: str) -> list:
    """Offene Hausaufgaben aus der Todo-Entity via todo.get_items.

    Rueckgabe: [{"titel": str, "due": iso|None}], nach Faelligkeit sortiert.
    """
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        return []
    entity = basis.replace("sensor.", "todo.", 1) + "_hausaufgaben"
    body = json.dumps({"entity_id": entity}).encode()
    req = urllib.request.Request(
        f"{API_URL}/services/todo/get_items?return_response", data=body,
        method="POST",
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        antwort = json.load(r)
    daten = antwort.get("service_response", antwort) or {}
    items = (daten.get(entity) or {}).get("items") or []
    offene = []
    for it in items:
        if it.get("status") not in (None, "needs_action"):
            continue
        titel = (it.get("summary") or "").strip()
        due = str(it.get("due"))[:10] if it.get("due") else None
        m = DUE_IM_TITEL.match(titel)
        if m:
            titel = titel[m.end():].strip()
            if not due:
                d = m.group(1)
                due = d if "-" in d else f"{d[6:10]}-{d[3:5]}-{d[0:2]}"
        offene.append({"titel": titel, "due": due})
    offene.sort(key=lambda x: x["due"] or "9999-99-99")
    return offene


def hole_arbeiten(basis: str) -> list:
    """Kommende Klassenarbeiten: [{"datum","fach","kuerzel","typ"}]."""
    try:
        d = _hole_state(f"{basis}_tage_bis_nachste_arbeit")
    except Exception as exc:
        log.debug("Arbeiten fuer %s nicht abrufbar: %s", basis, exc)
        return []
    a = d.get("attributes") or {}
    eintraege = a.get("upcoming_exams")
    if not eintraege and a.get("next_exam"):
        eintraege = [a["next_exam"]]
    arbeiten = []
    for e in eintraege or []:
        if not e.get("date"):
            continue
        arbeiten.append({"datum": str(e["date"])[:10],
                         "fach": e.get("subject") or "",
                         "kuerzel": e.get("subject_abbr") or "",
                         "typ": e.get("type") or "Arbeit"})
    arbeiten.sort(key=lambda x: x["datum"])
    return arbeiten


def hole_fach_details(basis: str) -> dict:
    """Raum, Lehrer und voller Fachname je Kuerzel aus den
    Stundenplan-heute/morgen-Sensoren (raw.lessons).

    Rueckgabe: {KUERZEL_UPPER: {"raum", "lehrer", "name"}}
    """
    details = {}
    for suffix in ("_stundenplan_heute", "_stundenplan_morgen"):
        try:
            d = _hole_state(f"{basis}{suffix}")
        except Exception:
            continue
        lessons = ((d.get("attributes") or {}).get("raw") or {}).get("lessons") or []
        for l in lessons:
            # Nur regulaere Daten lernen: bei Vertretung/Entfall enthaelt
            # "original" den regulaeren Stand - sonst Stunde ueberspringen,
            # damit kein Springer-Lehrer oder Ausweichraum haengenbleibt.
            typ = l.get("type") or "regularLesson"
            if typ != "regularLesson":
                l = l.get("original") or {}
            kz = (l.get("subject") or "").strip()
            if not kz:
                continue
            eintrag = details.setdefault(kz.upper(), {"raum": "", "lehrer": "", "name": ""})
            if not eintrag["raum"] and l.get("room"):
                eintrag["raum"] = str(l["room"]).strip()
            if not eintrag["lehrer"] and l.get("teacher"):
                eintrag["lehrer"] = str(l["teacher"]).strip()
            if not eintrag["name"] and l.get("subject_full"):
                eintrag["name"] = str(l["subject_full"]).strip()
    return details
