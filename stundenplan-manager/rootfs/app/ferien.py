"""Stundenplan Manager - Schulferien & Feiertage als Zeitraeume.

Liest zwei Sensoren des Schulferien & Feiertage Managers ueber die HA-REST-API:
  - Ferien-Sensor (z.B. sensor.schulferien_bayern_naechste_schulferien):
      state = Name der naechsten Ferien, Attribute beginn/ende,
      sowie aktuell_ferien(_beginn/_ende) waehrend laufender Ferien
  - Feiertag-Sensor (z.B. sensor.schulferien_bayern_naechster_feiertag):
      state = Name, Attribut datum, plus 14-Tage-vorschau mit Tagesstatus

Daraus entsteht eine Liste schulfreier Zeitraeume/Tage mit Grund. 60s-Cache.
Ohne konfigurierte Sensoren liefert alles leere Ergebnisse - die
Stundenplan-Logik laeuft dann unveraendert weiter.
"""
import json
import logging
import os
import re
import time
import urllib.request
from datetime import date

log = logging.getLogger("stundenplan.ferien")

API_URL = os.environ.get("HA_API_URL", "http://supervisor/core/api")
CACHE_TTL = 60

_cache = {"zeit": 0.0, "schluessel": None, "daten": []}


def _hole_state(entity: str, token: str) -> dict:
    req = urllib.request.Request(
        f"{API_URL}/states/{entity}",
        headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.load(r)


def _parse_zeitraeume(state_obj: dict) -> list:
    """Erkennt das Sensor-Format am Attribut-Set und liefert Zeitraeume.

    Unterstuetzt:
      - Kalender-Sensor: Attribute 'schulferien' (Liste mit beginn/ende/name)
        und/oder 'feiertage' (Liste mit datum/name) - komplette Jahresdaten
      - Legacy 'naechste_schulferien': beginn/ende + aktuell_ferien(_beginn/_ende)
      - Legacy 'naechster_feiertag': datum + 14-Tage-vorschau
    """
    a = state_obj.get("attributes", {}) or {}
    z = []

    if isinstance(a.get("schulferien"), list) or isinstance(a.get("feiertage"), list):
        for e in a.get("schulferien") or []:
            if e.get("beginn") and e.get("ende"):
                z.append({"von": e["beginn"], "bis": e["ende"],
                          "grund": e.get("name") or "Ferien"})
        for e in a.get("feiertage") or []:
            if e.get("datum"):
                z.append({"von": e["datum"], "bis": e["datum"],
                          "grund": e.get("name") or "Feiertag"})
        return z

    if a.get("beginn") and a.get("ende"):
        if a.get("aktuell_ferien") and a.get("aktuell_ferien_beginn") \
                and a.get("aktuell_ferien_ende"):
            z.append({"von": a["aktuell_ferien_beginn"],
                      "bis": a["aktuell_ferien_ende"],
                      "grund": a["aktuell_ferien"]})
        z.append({"von": a["beginn"], "bis": a["ende"],
                  "grund": state_obj.get("state") or "Ferien"})
        return z

    if a.get("datum") or a.get("vorschau"):
        if a.get("datum"):
            z.append({"von": a["datum"], "bis": a["datum"],
                      "grund": state_obj.get("state") or "Feiertag"})
        for tag in a.get("vorschau") or []:
            status = (tag.get("status") or "").lower()
            if status in ("", "normal", "wochenende") or not tag.get("date"):
                continue
            grund = "Feiertag" if status == "feiertag" else status.capitalize()
            if status == "feiertag" and tag["date"] == a.get("datum"):
                grund = state_obj.get("state") or grund
            z.append({"von": tag["date"], "bis": tag["date"], "grund": grund})
    return z


def hole_schulfrei_zeitraeume(ferien_entity: str = "",
                              feiertag_entity: str = "") -> list:
    """Liste von {"von": iso, "bis": iso, "grund": str}, gecacht.
    Beide Felder akzeptieren jedes unterstuetzte Format; beim Kalender-Sensor
    reicht ein einziges Feld."""
    schluessel = (ferien_entity, feiertag_entity)
    jetzt = time.monotonic()
    if _cache["schluessel"] == schluessel and jetzt - _cache["zeit"] < CACHE_TTL:
        return _cache["daten"]

    token = os.environ.get("SUPERVISOR_TOKEN")
    zeitraeume = []
    gesehen = set()
    for entity in (ferien_entity, feiertag_entity):
        entity = (entity or "").strip()
        if not entity or not token or entity in gesehen:
            continue
        gesehen.add(entity)
        try:
            zeitraeume.extend(_parse_zeitraeume(_hole_state(entity, token)))
        except Exception as exc:
            log.debug("Ferien-Entity %s nicht abrufbar: %s", entity, exc)

    _cache["zeit"] = jetzt
    _cache["schluessel"] = schluessel
    _cache["daten"] = zeitraeume
    return zeitraeume


def schulfrei_grund(datum: date, zeitraeume: list):
    """Grund (str) wenn das Datum schulfrei ist, sonst None.
    Ferien-Zeitraeume (mehrtaegig) haben Vorrang vor Einzeltagen."""
    d = datum.isoformat()
    treffer = [z for z in zeitraeume if z["von"] <= d <= z["bis"]]
    if not treffer:
        return None
    mehrtaegig = [z for z in treffer if z["von"] != z["bis"]]
    return (mehrtaegig[0] if mehrtaegig else treffer[0])["grund"]


ENTITY_MUSTER = re.compile(
    r"^sensor\..*(schulferien|ferien|feiertag|holiday)", re.I)


def liste_ferien_entities() -> list:
    """Sensor-Entities, die nach Schulferien/Feiertags-Zeitraeumen aussehen."""
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
        if ENTITY_MUSTER.match(eid):
            name = (s.get("attributes") or {}).get("friendly_name") or eid
            treffer.append({"entity_id": eid, "name": name})
    treffer.sort(key=lambda t: t["name"].lower())
    return treffer
