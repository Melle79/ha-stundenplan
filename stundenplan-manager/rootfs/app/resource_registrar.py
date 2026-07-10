"""Stundenplan Manager - automatische Lovelace-Ressourcen-Registrierung.

Registriert /local/stundenplan-card.js?v={Kartenversion} als Dashboard-Ressource
ueber die Home-Assistant-WebSocket-API (Supervisor-Proxy). Existiert die Ressource
bereits mit alter Version, wird sie aktualisiert - der Browser laedt dadurch nach
jedem Karten-Update automatisch die frische Datei.
"""
import json
import logging
import os
import re
import threading
import time

log = logging.getLogger("stundenplan.resource")

CARD_PATH = os.environ.get("CARD_PATH", "/card/stundenplan-card.js")
RESOURCE_URL = "/local/stundenplan-card.js"
WS_URL = os.environ.get("HA_WS_URL", "ws://supervisor/core/websocket")


def _karten_version():
    try:
        with open(CARD_PATH, encoding="utf-8") as f:
            m = re.search(r"Stundenplan Card v(\d+\.\d+\.\d+)", f.read())
        return m.group(1) if m else None
    except OSError:
        return None


def registriere_ressource_async():
    threading.Thread(target=_run, daemon=True).start()


def _run():
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        log.warning("Kein SUPERVISOR_TOKEN - Ressourcen-Registrierung uebersprungen")
        return
    version = _karten_version()
    if not version:
        log.warning("Kartenversion nicht ermittelbar - Ressourcen-Registrierung uebersprungen")
        return
    ziel = f"{RESOURCE_URL}?v={version}"
    for versuch in range(12):
        try:
            if _registriere(token, ziel):
                return
        except Exception as exc:
            log.debug("Registrierung Versuch %d fehlgeschlagen: %s", versuch + 1, exc)
        time.sleep(10)
    log.warning("Lovelace-Ressource konnte nicht automatisch registriert werden - "
                "bitte manuell pruefen: %s", ziel)


def _registriere(token: str, ziel: str) -> bool:
    import websocket
    ws = websocket.create_connection(WS_URL, timeout=10)
    try:
        json.loads(ws.recv())  # auth_required
        ws.send(json.dumps({"type": "auth", "access_token": token}))
        antwort = json.loads(ws.recv())
        if antwort.get("type") != "auth_ok":
            raise RuntimeError(f"Auth fehlgeschlagen: {antwort}")

        ws.send(json.dumps({"id": 1, "type": "lovelace/resources"}))
        res = json.loads(ws.recv())
        if not res.get("success"):
            log.info("Lovelace-Ressourcen nicht abrufbar (YAML-Dashboard-Modus?) - "
                     "Karte manuell einbinden: %s", ziel)
            return True

        vorhandene = [r for r in res.get("result", [])
                      if r.get("url", "").split("?")[0] == RESOURCE_URL]
        if vorhandene:
            r = vorhandene[0]
            if r["url"] == ziel:
                log.info("Lovelace-Ressource ist aktuell: %s", ziel)
                return True
            ws.send(json.dumps({"id": 2, "type": "lovelace/resources/update",
                                "resource_id": r["id"], "url": ziel,
                                "res_type": "module"}))
            ok = bool(json.loads(ws.recv()).get("success"))
            if ok:
                log.info("Lovelace-Ressource aktualisiert: %s (Browser einmal neu laden)", ziel)
            return ok

        ws.send(json.dumps({"id": 2, "type": "lovelace/resources/create",
                            "url": ziel, "res_type": "module"}))
        ok = bool(json.loads(ws.recv()).get("success"))
        if ok:
            log.info("Lovelace-Ressource angelegt: %s", ziel)
        return ok
    finally:
        ws.close()
