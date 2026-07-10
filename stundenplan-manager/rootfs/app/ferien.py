"""Stundenplan Manager - Anbindung an den Schulferien & Feiertage Manager.

Fragt konfigurierbare binary_sensor-Entities (heute/morgen schulfrei) ueber die
Home-Assistant-REST-API ab. Ergebnis wird 60s gecacht. Nicht konfigurierte oder
nicht erreichbare Entities liefern None - die Stundenplan-Logik laeuft dann
unveraendert ohne Ferien-Info weiter.
"""
import json
import logging
import os
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


def hole_ferien() -> dict:
    """Liefert {"heute": {...}|None, "morgen": {...}|None}, gecacht."""
    jetzt = time.monotonic()
    if jetzt - _cache["zeit"] < CACHE_TTL:
        return _cache["daten"]

    token = os.environ.get("SUPERVISOR_TOKEN")
    daten = {}
    for key, env in (("heute", "FERIEN_HEUTE"), ("morgen", "FERIEN_MORGEN")):
        entity = os.environ.get(env, "").strip()
        if not entity or not token:
            daten[key] = None
            continue
        try:
            daten[key] = _hole_entity(entity, token)
        except Exception as exc:
            log.debug("Ferien-Entity %s nicht abrufbar: %s", entity, exc)
            daten[key] = None

    _cache["zeit"] = jetzt
    _cache["daten"] = daten
    return daten
