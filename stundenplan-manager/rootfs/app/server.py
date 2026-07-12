"""Stundenplan Manager - Flask-Backend (Schritt 1: Grundgeruest)."""
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from mqtt_publisher import SensorPublisher, ist_im_block  # noqa: F401
from resource_registrar import registriere_ressource_async
from ferien import liste_ferien_entities
from push import PushScheduler, baue_nachricht, liste_notify_services, sende_push
from schulmanager import (hole_aenderungen, hole_arbeiten, hole_fach_details,
                          hole_hausaufgaben_items, hole_wochenplan, liste_schueler)
from sync import AutoImportScheduler, fuehre_import_aus
from backup import BackupScheduler, backup_erstellen, backup_wiederherstellen, liste_backups

LOG_LEVEL = os.environ.get("LOG_LEVEL", "info").upper()
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO),
                    format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("stundenplan")

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
DATA_FILE = DATA_DIR / "stundenplan.json"

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Datenmodell
#
# {
#   "version": 1,
#   "einstellungen": {
#     "stundenraster_standard": [
#       {"nr": 1, "von": "08:00", "bis": "08:45"}, ...
#     ]
#   },
#   "faecher": {
#     "MA": {"name": "Mathematik", "farbe": "#4A90D9", "raum": ""},
#     ...
#   },
#   "kinder": [
#     {
#       "id": "kind-1",
#       "name": "Max",
#       "modus": "wochenplan",          # oder "block"
#       "stundenraster": null,           # null = Standard, sonst eigenes Raster
#       "plan": {
#         "mo": ["MA", "DE", null, ...], # Fach-Kuerzel je Stunde, null = frei
#         "di": [...], "mi": [...], "do": [...], "fr": [...]
#       },
#       "bloecke": [                     # nur bei modus == "block" relevant
#         {"von": "2026-09-14", "bis": "2026-10-02", "label": "Block 1"}
#       ]
#     }
#   ]
# }
# ---------------------------------------------------------------------------

STANDARD_FAECHER = {
    "DE":  {"name": "Deutsch",                "farbe": "#e05d5d", "raum": ""},
    "MA":  {"name": "Mathematik",             "farbe": "#4a90d9", "raum": ""},
    "EN":  {"name": "Englisch",               "farbe": "#e0b34c", "raum": ""},
    "FR":  {"name": "Französisch",            "farbe": "#9b6dd6", "raum": ""},
    "LA":  {"name": "Latein",                 "farbe": "#8d6e63", "raum": ""},
    "BIO": {"name": "Biologie",               "farbe": "#4caf7d", "raum": ""},
    "CH":  {"name": "Chemie",                 "farbe": "#26a69a", "raum": ""},
    "PH":  {"name": "Physik",                 "farbe": "#5c6bc0", "raum": ""},
    "NUT": {"name": "Natur und Technik",      "farbe": "#66bb6a", "raum": ""},
    "INF": {"name": "Informatik",             "farbe": "#455a64", "raum": ""},
    "GE":  {"name": "Geschichte",             "farbe": "#a1887f", "raum": ""},
    "GEO": {"name": "Geographie",             "farbe": "#7cb342", "raum": ""},
    "PUG": {"name": "Politik und Gesellschaft", "farbe": "#ef6c00", "raum": ""},
    "WR":  {"name": "Wirtschaft und Recht",   "farbe": "#f4a742", "raum": ""},
    "REL": {"name": "Religion",               "farbe": "#b39ddb", "raum": ""},
    "ETH": {"name": "Ethik",                  "farbe": "#90a4ae", "raum": ""},
    "KU":  {"name": "Kunst",                  "farbe": "#ec407a", "raum": ""},
    "MU":  {"name": "Musik",                  "farbe": "#ab47bc", "raum": ""},
    "SP":  {"name": "Sport",                  "farbe": "#29b6f6", "raum": ""},
    "HSU": {"name": "Heimat- und Sachunterricht", "farbe": "#8bc34a", "raum": ""},
    "WG":  {"name": "Werken und Gestalten",   "farbe": "#bcaaa4", "raum": ""},
}

DEFAULT_DATA = {
    "version": 1,
    "einstellungen": {
        "stundenraster_standard": [
            {"nr": 1, "von": "08:00", "bis": "08:45"},
            {"nr": 2, "von": "08:45", "bis": "09:30"},
            {"nr": 3, "von": "09:50", "bis": "10:35"},
            {"nr": 4, "von": "10:35", "bis": "11:20"},
            {"nr": 5, "von": "11:40", "bis": "12:25"},
            {"nr": 6, "von": "12:25", "bis": "13:10"},
        ]
    },
    "faecher": dict(STANDARD_FAECHER),
    "kinder": [],
}


def load_data() -> dict:
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            log.error("Konnte %s nicht lesen: %s", DATA_FILE, exc)
    return json.loads(json.dumps(DEFAULT_DATA))


PUBLISHER = SensorPublisher(lambda: load_data())


def save_data(data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = DATA_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(DATA_FILE)
    log.debug("Daten gespeichert (%d Kinder)", len(data.get("kinder", [])))
    PUBLISHER.trigger()


# ---------------------------------------------------------------------------
# Routen (Schritt 1: Health + Basis-API, UI folgt in Schritt 2)
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/health")
def health():
    data = load_data()
    return jsonify({
        "status": "ok",
        "version": "1.0.0",
        "kinder": len(data.get("kinder", [])),
        "mqtt": bool(os.environ.get("MQTT_HOST")),
    })


@app.route("/api/backups")
def backups():
    return jsonify(liste_backups())


@app.route("/api/backup/snapshot", methods=["POST"])
def backup_snapshot():
    prefix = (request.get_json(silent=True) or {}).get("prefix", "snapshot")
    if not re.match(r"^[a-z]+$", prefix):
        return jsonify({"error": "Ungueltiger Prefix"}), 400
    name = backup_erstellen(prefix)
    return jsonify({"datei": name})


@app.route("/api/backup/restore", methods=["POST"])
def backup_restore():
    datei = (request.get_json(silent=True) or {}).get("datei", "")
    try:
        backup_wiederherstellen(datei)
        PUBLISHER.trigger()
        return jsonify({"status": "wiederhergestellt"})
    except (ValueError, FileNotFoundError) as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/api/schulmanager/schueler")
def schulmanager_schueler():
    try:
        return jsonify(liste_schueler())
    except Exception as exc:
        log.warning("Schulmanager-Schueler nicht abrufbar: %s", exc)
        return jsonify([])


@app.route("/api/schulmanager/status")
def schulmanager_status():
    """Aenderungen, faellige Hausaufgaben und Arbeiten fuer die Web-UI."""
    data = load_data()
    kind = next((k for k in data.get("kinder", [])
                 if k.get("id") == request.args.get("kind_id")), None)
    if not kind or not kind.get("schulmanager"):
        return jsonify({"error": "Kind nicht gefunden oder nicht verknüpft"}), 400
    basis = kind["schulmanager"]
    ergebnis = {"aenderungen": [], "hausaufgaben": [], "arbeiten": []}
    from datetime import date as _date, timedelta as _td
    heute = _date.today()
    try:
        ergebnis["aenderungen"] = hole_aenderungen(basis, heute)
    except Exception:
        pass
    try:
        ab = (heute - _td(days=7)).isoformat()
        bis = (heute + _td(days=3)).isoformat()
        ergebnis["hausaufgaben"] = [h for h in hole_hausaufgaben_items(basis)
                                    if h["due"] and ab <= h["due"] <= bis][:8]
    except Exception:
        pass
    try:
        ergebnis["arbeiten"] = hole_arbeiten(basis)
    except Exception:
        pass
    return jsonify(ergebnis)


@app.route("/api/schulmanager/import", methods=["POST"])
def schulmanager_import():
    body = request.get_json(silent=True) or {}
    data = load_data()
    kind = next((k for k in data.get("kinder", [])
                 if k.get("id") == body.get("kind_id")), None)
    if not kind or not kind.get("schulmanager"):
        return jsonify({"error": "Kind nicht gefunden oder nicht verknüpft"}), 400
    snapshot = None
    try:
        snapshot = backup_erstellen("import")
        stats = fuehre_import_aus(data, kind)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502
    if stats["geaendert"]:
        save_data(data)
        PUBLISHER.trigger()
    stats["snapshot"] = snapshot
    return jsonify(stats)


@app.route("/api/schulmanager/wochenplan")
def schulmanager_wochenplan():
    entity = request.args.get("entity", "")
    if not entity.startswith("sensor.schule_"):
        return jsonify({"error": "Ungueltige Entity"}), 400
    try:
        ergebnis = hole_wochenplan(entity)
        try:
            basis = entity[:-len("_wochenplan_json")]
            ergebnis["details"] = hole_fach_details(basis)
        except Exception:
            ergebnis["details"] = {}
        return jsonify(ergebnis)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502


@app.route("/api/notify-services")
def notify_services():
    try:
        return jsonify(liste_notify_services())
    except Exception as exc:
        log.warning("Notify-Services nicht abrufbar: %s", exc)
        return jsonify([])


@app.route("/api/push-test", methods=["POST"])
def push_test():
    data = load_data()
    push = (data.get("einstellungen", {}) or {}).get("push", {}) or {}
    if not push.get("service"):
        return jsonify({"error": "Kein Notify-Service gewählt"}), 400
    nachricht = baue_nachricht(data, datetime.now()) or         "Testnachricht: morgen haben alle frei 🎉"
    try:
        sende_push(push["service"], nachricht)
        return jsonify({"status": "gesendet", "nachricht": nachricht})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502


@app.route("/api/ha-entities")
def ha_entities():
    try:
        return jsonify(liste_ferien_entities())
    except Exception as exc:
        log.warning("HA-Entities nicht abrufbar: %s", exc)
        return jsonify([])


def _entity_existiert(entity: str) -> bool:
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token or not entity:
        return False
    try:
        import urllib.request
        from ferien import API_URL
        req = urllib.request.Request(f"{API_URL}/states/{entity}",
                                     headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status == 200
    except Exception:
        return False


def migriere_auf_kalender():
    """Upgrade auf den Kalender-Sensor, falls einer mit gleichem Praefix existiert."""
    data = load_data()
    einst = data.setdefault("einstellungen", {})
    aktuell = einst.get("ferien_sensor", "")
    m = re.match(r"^sensor\.(.+?)_(naechste_schulferien|naechster_feiertag)$", aktuell)
    if not m:
        return
    kalender = f"sensor.{m.group(1)}_kalender"
    if _entity_existiert(kalender):
        einst["ferien_sensor"] = kalender
        einst["feiertag_sensor"] = ""
        log.info("Ferien-Konfiguration auf Kalender-Sensor migriert: %s", kalender)
        save_data(data)


def migriere_sm_marker():
    """Einmalig (v1.14.3): Bestehende Raum/Lehrer-Werte als aus Schulmanager
    gelernt markieren. Importe vor v1.14.2 setzten keine Herkunfts-Merker;
    ohne Migration wuerden damals falsch gelernte Vertretungswerte dauerhaft
    als handgepflegt geschuetzt. Wirklich handgepflegte Werte bleiben sicher:
    Ueberschrieben wird ohnehin nur durch echte Schulmanager-Daten desselben
    Fachs, und jede spaetere Handaenderung weicht vom Merker ab und ist damit
    wieder geschuetzt."""
    data = load_data()
    einst = data.setdefault("einstellungen", {})
    if einst.get("sm_marker_migriert"):
        return
    geaendert = False
    for f in (data.get("faecher") or {}).values():
        for feld in ("raum", "lehrer"):
            if f.get(feld) and not f.get(f"sm_{feld}"):
                f[f"sm_{feld}"] = f[feld]
                geaendert = True
    einst["sm_marker_migriert"] = True
    save_data(data)
    if geaendert:
        log.info("Faecher-Migration: Bestandswerte als Schulmanager-gelernt markiert")


def migriere_ferien_optionen():
    """Alte heute/morgen-Binaersensoren auf die Zeitraum-Sensoren umstellen.
    Nutzt den gemeinsamen Entity-Praefix (z.B. schulferien_bayern)."""
    data = load_data()
    einst = data.setdefault("einstellungen", {})
    if einst.get("ferien_sensor") or einst.get("feiertag_sensor"):
        return
    alt = einst.get("ferien_heute") or einst.get("ferien_morgen") or \
        os.environ.get("FERIEN_HEUTE", "").strip()
    m = re.match(r"^binary_sensor\.(.+?)_(heute|morgen)_(schulfrei|feiertag)$", alt or "")
    if not m:
        return
    praefix = m.group(1)
    einst["ferien_sensor"] = f"sensor.{praefix}_naechste_schulferien"
    einst["feiertag_sensor"] = f"sensor.{praefix}_naechster_feiertag"
    einst.pop("ferien_heute", None)
    einst.pop("ferien_morgen", None)
    log.info("Ferien-Konfiguration auf Zeitraum-Sensoren migriert (%s)", praefix)
    save_data(data)


@app.route("/api/standard-faecher")
def standard_faecher():
    return jsonify(STANDARD_FAECHER)


@app.route("/api/data", methods=["GET"])
def get_data():
    return jsonify(load_data())


@app.route("/api/data", methods=["POST"])
def post_data():
    payload = request.get_json(force=True, silent=True)
    if not isinstance(payload, dict) or "kinder" not in payload:
        return jsonify({"error": "Ungueltige Daten"}), 400
    save_data(payload)
    return jsonify({"status": "gespeichert"})


if __name__ == "__main__":
    log.info("Stundenplan Manager startet auf Port 8098")
    migriere_ferien_optionen()
    migriere_auf_kalender()
    migriere_sm_marker()
    PUBLISHER.start()
    BackupScheduler().start()
    PushScheduler(lambda: load_data()).start()
    AutoImportScheduler(load_data, save_data, backup_erstellen,
                        lambda: PUBLISHER.trigger()).start()
    registriere_ressource_async()
    app.run(host="0.0.0.0", port=8098)
