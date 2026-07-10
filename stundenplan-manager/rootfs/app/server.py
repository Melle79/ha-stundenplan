"""Stundenplan Manager - Flask-Backend (Schritt 1: Grundgeruest)."""
import json
import logging
import os
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, render_template, request

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
    "faecher": {},
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


def save_data(data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = DATA_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(DATA_FILE)
    log.debug("Daten gespeichert (%d Kinder)", len(data.get("kinder", [])))


def ist_im_block(kind: dict, datum: datetime) -> bool:
    """True, wenn das Datum in einem Blockzeitraum liegt (nur Modus 'block')."""
    if kind.get("modus") != "block":
        return True
    d = datum.date().isoformat()
    return any(b["von"] <= d <= b["bis"] for b in kind.get("bloecke", []))


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
    app.run(host="0.0.0.0", port=8098)
