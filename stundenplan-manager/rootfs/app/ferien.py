"""Stundenplan Manager - Anbindung an den Schulferien & Feiertage Manager.

Fragt konfigurierbare binary_sensor-Entities (heute/morgen schulfrei) ueber die
Home-Assistant-REST-API ab. Ergebnis wird 60s gecacht. Nicht konfigurierte oder
nicht erreichbare Entities liefern None - die Stundenplan-Logik laeuft dann
unveraendert ohne Ferien-Info weiter.
"""
import json
import logging
import os
import re
import time
import urllib.request

log = logging.getLogger("stundenplan.ferien")

API_URL = os.environ.get("HA_API_URL", "http://supervisor/core/api")
CACHE_TTL = 60

_cache = {"zeit": 0.0, "daten": {"heute": None, "morgen": None}}


def _hole_entity(entity: str, token: str):
    req = urllib.request.Request(
        f"{API_URL}/states/{entity}",
        headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=5) as r:
        d = json.load(r)
    attrs = d.get("attributes", {}) or {}
    return {
        "schulfrei": d.get("state") == "on",
        "grund": attrs.get("grund") or attrs.get("name") or "",
    }


def hole_ferien(entity_heute: str = "", entity_morgen: str = "") -> dict:
    """Liefert {"heute": {...}|None, "morgen": {...}|None}, gecacht."""
    schluessel = (entity_heute, entity_morgen)
    jetzt = time.monotonic()
    if _cache.get("schluessel") == schluessel and jetzt - _cache["zeit"] < CACHE_TTL:
        return _cache["daten"]

    token = os.environ.get("SUPERVISOR_TOKEN")
    daten = {}
    for key, entity in (("heute", entity_heute), ("morgen", entity_morgen)):
        entity = (entity or "").strip()
        if not entity or not token:
            daten[key] = None
            continue
        try:
            daten[key] = _hole_entity(entity, token)
        except Exception as exc:
            log.debug("Ferien-Entity %s nicht abrufbar: %s", entity, exc)
            daten[key] = None

    _cache["zeit"] = jetzt
    _cache["schluessel"] = schluessel
    _cache["daten"] = daten
    return daten


ENTITY_MUSTER = re.compile(r"^binary_sensor\..*(schulfrei|ferien|feiertag|holiday)", re.I)


def liste_ferien_entities() -> list:
    """Alle binary_sensor-Entities, die nach Schulferien/Feiertagen aussehen."""
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
