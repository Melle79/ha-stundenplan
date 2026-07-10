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


def hole_schulfrei_zeitraeume(ferien_entity: str = "",
                              feiertag_entity: str = "") -> list:
    """Liste von {"von": iso, "bis": iso, "grund": str}, gecacht."""
    schluessel = (ferien_entity, feiertag_entity)
    jetzt = time.monotonic()
    if _cache["schluessel"] == schluessel and jetzt - _cache["zeit"] < CACHE_TTL:
        return _cache["daten"]

    token = os.environ.get("SUPERVISOR_TOKEN")
    zeitraeume = []

    if token and (ferien_entity or "").strip():
        try:
            d = _hole_state(ferien_entity.strip(), token)
            a = d.get("attributes", {}) or {}
            if a.get("aktuell_ferien") and a.get("aktuell_ferien_beginn") \
                    and a.get("aktuell_ferien_ende"):
                zeitraeume.append({"von": a["aktuell_ferien_beginn"],
                                   "bis": a["aktuell_ferien_ende"],
                                   "grund": a["aktuell_ferien"]})
            if a.get("beginn") and a.get("ende"):
                zeitraeume.append({"von": a["beginn"], "bis": a["ende"],
                                   "grund": d.get("state") or "Ferien"})
        except Exception as exc:
            log.debug("Ferien-Sensor %s nicht abrufbar: %s", ferien_entity, exc)

    if token and (feiertag_entity or "").strip():
        try:
            d = _hole_state(feiertag_entity.strip(), token)
            a = d.get("attributes", {}) or {}
            if a.get("datum"):
                zeitraeume.append({"von": a["datum"], "bis": a["datum"],
                                   "grund": d.get("state") or "Feiertag"})
            for tag in a.get("vorschau") or []:
                status = (tag.get("status") or "").lower()
                if status in ("", "normal", "wochenende") or not tag.get("date"):
                    continue
                grund = "Feiertag" if status == "feiertag" else status.capitalize()
                if status == "feiertag" and tag["date"] == a.get("datum"):
                    grund = d.get("state") or grund
                zeitraeume.append({"von": tag["date"], "bis": tag["date"],
                                   "grund": grund})
        except Exception as exc:
            log.debug("Feiertag-Sensor %s nicht abrufbar: %s", feiertag_entity, exc)

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
