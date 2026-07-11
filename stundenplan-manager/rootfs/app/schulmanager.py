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
            typ = c.get("type", "")
            ergebnis.append({
                "datum": str(datum)[:10],
                "stunde": stunde,
                "typ": typ,
                "label": TYP_LABELS.get(typ, "Änderung"),
                "fach": c.get("new_subject") or "",
                "raum": c.get("new_room") or "",
                "grund": c.get("reason") or c.get("note") or "",
            })
    return ergebnis
