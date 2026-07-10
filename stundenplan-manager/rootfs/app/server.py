"""Stundenplan Manager - Flask-Backend (Schritt 1: Grundgeruest)."""
import json
import logging
import os
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from mqtt_publisher import SensorPublisher, ist_im_block  # noqa: F401

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
    PUBLISHER.start()
    app.run(host="0.0.0.0", port=8098)
