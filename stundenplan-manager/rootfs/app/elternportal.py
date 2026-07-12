"""Stundenplan Manager - Adapter fuer die Eltern-Portal-Integration
(workFLOw42/Elternportal_API).

Gleiches Interface wie schulmanager.py, gespeist aus den Sensoren
sensor.<slug>_<kind>_stundenplan / _schulaufgaben / _schulinformationen.

Eigenheiten der Quelle:
  - Zeiten mit Punkten ("08.00 - 08.45")
  - Zellen mehrzeilig ("KUERZEL\\nRAUM"), Splitfaecher "K/Ev/Eth" mit
    Raeumen "O28/O32/O21" - Splitfaecher werden als Kombi-Fach uebernommen
  - Kein Vertretungs-/Hausaufgaben-Sensor -> Aenderungen/Todos leer
  - Lehrer je Fach aus dem teachers-Block (Fach-Vollname -> Lehrer-Vollname),
    Kuerzel via Schulinformationen ("Stundenplankuerzel der Lehrkraefte")
  - Arbeiten aus Fliesstext ("Schulaufgabe in Mathematik (Loe)")
"""
import json
import logging
import os
import re
import urllib.request
from datetime import date

from schulmanager import API_URL, _hole_state

log = logging.getLogger("stundenplan.elternportal")

STUNDENPLAN_MUSTER = re.compile(r"^sensor\..+_stundenplan$")
TAGE_MAP = {"Montag": "mo", "Dienstag": "di", "Mittwoch": "mi",
            "Donnerstag": "do", "Freitag": "fr"}
ARBEIT_MUSTER = re.compile(
    r"^(?P<typ>.+?) in (?P<fach>.+?)(?:\s*\([^)]*\))*\s*\((?P<krz>[^)]+)\)\s*$")


def _bloecke(basis: str) -> dict:
    """{'timetable': [...], 'teachers': [...]} aus dem Stundenplan-Sensor."""
    d = _hole_state(f"{basis}_stundenplan")
    ergebnis = {}
    for block in (d.get("attributes") or {}).get("entries") or []:
        ergebnis[block.get("type")] = block.get("entries") or []
    return ergebnis


def _zelle(wert: str):
    """'E\\nO21' -> ('E', 'O21'); Raum-Kombis von leeren Teilen bereinigt."""
    zeilen = [z.strip() for z in str(wert or "").splitlines() if z.strip()]
    kz = zeilen[0] if zeilen else ""
    raum = ""
    if len(zeilen) > 1:
        raum = "/".join(t for t in zeilen[1].split("/") if t.strip())
    return kz, raum


def _zeit(t: str) -> str:
    """'08.00' -> '08:00'"""
    return t.strip().replace(".", ":")


def liste_schueler() -> list:
    """Alle Eltern-Portal-Kinder: [{"entity_id","basis","name"}]."""
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
        if not STUNDENPLAN_MUSTER.match(eid):
            continue
        attrs = s.get("attributes") or {}
        entries = attrs.get("entries")
        if not isinstance(entries, list) or not any(
                isinstance(b, dict) and b.get("type") == "timetable"
                for b in entries):
            continue
        name = attrs.get("child_name") or attrs.get("friendly_name") or eid
        if attrs.get("class_name"):
            name = f"{name} ({attrs['class_name']})"
        treffer.append({"entity_id": eid,
                        "basis": eid[:-len("_stundenplan")],
                        "name": name})
    treffer.sort(key=lambda t: t["name"].lower())
    return treffer


def hole_wochenplan(basis: str) -> dict:
    """Kompletter Wochenplan aus dem timetable-Block.

    Rueckgabe wie schulmanager.hole_wochenplan:
    {"kw", "raster": [{nr, von, bis}], "plan": {mo..fr}, "kuerzel"}
    """
    rows = _bloecke(basis).get("timetable") or []
    raster = []
    plan = {t: [] for t in TAGE_MAP.values()}
    kuerzel = []
    for row in rows:
        try:
            nr = int(str(row.get("period", "")).rstrip(". "))
        except ValueError:
            continue
        von, _, bis = str(row.get("time", "")).partition("-")
        raster.append({"nr": nr, "von": _zeit(von), "bis": _zeit(bis)})
        for tag_name, kurz in TAGE_MAP.items():
            kz, _raum = _zelle(row.get(tag_name))
            plan[kurz].append(kz or None)
            if kz and kz not in kuerzel:
                kuerzel.append(kz)
    return {"kw": "Eltern-Portal", "raster": raster, "plan": plan,
            "kuerzel": kuerzel}


def _lehrer_kuerzel_map(basis: str) -> dict:
    """Lehrer-Vollname -> Stundenplankuerzel aus den Schulinformationen."""
    try:
        d = _hole_state(f"{basis}_schulinformationen")
    except Exception:
        return {}
    ergebnis = {}
    for e in (d.get("attributes") or {}).get("entries") or []:
        if "kürzel" in str(e.get("section", "")).lower():
            name = str(e.get("value", "")).strip()
            if name:
                ergebnis[name] = str(e.get("label", "")).strip()
    return ergebnis


def _initialen(text: str) -> str:
    return "".join(w[0] for w in re.split(r"\s+", text) if w)


# Gaengige Fachkuerzel bayerischer Gymnasien (Stamm -> Fach-Vollname wie im
# teachers-Block). Deterministisch; die Heuristik greift nur als Fallback.
KUERZEL_STANDARD = {
    "d": "Deutsch", "e": "Englisch", "m": "Mathematik", "f": "Französisch",
    "l": "Latein", "sp": "Spanisch", "g": "Geschichte", "geo": "Geographie",
    "ek": "Geographie", "ku": "Kunst", "mu": "Musik", "k": "Kath. Religionslehre",
    "ev": "Evang. Religionslehre", "eth": "Ethik", "nut": "Natur und Technik",
    "b": "Biologie", "c": "Chemie", "ph": "Physik", "inf": "Informatik",
    "wr": "Wirtschaft und Recht", "pug": "Politik und Gesellschaft",
    "sm": "Sport", "sw": "Sport", "spo": "Sport",
}


def hole_fach_details(basis: str) -> dict:
    """Raum (aus timetable), Name + Lehrer (aus teachers-Block) je Kuerzel.

    Fachname-Zuordnung ist Best-Effort: Kuerzel-Stamm gegen Fach-Vollnamen
    (startswith bzw. Initialen wie NuT), Mehrdeutigkeiten werden ueber
    laengere Kuerzel zuerst aufgeloest; Unklares bleibt leer.
    Rueckgabe: {KZ_UPPER: {"raum","lehrer","name"}}
    """
    bloecke = _bloecke(basis)
    details = {}
    for row in bloecke.get("timetable") or []:
        for tag_name in TAGE_MAP:
            kz, raum = _zelle(row.get(tag_name))
            if not kz:
                continue
            eintrag = details.setdefault(kz.upper(),
                                         {"raum": "", "lehrer": "", "name": ""})
            if not eintrag["raum"] and raum:
                eintrag["raum"] = raum

    faecher = []  # [(vollname, lehrer_vollname)] dedupliziert nach vollname
    gesehen = set()
    for t in bloecke.get("teachers") or []:
        voll = str(t.get("subject", "")).strip()
        voll = voll.split(", ")[-1]  # "6_F_6E_Bay, Franzoesisch" -> Vollname
        if voll and voll not in gesehen:
            gesehen.add(voll)
            faecher.append((voll, str(t.get("teacher", "")).strip()))
    krz_map = _lehrer_kuerzel_map(basis)

    fach_lehrer = dict(faecher)  # Vollname -> Lehrer (erster Eintrag)
    verbraucht = set()
    for kz in sorted(details, key=lambda k: -len(k.split("_")[0])):
        stamm = kz.split("_")[0]
        if "/" in stamm:
            continue  # Splitfaecher nicht raten
        voll = None
        standard = KUERZEL_STANDARD.get(stamm.lower())
        if standard and standard in fach_lehrer:
            voll = standard
        else:
            kandidaten = [v for v, _ in faecher
                          if v.lower().startswith(stamm.lower())
                          or _initialen(v).lower() == stamm.lower()]
            if len(kandidaten) > 1:
                kandidaten = [v for v in kandidaten if v not in verbraucht]
            if len(kandidaten) == 1:
                voll = kandidaten[0]
        if not voll:
            continue
        lehrer_voll = fach_lehrer.get(voll, "")
        verbraucht.add(voll)
        details[kz]["name"] = voll
        # Kuerzel-Lookup titel-tolerant ("Dr. des. Elisabeth Perzl" vs.
        # "Elisabeth Perzl"); Nachname als letzter Fallback
        kuerzel = krz_map.get(lehrer_voll) or next(
            (k for name, k in krz_map.items()
             if name and lehrer_voll.endswith(name)), "")
        details[kz]["lehrer"] = kuerzel \
            or (lehrer_voll.split()[-1] if lehrer_voll else "")
    return details


def hole_tagesplaene(basis: str) -> dict:
    """Eltern-Portal liefert keine Tagesplaene - der Wochenplan ist bereits
    der Originalplan."""
    return {}


def hole_aenderungen(basis: str, heute: date) -> list:
    """Kein Vertretungssensor in dieser Integration."""
    return []


def hole_hausaufgaben_items(basis: str) -> list:
    """Keine Hausaufgaben im Eltern-Portal."""
    return []


def hole_arbeiten(basis: str, heute: date = None) -> list:
    """Anstehende Arbeiten aus dem Schulaufgaben-Sensor.

    Parst 'Schulaufgabe in Mathematik (Loe)' bzw. Varianten mit
    Gruppenklammern; Kuerzel wird ueber die Fach-Details rueckabgebildet.
    Rueckgabe wie schulmanager.hole_arbeiten:
    [{"datum","fach","kuerzel","typ"}], nur zukuenftige.
    """
    heute = heute or date.today()
    try:
        d = _hole_state(f"{basis}_schulaufgaben")
    except Exception as exc:
        log.debug("Schulaufgaben fuer %s nicht abrufbar: %s", basis, exc)
        return []
    try:
        det = hole_fach_details(basis)
        name_zu_kz = {}
        for kz in sorted(det, key=len):  # kuerzestes Kuerzel je Fach gewinnt
            if det[kz].get("name"):
                name_zu_kz.setdefault(det[kz]["name"].lower(), kz)
    except Exception:
        name_zu_kz = {}
    arbeiten = []
    for e in (d.get("attributes") or {}).get("entries") or []:
        try:
            t, m, j = str(e.get("date", "")).split(".")
            datum = f"{j}-{m.zfill(2)}-{t.zfill(2)}"
        except ValueError:
            continue
        if datum < heute.isoformat():
            continue
        m = ARBEIT_MUSTER.match(str(e.get("description", "")).strip())
        if m:
            typ, fach = m.group("typ").strip(), m.group("fach").strip()
        else:
            typ, fach = "Arbeit", str(e.get("description", "")).strip()
        arbeiten.append({"datum": datum, "fach": fach,
                         "kuerzel": name_zu_kz.get(fach.lower(), ""),
                         "typ": typ})
    arbeiten.sort(key=lambda x: x["datum"])
    return arbeiten


def hole_zusatzinfos(basis: str) -> dict:
    """Naechste Arbeit fuer den Morgen-Push (Hausaufgaben gibt es nicht)."""
    info = {"hausaufgaben_offen": None, "naechste_arbeit": None}
    try:
        kommende = hole_arbeiten(basis)
    except Exception:
        kommende = []
    if kommende:
        a = kommende[0]
        delta = (date.fromisoformat(a["datum"]) - date.today()).days
        info["naechste_arbeit"] = {"datum": a["datum"], "in_tagen": delta,
                                   "fach": a["fach"], "typ": a["typ"]}
    return info
