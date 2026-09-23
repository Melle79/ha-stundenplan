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
from mqtt_publisher import (TAGE, belegte_stunden, entfall_stunden,
                            ist_im_block, plan_fuer_datum, raster_fuer_kind)
import quellen

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


def _zeilen_fuer_kind(data: dict, kind: dict, jetzt: datetime,
                      mit_name: bool = True) -> list:
    """Push-Zeilen eines Kindes fuer den morgigen Tag ([] wenn frei/leer).

    mit_name=True stellt jeder Hauptzeile den Kindnamen voran (Sammel-Push
    fuer die Eltern); mit_name=False laesst ihn weg (persoenlicher Push ans
    Kind, der Name steht schon im Titel)."""
    einst = data.get("einstellungen", {})
    zeitraeume = hole_schulfrei_zeitraeume(
        einst.get("ferien_sensor", ""), einst.get("feiertag_sensor", ""))
    faecher = quellen.faecher_fuer_kind(data.get("faecher", {}), kind)
    std_raster = einst.get("stundenraster_standard", [])
    morgen = jetzt + timedelta(days=1)
    zeilen = []

    modus = kind.get("modus", "wochenplan")
    if modus == "wochenplan" and schulfrei_grund(morgen.date(), zeitraeume):
        return zeilen
    if morgen.weekday() > 4:
        return zeilen
    if modus == "block" and not ist_im_block(kind, morgen):
        return zeilen
    raster = raster_fuer_kind(kind, std_raster)
    plan = plan_fuer_datum(kind, morgen.date(), raster).get(TAGE[morgen.weekday()], [])
    geplant = belegte_stunden(plan, raster)
    if not geplant:
        return zeilen

    prefix = f"{kind['name']}: " if mit_name else ""

    # Bekannte Entfaelle fuer morgen kennen wir schon jetzt - sie
    # verschieben Schulbeginn und -schluss in der Nachricht
    morgen_iso = morgen.date().isoformat()
    aend_morgen = []
    if kind.get("schulmanager"):
        try:
            aend_morgen = [a for a in quellen.hole_aenderungen(kind, jetzt.date())
                           if a["datum"] == morgen_iso]
        except Exception:
            log.debug("Aenderungen fuer Push nicht abrufbar")
    belegte = belegte_stunden(plan, raster,
                              entfall_stunden(aend_morgen, morgen.date()))

    if not belegte:
        zeilen.append(f"{prefix}schulfrei – alle Stunden entfallen")
    else:
        erster_kz = plan[belegte[0]]
        f = faecher.get(erster_kz, {})
        beginn = raster[belegte[0]]["von"]
        schluss = raster[belegte[-1]]["bis"]
        if beginn != raster[geplant[0]]["von"]:
            beginn += f" (statt {raster[geplant[0]]['von']})"
        if schluss != raster[geplant[-1]]["bis"]:
            schluss += f" (statt {raster[geplant[-1]]['bis']})"
        zeile = (f"{prefix}{f.get('name', erster_kz)} um "
                 f"{beginn}, Schluss {schluss}")
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
            zusatz = quellen.hole_zusatzinfos(kind)
            ab = (jetzt.date() - timedelta(days=3)).isoformat()
            faellig = [h for h in quellen.hole_hausaufgaben_items(kind)
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
        for a in aend_morgen:
            detail = f"{a['stunde']}. Std {a['label']}" if a["stunde"] else a["label"]
            if a["fach"]:
                detail += f" {a['fach']}"
            if a.get("lehrer"):
                detail += f" bei {a['lehrer']}"
            if a["raum"]:
                detail += f" (Raum {a['raum']})"
            if a.get("grund"):
                detail += f" – {a['grund']}"
            zeilen.append(f"  ⚠ {detail}")

    return zeilen


def baue_nachricht(data: dict, jetzt: datetime) -> str:
    """Sammel-Nachricht (alle Kinder) fuer den morgigen Tag; leerer String
    wenn alle frei haben."""
    quellen.aktualisiere_quellen(data.get("kinder", []))
    zeilen = []
    for kind in data.get("kinder", []):
        zeilen += _zeilen_fuer_kind(data, kind, jetzt, mit_name=True)
    return "\n".join(zeilen)


def baue_nachricht_kind(data: dict, kind: dict, jetzt: datetime) -> str:
    """Persoenliche Nachricht fuer ein einzelnes Kind (ohne Namensprefix)."""
    quellen.aktualisiere_quellen([kind])
    return "\n".join(_zeilen_fuer_kind(data, kind, jetzt, mit_name=False))


def sende_push(service: str, nachricht: str, titel: str = "🎒 Schule morgen") -> bool:
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token or not service:
        return False
    body = json.dumps({"title": titel, "message": nachricht}).encode()
    req = urllib.request.Request(
        f"{API_URL}/services/notify/{service}", data=body, method="POST",
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10):
        pass
    log.info("Push gesendet an notify.%s (%d Zeilen)",
             service, nachricht.count("\n") + 1)
    return True


class PushScheduler:
    """Prueft alle 30s, ob die konfigurierte Push-Zeit erreicht ist."""

    def __init__(self, load_data_fn):
        self._load_data = load_data_fn
        self._stop = threading.Event()
        self._zuletzt_gesendet = None       # date (Sammel-Push)
        self._zuletzt_kind = {}             # kind_id -> date (Pro-Kind-Push)

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
        jetzt = datetime.now()
        hhmm = jetzt.strftime("%H:%M")

        # 1) Sammel-Push (alle Kinder an ein Geraet, fuer die Eltern)
        push = (data.get("einstellungen", {}) or {}).get("push", {}) or {}
        if push.get("aktiv") and push.get("service") \
                and hhmm == (push.get("zeit") or "19:00") \
                and self._zuletzt_gesendet != jetzt.date():
            self._zuletzt_gesendet = jetzt.date()
            nachricht = baue_nachricht(data, jetzt)
            if nachricht:
                sende_push(push["service"], nachricht)
            else:
                log.info("Morgen-Push uebersprungen: morgen haben alle frei")

        # 2) Pro-Kind-Push (jedes Kind an sein eigenes Geraet)
        for kind in data.get("kinder", []):
            kp = kind.get("push") or {}
            if not (kp.get("aktiv") and kp.get("service")):
                continue
            if hhmm != (kp.get("zeit") or "19:00"):
                continue
            if self._zuletzt_kind.get(kind.get("id")) == jetzt.date():
                continue
            self._zuletzt_kind[kind.get("id")] = jetzt.date()
            nachricht = baue_nachricht_kind(data, kind, jetzt)
            if nachricht:
                sende_push(kp["service"], nachricht,
                           titel=f"🎒 {kind.get('name', 'Schule')} – Schule morgen")
            else:
                log.info("Pro-Kind-Push %s uebersprungen: morgen frei",
                         kind.get("name"))
