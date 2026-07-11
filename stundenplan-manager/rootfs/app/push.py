"""Stundenplan Manager - optionaler Morgen-Push.

Sendet einmal taeglich (konfigurierbare Uhrzeit, default abends) eine gesammelte
Benachrichtigung ueber den morgigen Schultag aller Kinder an einen
HA-Notify-Service. Standardmaessig deaktiviert. An Tagen, an denen alle Kinder
frei haben, wird nichts gesendet.
"""
import json
import logging
import os
import threading
import urllib.request
from datetime import datetime, timedelta

from ferien import hole_schulfrei_zeitraeume, schulfrei_grund, API_URL
from mqtt_publisher import TAGE, ist_im_block, plan_fuer_datum
from schulmanager import hole_aenderungen, hole_hausaufgaben_items, hole_zusatzinfos

log = logging.getLogger("stundenplan.push")


def liste_notify_services() -> list:
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        return []
    req = urllib.request.Request(f"{API_URL}/services",
                                 headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=10) as r:
        domains = json.load(r)
    dienste = []
    for d in domains:
        if d.get("domain") == "notify":
            for name in (d.get("services") or {}):
                if name != "notify" or len(d["services"]) == 1:
                    dienste.append(name)
    return sorted(dienste)


def baue_nachricht(data: dict, jetzt: datetime) -> str:
    """Zeilen fuer den morgigen Tag; leerer String wenn alle frei haben."""
    einst = data.get("einstellungen", {})
    zeitraeume = hole_schulfrei_zeitraeume(
        einst.get("ferien_sensor", ""), einst.get("feiertag_sensor", ""))
    faecher = data.get("faecher", {})
    std_raster = einst.get("stundenraster_standard", [])
    morgen = jetzt + timedelta(days=1)
    zeilen = []

    for kind in data.get("kinder", []):
        modus = kind.get("modus", "wochenplan")
        if modus == "wochenplan" and schulfrei_grund(morgen.date(), zeitraeume):
            continue
        if morgen.weekday() > 4:
            continue
        if modus == "block" and not ist_im_block(kind, morgen):
            continue
        plan = plan_fuer_datum(kind, morgen.date()).get(TAGE[morgen.weekday()], [])
        raster = kind.get("stundenraster") or std_raster
        belegte = [i for i, kz in enumerate(plan) if kz and i < len(raster)]
        if not belegte:
            continue
        erster_kz = plan[belegte[0]]
        f = faecher.get(erster_kz, {})
        zeile = (f"{kind['name']}: {f.get('name', erster_kz)} um "
                 f"{raster[belegte[0]]['von']}, Schluss {raster[belegte[-1]]['bis']}")
        material = []
        for i in belegte:
            m = (faecher.get(plan[i], {}) or {}).get("material", "").strip()
            if m and m not in material:
                material.append(m)
        if material:
            zeile += " – 🎒 " + ", ".join(material)
        zeilen.append(zeile)
        if kind.get("schulmanager"):
            try:
                zusatz = hole_zusatzinfos(kind["schulmanager"])
                ab = (jetzt.date() - timedelta(days=3)).isoformat()
                faellig = [h for h in hole_hausaufgaben_items(kind["schulmanager"])
                           if h["due"] and ab <= h["due"] <= morgen.date().isoformat()]
                if faellig:
                    kurz = [h["titel"][:40] for h in faellig[:3] if h["titel"]]
                    rest = len(faellig) - len(kurz)
                    zeilen.append("  📚 Bis morgen: " + "; ".join(kurz)
                                  + (f" (+{rest} weitere)" if rest > 0 else ""))
                elif (zusatz.get("hausaufgaben_offen") or 0) > 0:
                    zeilen.append(f"  📚 {zusatz['hausaufgaben_offen']} offene Hausaufgaben")
                arbeit = zusatz.get("naechste_arbeit")
                if arbeit and arbeit["datum"] == morgen.date().isoformat():
                    zeilen.append(f"  📝 {arbeit['typ']} {arbeit['fach']} morgen!")
            except Exception:
                log.debug("Zusatzinfos fuer Push nicht abrufbar")
            try:
                morgen_iso = morgen.date().isoformat()
                for a in hole_aenderungen(kind["schulmanager"], jetzt.date()):
                    if a["datum"] != morgen_iso:
                        continue
                    detail = f"{a['stunde']}. Std {a['label']}" if a["stunde"] else a["label"]
                    if a["fach"]:
                        detail += f" {a['fach']}"
                    if a["raum"]:
                        detail += f" (Raum {a['raum']})"
                    zeilen.append(f"  ⚠ {detail}")
            except Exception:
                log.debug("Aenderungen fuer Push nicht abrufbar")

    return "\n".join(zeilen)


def sende_push(service: str, nachricht: str) -> bool:
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token or not service:
        return False
    body = json.dumps({"title": "🎒 Schule morgen",
                       "message": nachricht}).encode()
    req = urllib.request.Request(
        f"{API_URL}/services/notify/{service}", data=body, method="POST",
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10):
        pass
    log.info("Morgen-Push gesendet an notify.%s (%d Zeilen)",
             service, nachricht.count("\n") + 1)
    return True


class PushScheduler:
    """Prueft alle 30s, ob die konfigurierte Push-Zeit erreicht ist."""

    def __init__(self, load_data_fn):
        self._load_data = load_data_fn
        self._stop = threading.Event()
        self._zuletzt_gesendet = None  # date

    def start(self):
        threading.Thread(target=self._loop, daemon=True).start()
        log.info("Push-Scheduler gestartet")

    def _loop(self):
        while not self._stop.wait(30):
            try:
                self._tick()
            except Exception:
                log.exception("Fehler im Push-Scheduler")

    def _tick(self):
        data = self._load_data()
        push = (data.get("einstellungen", {}) or {}).get("push", {}) or {}
        if not push.get("aktiv") or not push.get("service"):
            return
        jetzt = datetime.now()
        if jetzt.strftime("%H:%M") != (push.get("zeit") or "19:00"):
            return
        if self._zuletzt_gesendet == jetzt.date():
            return
        self._zuletzt_gesendet = jetzt.date()
        nachricht = baue_nachricht(data, jetzt)
        if nachricht:
            sende_push(push["service"], nachricht)
        else:
            log.info("Morgen-Push uebersprungen: morgen haben alle frei")
