"""Stundenplan Manager - MQTT Discovery Publisher.

Publiziert pro Kind vier Sensoren via MQTT Discovery:
  - aktuelle_stunde     (laufende Stunde, Pause, Kein Unterricht, Schulfrei, Betrieb)
  - naechste_stunde     (naechste belegte Stunde heute)
  - erste_stunde_morgen (erste belegte Stunde am morgigen Tag)
  - schulschluss_heute  (Ende der letzten belegten Stunde heute)

Blocklogik: Bei Kindern im Modus "block" gelten die Plaene nur innerhalb
der gepflegten Blockzeitraeume, ausserhalb liefern die Sensoren "Betrieb".
"""
import json
import logging
import os
import re
import threading
import time
from datetime import datetime, timedelta

import paho.mqtt.client as mqtt

from ferien import hole_schulfrei_zeitraeume, schulfrei_grund
import quellen
from schulmanager import QuelleNichtVerfuegbar

log = logging.getLogger("stundenplan.mqtt")

TAGE = ["mo", "di", "mi", "do", "fr"]
DISCOVERY_PREFIX = "homeassistant"
BASE_TOPIC = "stundenplan"
AVAILABILITY_TOPIC = f"{BASE_TOPIC}/status"

SENSOREN = [
    ("aktuelle_stunde", "Aktuelle Stunde", "mdi:school"),
    ("naechste_stunde", "Nächste Stunde", "mdi:arrow-right-circle"),
    ("erste_stunde_morgen", "Erste Stunde morgen", "mdi:weather-sunset-up"),
    ("schulschluss_heute", "Schulschluss heute", "mdi:home-clock"),
    ("wochenplan", "Wochenplan", "mdi:calendar-week"),
]


def plan_fuer_datum(kind: dict, datum) -> dict:
    """Plan-Version, die am gegebenen Datum gilt (Schuljahreswechsel).
    plaene: [{"gueltig_ab": iso, "plan": {...}}, ...]; Basis ist kind["plan"]."""
    d = datum.isoformat() if hasattr(datum, "isoformat") else str(datum)
    passend = sorted((p for p in kind.get("plaene", [])
                      if p.get("gueltig_ab", "9999") <= d),
                     key=lambda p: p["gueltig_ab"])
    return passend[-1]["plan"] if passend else kind.get("plan", {})


def slugify(name: str) -> str:
    s = name.lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        s = s.replace(a, b)
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_") or "kind"


def ist_im_block(kind: dict, datum: datetime) -> bool:
    if kind.get("modus") != "block":
        return True
    d = datum.date().isoformat()
    return any(b["von"] <= d <= b["bis"] for b in kind.get("bloecke", []))


def _fach_label(kz, faecher):
    f = faecher.get(kz)
    return f"{kz} – {f['name']}" if f else str(kz)


def _nr(stunde: dict):
    """Stundennummer aus dem Raster als int (Web-UI liefert teils Strings)."""
    try:
        return int(stunde.get("nr"))
    except (TypeError, ValueError):
        return None


def entfall_stunden(aenderungen: list, datum) -> set:
    """Stundennummern, die am Datum ersatzlos entfallen (kein Ersatzunterricht)."""
    iso = datum.isoformat() if hasattr(datum, "isoformat") else str(datum)[:10]
    nrs = set()
    for a in aenderungen or []:
        if str(a.get("datum", ""))[:10] != iso:
            continue
        if not (a.get("entfall") or a.get("typ") == "cancelledLesson"):
            continue
        try:
            nrs.add(int(a.get("stunde")))
        except (TypeError, ValueError):
            pass  # Entfall ohne Stundenbezug (z.B. ganzer Tag) - nicht zuordenbar
    return nrs


def belegte_stunden(plan: list, raster: list, entfall: set = None) -> list:
    """Indizes der tatsaechlich stattfindenden Stunden (Entfall zaehlt nicht)."""
    entfall = entfall or set()
    return [i for i, kz in enumerate(plan)
            if kz and i < len(raster) and _nr(raster[i]) not in entfall]


def berechne_sensoren(kind: dict, faecher: dict, raster: list, jetzt: datetime,
                      zeitraeume: list = None, aenderungen: list = None) -> dict:
    """Berechnet die vier Sensorwerte fuer ein Kind zum Zeitpunkt `jetzt`.

    zeitraeume: schulfreie Zeitraeume [{"von","bis","grund"}, ...].
    Sie gelten nur im Modus "wochenplan" - Azubis im Blockmodus haben in
    Schulferien Betrieb, keine freien Tage.
    aenderungen: Vertretungs-Overlay (heute/morgen) der Datenquelle. Entfallene
    Stunden gelten als frei - sie verschieben Schulbeginn und -schluss.
    """
    zeit = jetzt.strftime("%H:%M")
    zeitraeume = zeitraeume or []
    entfall_heute = entfall_stunden(aenderungen, jetzt.date())
    entfall_morgen = entfall_stunden(aenderungen, (jetzt + timedelta(days=1)).date())

    def tagesinfo(offset: int):
        d = jetzt + timedelta(days=offset)
        if kind.get("modus", "wochenplan") == "wochenplan":
            grund = schulfrei_grund(d.date(), zeitraeume)
            if grund:
                return None, f"Schulfrei ({grund})"
        if d.weekday() > 4:
            return None, "Schulfrei"
        if not ist_im_block(kind, d):
            return None, "Betrieb"
        plan = plan_fuer_datum(kind, d.date()).get(TAGE[d.weekday()], [])
        if not any(plan):
            return None, "Schulfrei"
        return plan, None

    heute, heute_status = tagesinfo(0)
    morgen, morgen_status = tagesinfo(1)

    res = {s[0]: "–" for s in SENSOREN}
    attrs = {"kind": kind["name"], "modus": kind.get("modus", "wochenplan")}

    # --- wochenplan: Anzahl Unterrichtsstunden Mo-Fr (aktuell gueltiger Plan) ---
    _p = plan_fuer_datum(kind, jetzt.date())
    res["wochenplan"] = sum(1 for tag in TAGE for kz in _p.get(tag, []) if kz)

    # --- erste_stunde_morgen (+ Materialliste morgen) ---
    if morgen is None:
        res["erste_stunde_morgen"] = morgen_status
    else:
        belegte_morgen = belegte_stunden(morgen, raster, entfall_morgen)
        if not belegte_morgen:
            res["erste_stunde_morgen"] = "Schulfrei (Entfall)"
        material = []
        for i in belegte_morgen:
            kz = morgen[i]
            if "morgen_erste_von" not in attrs:
                res["erste_stunde_morgen"] = f"{_fach_label(kz, faecher)} ({raster[i]['von']})"
                attrs["morgen_erste_von"] = raster[i]["von"]
            m = (faecher.get(kz, {}) or {}).get("material", "").strip()
            if m and m not in material:
                material.append(m)
        if material:
            attrs["material_morgen"] = ", ".join(material)

    # --- Tages-Sensoren ---
    if heute is None:
        res["aktuelle_stunde"] = heute_status
        res["naechste_stunde"] = heute_status
        res["schulschluss_heute"] = "–"
        return {"state": res, "attrs": attrs}

    geplant = belegte_stunden(heute, raster)
    belegte = belegte_stunden(heute, raster, entfall_heute)
    attrs["heute_stunden"] = len(belegte)
    if len(geplant) > len(belegte):
        attrs["heute_entfall"] = len(geplant) - len(belegte)

    if not belegte:
        # Alle Stunden des Tages entfallen - der Tag ist faktisch schulfrei
        res["aktuelle_stunde"] = "Schulfrei (Entfall)"
        res["naechste_stunde"] = "Schulfrei (Entfall)"
        res["schulschluss_heute"] = "–"
        attrs["schulschluss_regulaer"] = raster[geplant[-1]]["bis"]
        attrs["schulbeginn_heute"] = "–"
        return {"state": res, "attrs": attrs}

    erste, letzte = belegte[0], belegte[-1]
    res["schulschluss_heute"] = raster[letzte]["bis"]
    attrs["schulbeginn_heute"] = raster[erste]["von"]
    # Regulaere Zeiten mitliefern, wenn Randstunden entfallen ("statt 15:00")
    if raster[geplant[-1]]["bis"] != raster[letzte]["bis"]:
        attrs["schulschluss_regulaer"] = raster[geplant[-1]]["bis"]
    if raster[geplant[0]]["von"] != raster[erste]["von"]:
        attrs["schulbeginn_regulaer"] = raster[geplant[0]]["von"]

    # aktuelle_stunde
    if zeit < raster[erste]["von"] or zeit >= raster[letzte]["bis"]:
        res["aktuelle_stunde"] = "Kein Unterricht"
    else:
        res["aktuelle_stunde"] = "Pause"
        for i in belegte:
            if raster[i]["von"] <= zeit < raster[i]["bis"]:
                kz = heute[i]
                res["aktuelle_stunde"] = _fach_label(kz, faecher)
                f = faecher.get(kz, {})
                attrs.update({"aktuell_kuerzel": kz, "aktuell_raum": f.get("raum", ""),
                              "aktuell_bis": raster[i]["bis"], "aktuell_nr": raster[i]["nr"]})
                break
        else:
            # Freistunde durch Entfall mitten im Tag - nicht als "Pause" ausgeben
            if any(raster[i]["von"] <= zeit < raster[i]["bis"] for i in geplant
                   if i not in belegte):
                res["aktuelle_stunde"] = "Frei (Entfall)"

    # naechste_stunde
    for i in belegte:
        if raster[i]["von"] > zeit:
            kz = heute[i]
            res["naechste_stunde"] = f"{_fach_label(kz, faecher)} ({raster[i]['von']})"
            attrs["naechste_von"] = raster[i]["von"]
            break

    return {"state": res, "attrs": attrs}


class SensorPublisher:
    def __init__(self, load_data_fn):
        self._load_data = load_data_fn
        self._client = None
        self._bekannte_kids: set = set()
        self._letzter_state: dict = {}
        self._letzter_plan: dict = {}
        self._live_cache: dict = {}
        self._wakeup = threading.Event()
        self._connected = threading.Event()

    # ------------------------------------------------------------------
    def start(self) -> bool:
        host = os.environ.get("MQTT_HOST")
        if not host:
            log.warning("MQTT_HOST nicht gesetzt - Publisher inaktiv")
            return False
        port = int(os.environ.get("MQTT_PORT", 1883))
        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                                   client_id="stundenplan_manager")
        user = os.environ.get("MQTT_USER")
        if user:
            self._client.username_pw_set(user, os.environ.get("MQTT_PASSWORD", ""))
        self._client.will_set(AVAILABILITY_TOPIC, "offline", retain=True)
        self._client.on_connect = self._on_connect
        self._client.connect_async(host, port)
        self._client.loop_start()
        threading.Thread(target=self._loop, daemon=True).start()
        log.info("MQTT-Publisher gestartet (%s:%s)", host, port)
        return True

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        log.info("MQTT verbunden: %s", reason_code)
        client.publish(AVAILABILITY_TOPIC, "online", retain=True)
        self._letzter_state.clear()
        self._letzter_plan.clear()
        self._bekannte_kids.clear()
        self._connected.set()
        self._wakeup.set()

    def trigger(self):
        """Von save_data aufgerufen: sofortiges Update anstossen."""
        self._wakeup.set()

    # ------------------------------------------------------------------
    def _loop(self):
        while True:
            self._wakeup.wait(timeout=30)
            self._wakeup.clear()
            if not self._connected.is_set():
                continue
            try:
                self._publiziere_alle()
            except Exception:
                log.exception("Fehler beim Publizieren")

    def _publiziere_alle(self):
        data = self._load_data()
        faecher = data.get("faecher", {})
        std_raster = data.get("einstellungen", {}).get("stundenraster_standard", [])
        jetzt = datetime.now()
        einst = data.get("einstellungen", {})
        zeitraeume = hole_schulfrei_zeitraeume(
            einst.get("ferien_sensor", ""), einst.get("feiertag_sensor", ""))
        aktuelle_ids = set()

        for kind in data.get("kinder", []):
            kid = kind["id"]
            aktuelle_ids.add(kid)
            if kid not in self._bekannte_kids:
                self._discovery(kind)
                self._bekannte_kids.add(kid)
            raster = kind.get("stundenraster") or std_raster
            kind_faecher = quellen.faecher_fuer_kind(faecher, kind)

            genutzt = {kz for p in [kind.get("plan", {})] + [v.get("plan", {}) for v in kind.get("plaene", [])]
                       for tag in TAGE for kz in p.get(tag, []) if kz}
            aenderungen = []
            zusatz = {"hausaufgaben_offen": None, "naechste_arbeit": None}
            ha_faellig = []
            arbeiten = []
            if kind.get("schulmanager"):
                try:
                    aenderungen = quellen.hole_aenderungen(kind, jetzt.date())
                    zusatz = quellen.hole_zusatzinfos(kind)
                    bis = (jetzt.date() + timedelta(days=3)).isoformat()
                    ab = (jetzt.date() - timedelta(days=7)).isoformat()
                    ha_faellig = [h for h in quellen.hole_hausaufgaben_items(kind)
                                  if h["due"] and ab <= h["due"] <= bis][:8]
                    arbeiten = quellen.hole_arbeiten(kind)
                    self._live_cache[kind["id"]] = {
                        "ts": jetzt, "aenderungen": aenderungen, "zusatz": zusatz,
                        "ha_faellig": ha_faellig, "arbeiten": arbeiten}
                except Exception as exc:
                    # Quelle gestoert (z.B. Schulmanager-API down): letzten
                    # bekannten Stand bis zu 6h weiterzeigen statt die Karte
                    # leerzufegen. Die Datenstand-Zeile bleibt ehrlich alt.
                    cache = self._live_cache.get(kind["id"])
                    if cache and (jetzt - cache["ts"]).total_seconds() < 6 * 3600:
                        aenderungen = cache["aenderungen"]
                        zusatz = cache["zusatz"]
                        ha_faellig = cache["ha_faellig"]
                        arbeiten = cache["arbeiten"]
                        log.warning("Quelle fuer %s nicht verfuegbar (%s) - zeige Stand von %s weiter",
                                    kind["name"], exc.__class__.__name__,
                                    cache["ts"].strftime("%H:%M"))
                    else:
                        log.warning("Quelle fuer %s nicht verfuegbar (%s) - kein frischer Stand im Cache",
                                    kind["name"], exc.__class__.__name__)

            # Sensoren erst jetzt berechnen: entfallene Randstunden verschieben
            # Schulbeginn und Schulschluss
            ergebnis = berechne_sensoren(kind, kind_faecher, raster, jetzt,
                                         zeitraeume, aenderungen)
            if kind.get("schulmanager"):
                if zusatz["hausaufgaben_offen"] is not None:
                    ergebnis["attrs"]["hausaufgaben_offen"] = zusatz["hausaufgaben_offen"]
                if zusatz["naechste_arbeit"]:
                    ergebnis["attrs"]["naechste_arbeit"] = zusatz["naechste_arbeit"]
            payload = json.dumps(ergebnis["state"], ensure_ascii=False)
            attr_payload = json.dumps(ergebnis["attrs"], ensure_ascii=False)
            if self._letzter_state.get(kid) != (payload, attr_payload):
                self._client.publish(f"{BASE_TOPIC}/{kid}/state", payload, retain=True)
                self._client.publish(f"{BASE_TOPIC}/{kid}/attributes", attr_payload,
                                     retain=True)
                self._letzter_state[kid] = (payload, attr_payload)
                log.debug("Publiziert %s: %s", kind["name"], payload)

            plan_payload = json.dumps({
                "kind": kind["name"],
                "modus": kind.get("modus", "wochenplan"),
                "aenderungen": aenderungen,
                "hausaufgaben_offen": zusatz["hausaufgaben_offen"],
                "hausaufgaben_faellig": ha_faellig,
                "arbeiten": arbeiten,
                "daten_stand": quellen.hole_datenstand(kind) if kind.get("schulmanager") else None,
                "naechste_arbeit": zusatz["naechste_arbeit"],
                "schulfrei_zeitraeume": zeitraeume if kind.get("modus", "wochenplan") == "wochenplan" else [],
                "raster": raster,
                "plan": kind.get("plan", {}),
                "plaene": kind.get("plaene", []),
                "faecher": {kz: f for kz, f in kind_faecher.items() if kz in genutzt},
                "bloecke": kind.get("bloecke", []),
            }, ensure_ascii=False)
            if self._letzter_plan.get(kid) != plan_payload:
                self._client.publish(f"{BASE_TOPIC}/{kid}/plan", plan_payload, retain=True)
                self._letzter_plan[kid] = plan_payload

        # Geloeschte Kinder aufraeumen
        for kid in self._bekannte_kids - aktuelle_ids:
            for key, _, _ in SENSOREN:
                self._client.publish(
                    f"{DISCOVERY_PREFIX}/sensor/stundenplan_{kid}/{key}/config",
                    "", retain=True)
            self._client.publish(f"{BASE_TOPIC}/{kid}/state", "", retain=True)
            self._client.publish(f"{BASE_TOPIC}/{kid}/attributes", "", retain=True)
            self._client.publish(f"{BASE_TOPIC}/{kid}/plan", "", retain=True)
            self._letzter_state.pop(kid, None)
            self._letzter_plan.pop(kid, None)
        self._bekannte_kids = aktuelle_ids

    def _discovery(self, kind: dict):
        kid = kind["id"]
        slug = slugify(kind["name"])
        device = {
            "identifiers": [f"stundenplan_{kid}"],
            "name": f"Stundenplan {kind['name']}",
            "manufacturer": "Melle79",
            "model": "Stundenplan Manager",
        }
        for key, name, icon in SENSOREN:
            attr_topic = f"{BASE_TOPIC}/{kid}/plan" if key == "wochenplan" \
                else f"{BASE_TOPIC}/{kid}/attributes"
            payload = {
                "name": name,
                "unique_id": f"stundenplan_{kid}_{key}",
                "object_id": f"stundenplan_{slug}_{key}",
                "state_topic": f"{BASE_TOPIC}/{kid}/state",
                "value_template": "{{ value_json." + key + " }}",
                "json_attributes_topic": attr_topic,
                "availability_topic": AVAILABILITY_TOPIC,
                "icon": icon,
                "device": device,
            }
            self._client.publish(
                f"{DISCOVERY_PREFIX}/sensor/stundenplan_{kid}/{key}/config",
                json.dumps(payload, ensure_ascii=False), retain=True)
        log.info("Discovery publiziert fuer %s (%s)", kind["name"], slug)
