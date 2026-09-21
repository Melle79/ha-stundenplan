"""Stundenplan Manager - Quellen-Dispatcher.

Ein Kind ist ueber kind["schulmanager"] (Basis-Entity) mit einer Datenquelle
verknuepft; kind["quelle"] bestimmt den Adapter ("schulmanager" ist der
Default fuer Bestandsdaten). Alle Aufrufer (sync, push, server) nutzen
ausschliesslich dieses Modul - die Adapter bleiben austauschbar.
"""
from datetime import date

import elternportal
import schulmanager
import untis

_ADAPTER = {"schulmanager": schulmanager, "elternportal": elternportal,
            "untis": untis}
QUELLEN_LABEL = {"schulmanager": "Schulmanager", "elternportal": "Eltern-Portal",
                 "untis": "WebUntis"}


def _adapter(kind: dict):
    return _ADAPTER.get(kind.get("quelle") or "schulmanager", schulmanager)


def label(kind: dict) -> str:
    return QUELLEN_LABEL.get(kind.get("quelle") or "schulmanager",
                             "Schulmanager")


def liste_schueler() -> list:
    """Schueler beider Quellen: [{"entity_id","basis","name","quelle"}]."""
    ergebnis = []
    for quelle, adapter in _ADAPTER.items():
        try:
            eintraege = adapter.liste_schueler()
        except Exception:
            eintraege = []
        for e in eintraege:
            e["quelle"] = quelle
            ergebnis.append(e)
    ergebnis.sort(key=lambda t: t["name"].lower())
    return ergebnis


def hole_wochenplan(kind: dict) -> dict:
    a = _adapter(kind)
    if a is schulmanager:
        return a.hole_wochenplan(f"{kind['schulmanager']}_wochenplan_json")
    return a.hole_wochenplan(kind["schulmanager"])


def hole_fach_details(kind: dict) -> dict:
    return _adapter(kind).hole_fach_details(kind["schulmanager"])


def hole_tagesplaene(kind: dict) -> dict:
    return _adapter(kind).hole_tagesplaene(kind["schulmanager"])


def hole_aenderungen(kind: dict, heute: date) -> list:
    return _adapter(kind).hole_aenderungen(kind["schulmanager"], heute)


def hole_hausaufgaben_items(kind: dict) -> list:
    return _adapter(kind).hole_hausaufgaben_items(kind["schulmanager"])


def hole_arbeiten(kind: dict) -> list:
    return _adapter(kind).hole_arbeiten(kind["schulmanager"])


def hole_schultermine(kind: dict) -> list:
    """Schulweite Termine, sofern die Quelle sie anbietet (nur Schulmanager);
    andere Adapter liefern nichts."""
    fn = getattr(_adapter(kind), "hole_schultermine", None)
    return fn(kind["schulmanager"]) if fn else []


def hole_zusatzinfos(kind: dict) -> dict:
    return _adapter(kind).hole_zusatzinfos(kind["schulmanager"])


def faecher_fuer_kind(faecher: dict, kind: dict) -> dict:
    """Effektive Faecher eines Kindes: globale Faecher als Standard, ueberlagert
    von den kindspezifischen Angaben aus kind["fach_details"].

    Name/Farbe/Material sind kindbezogen ueberschreibbar (gleiches Kuerzel kann
    bei verschiedenen Kindern ein anderes Fach sein, z.B. "Sw" = Schwimmen vs.
    Sport weiblich); Raum/Lehrer sind ohnehin kindspezifisch. Kuerzel, die es
    nur in fach_details gibt (z.B. aus WebUntis), werden mitgefuehrt."""
    det = kind.get("fach_details") or {}
    ergebnis = {}
    for kz in set(faecher) | set(det):
        g = dict(faecher.get(kz) or {})
        d = det.get(kz) or {}
        for feld in ("name", "farbe", "material"):
            if d.get(feld):
                g[feld] = d[feld]
        g.setdefault("name", kz)
        g.setdefault("farbe", "#888888")
        g["raum"] = d.get("raum", "")
        g["lehrer"] = d.get("lehrer", "")
        ergebnis[kz] = g
    return ergebnis


def aktualisiere_quellen(kinder: list, **kw) -> None:
    """Stoesst je beteiligter Quelle einen Datenabruf an (falls der Adapter
    das anbietet, z.B. Eltern-Portal-fetch). Ein Aufruf pro Quelle genuegt,
    da die Integrationen alle Instanzen gemeinsam aktualisieren."""
    erledigt = set()
    for kind in kinder:
        if not kind.get("schulmanager"):
            continue
        quelle = kind.get("quelle") or "schulmanager"
        if quelle in erledigt:
            continue
        erledigt.add(quelle)
        adapter = _ADAPTER.get(quelle)
        fetch = getattr(adapter, "fetch_daten", None)
        if fetch:
            try:
                fetch(kind["schulmanager"], **kw)
            except Exception:
                pass


def hole_datenstand(kind: dict):
    try:
        return _adapter(kind).hole_datenstand(kind["schulmanager"])
    except Exception:
        return None
