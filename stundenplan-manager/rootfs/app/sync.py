"""Stundenplan Manager - Schulmanager-Import als Backend-Logik.

Eine Merge-Funktion fuer beide Wege: den Import-Button in der Web-UI und den
optionalen taeglichen Auto-Import (pro Kind aktivierbar, kind["auto_import"]).

Merge-Regeln:
  - Nur in Schulmanager befuellte Tage ersetzen, leere bleiben unangetastet
  - Faecher: case-insensitives Kuerzel-Matching; neue Faecher werden mit
    Name/Raum/Lehrer aus den Detail-Sensoren angelegt, bei bestehenden werden
    nur leere Felder ergaenzt - nichts wird ueberschrieben
  - Zielversion ist die am Import-Tag gueltige Planversion
  - Das Stundenraster wird nur gesetzt, wenn das Kind noch keines hat
"""
import logging
import threading
from datetime import date, datetime, timedelta

import quellen

log = logging.getLogger("stundenplan.sync")

FARBPALETTE = ["#e05d5d", "#4a90d9", "#e0b34c", "#4caf7d", "#9b6dd6", "#26a69a",
               "#ec407a", "#5c6bc0", "#ef6c00", "#8d6e63", "#29b6f6", "#ab47bc",
               "#7cb342", "#90a4ae"]
TAG_NAMEN = {"mo": "Mo", "di": "Di", "mi": "Mi", "do": "Do", "fr": "Fr"}


def _verz_key(verz: dict, kuerzel: str) -> str:
    """Findet den bestehenden Verzeichnis-Schluessel case-insensitiv oder
    legt das Kuerzel neu an (leerer Klarname, zum Handbefuellen)."""
    treffer = next((k for k in verz if k.lower() == kuerzel.lower()), None)
    if treffer is None:
        verz[kuerzel] = ""
        return kuerzel
    return treffer


def lehrer_verzeichnis_pflegen(kind: dict, kuerzel: str, klarname: str,
                               stats: dict) -> None:
    """Pflegt kind["lehrer_namen"] (Lehrer-Kuerzel -> Klarname).

    - Das Kuerzel wird immer angelegt (Auto-Entdeckung), damit es in der
      Web-UI zum Befuellen erscheint.
    - Einen Klarname aus der Quelle (Eltern-Portal) uebernimmt/korrigiert das
      Verzeichnis automatisch - es sei denn, er wurde von Hand abweichend
      gesetzt (Merker-Prinzip wie bei Raum/Lehrer). Schulmanager liefert
      keinen Klarname; dort bleibt der Handeintrag unangetastet.
    """
    kuerzel = (kuerzel or "").strip()
    if not kuerzel:
        return
    verz = kind.setdefault("lehrer_namen", {})
    key = _verz_key(verz, kuerzel)
    klarname = (klarname or "").strip()
    if not klarname:
        return
    quelle = kind.setdefault("lehrer_namen_quelle", {})
    aktuell = verz.get(key, "")
    darf = (not aktuell) or aktuell == quelle.get(key, "")
    if darf and aktuell != klarname:
        verz[key] = klarname
        stats["geaendert"] = True
    if quelle.get(key) != klarname:
        quelle[key] = klarname
        stats["geaendert"] = True


def _zielplan(kind: dict, heute: date) -> dict:
    """Die am Stichtag gueltige Planversion (Objekt-Referenz aus kind)."""
    d = heute.isoformat()
    passend = sorted((p for p in kind.get("plaene", [])
                      if p.get("gueltig_ab", "9999") <= d),
                     key=lambda p: p["gueltig_ab"])
    return passend[-1]["plan"] if passend else kind.setdefault("plan", {})


def fuehre_import_aus(data: dict, kind: dict, heute: date = None) -> dict:
    """Mutiert data/kind. Rueckgabe-Stats:
    {geaendert, kw, importiert, uebersprungen, neue_faecher, ergaenzt,
     raster_gesetzt}

    Planquelle je Tag: originalbereinigter Tagesplan (heute/morgen-Sensoren,
    bei Aenderungen zaehlt das Original-Fach) - Tage ohne Tagesdaten kommen
    aus dem Wochenplan-JSON. Nur tatsaechlich verwendete Kuerzel werden als
    Faecher angelegt; Vertretungsfaecher landen weder im Plan noch in der
    Faecherliste."""
    heute = heute or date.today()
    wp = quellen.hole_wochenplan(kind)
    try:
        details = quellen.hole_fach_details(kind)
    except Exception:
        details = {}
    try:
        tagesplaene = quellen.hole_tagesplaene(kind)
    except Exception:
        tagesplaene = {}

    stats = {"geaendert": False, "kw": wp.get("kw", ""), "importiert": [],
             "uebersprungen": [], "neue_faecher": 0, "ergaenzt": 0,
             "raster_gesetzt": False}
    raster = kind.get("stundenraster") or wp["raster"] \
        or (data.get("einstellungen", {}) or {}).get("stundenraster_standard") or []
    if not raster:
        return stats

    kfd = kind.setdefault("fach_details", {})

    def fach_sicherstellen(kz):
        """Kanonisches Kuerzel im Faecher-Katalog dieses Kindes; legt das Fach
        (Name/Farbe/Material) bei Bedarf kindspezifisch an. Raum/Lehrer wandern
        mit Merker-Prinzip in denselben Eintrag."""
        det = details.get(kz.upper(), {})
        match = next((v for v in kfd if v.upper() == kz.upper()), None)
        if not match:
            match = kz
            idx = len(kfd)
            neu = kfd.setdefault(kz, {})
            neu["name"] = det.get("name") or kz
            neu["farbe"] = FARBPALETTE[idx % len(FARBPALETTE)]
            neu["material"] = ""
            stats["neue_faecher"] += 1
            stats["geaendert"] = True
        eintrag = kfd.setdefault(match, {})
        # Name kindbezogen (gleiches Kuerzel kann je Kind ein anderes Fach sein),
        # daneben Raum/Lehrer - alle mit Merker-Prinzip (Handeintrag gewinnt).
        for feld in ("name", "raum", "lehrer"):
            neu_wert = det.get(feld)
            if not neu_wert:
                continue
            darf = not eintrag.get(feld) \
                or eintrag.get(feld) == eintrag.get(f"sm_{feld}")
            if darf and eintrag.get(feld) != neu_wert:
                eintrag[feld] = neu_wert
                stats["ergaenzt"] += 1
                stats["geaendert"] = True
            if eintrag.get(f"sm_{feld}") != neu_wert:
                eintrag[f"sm_{feld}"] = neu_wert
                stats["geaendert"] = True
        # Lehrerverzeichnis pflegen: Kuerzel entdecken, Klarname (nur
        # Eltern-Portal) automatisch fuellen/korrigieren
        teacher_kz = (eintrag.get("lehrer") or det.get("lehrer") or "").strip()
        if teacher_kz:
            lehrer_verzeichnis_pflegen(kind, teacher_kz,
                                       det.get("lehrer_name") or "", stats)
        # Raumliste des Kindes pflegen (Auswahl im Stunden-Editor, Drag&Drop)
        raum = (eintrag.get("raum") or "").strip()
        if raum:
            rl = kind.setdefault("raeume", [])
            if raum not in rl:
                rl.append(raum)
                rl.sort(key=lambda s: s.lower())
                stats["geaendert"] = True
        return match

    # Datumsgenauer Modus (optional pro Kind): NICHT auf einen Wochenplan falten
    # - das wuerde bei jedem Import die zuletzt gezeigte Woche ueberschreiben.
    # Stattdessen jede echte Kalenderstunde an ihrem Datum ablegen; jede Woche
    # bleibt so erhalten (Archiv). Der Wochenplan bleibt als Reserve unangetastet.
    if kind.get("datumsplan"):
        _import_datumsplan(kind, heute, details, fach_sicherstellen, stats)
        return stats

    # Finalen Plan je Tag bestimmen: Tagesplan schlaegt Wochen-JSON
    nr_index = {st["nr"]: i for i, st in enumerate(raster)}
    tage_namen = ["mo", "di", "mi", "do", "fr"]
    final = {}
    for datum, stunden in tagesplaene.items():
        wd = date.fromisoformat(datum).weekday()
        if wd > 4:
            continue
        neu_tag = [None] * len(raster)
        for nr, kz in stunden.items():
            idx = nr_index.get(nr)
            if idx is not None:
                neu_tag[idx] = kz
        if any(neu_tag):
            final[tage_namen[wd]] = neu_tag
    for tag, stunden in wp["plan"].items():
        if tag not in final and any(stunden):
            final[tag] = list(stunden)

    ziel = _zielplan(kind, heute)
    # Overlay "freie Stunden" mitschreiben: jede importierte Zelle bekommt Raum
    # und Lehrer aus dem (kindspezifischen) Fach-Standard. So ersetzt ein Import,
    # der eine Stunde auf ein anderes Fach aendert, auch den alten Raum/Lehrer -
    # sonst bliebe ein veraltetes Overlay massgeblich stehen.
    ziel_det = ziel.setdefault("details", {})
    for tag in tage_namen:
        if tag not in final:
            stats["uebersprungen"].append(TAG_NAMEN[tag])
            continue
        neu_tag, neu_det = [], []
        for kz in final[tag]:
            if not kz:
                neu_tag.append(None)
                neu_det.append(None)
                continue
            match = fach_sicherstellen(kz)
            neu_tag.append(match)
            eintrag = (kind.get("fach_details") or {}).get(match, {})
            raum = (eintrag.get("raum") or "").strip()
            lehrer = (eintrag.get("lehrer") or "").strip()
            neu_det.append({"raum": raum, "lehrer": lehrer} if (raum or lehrer) else None)
        if ziel.get(tag) != neu_tag:
            ziel[tag] = neu_tag
            stats["geaendert"] = True
        if ziel_det.get(tag) != neu_det:
            ziel_det[tag] = neu_det
            stats["geaendert"] = True
        stats["importiert"].append(TAG_NAMEN[tag])

    # Stundenraster: eigenes Raster automatisch anlegen, wenn die
    # Schulmanager-Zeiten vom Standard abweichen. Merker-Prinzip wie bei
    # Raum/Lehrer: ein vom Import gesetztes Raster folgt spaeteren
    # Aenderungen der Schule, ein handgepflegtes bleibt unangetastet.
    sm_raster = wp["raster"]
    if sm_raster:
        std = (data.get("einstellungen", {}) or {}).get("stundenraster_standard") or []
        eigenes = kind.get("stundenraster")
        erst_import = kind.get("sm_raster") is None
        if eigenes is None:
            if sm_raster != std:
                kind["stundenraster"] = sm_raster
                kind["sm_raster"] = sm_raster
                stats["raster_gesetzt"] = True
                stats["geaendert"] = True
        elif erst_import or eigenes == kind.get("sm_raster"):
            # Erstimport von dieser Quelle (oder ein vom Import gesetztes Raster):
            # die echten Schulzeiten uebernehmen. Ein *nach* dem Import von Hand
            # geaendertes Raster (eigenes != sm_raster) bleibt dagegen geschuetzt.
            if sm_raster != eigenes:
                kind["stundenraster"] = sm_raster
                stats["raster_gesetzt"] = True
                stats["geaendert"] = True
            if kind.get("sm_raster") != sm_raster:
                kind["sm_raster"] = sm_raster
                stats["geaendert"] = True

    # Vertretungslehrer entdecken: Kuerzel, die nur in einer Vertretung vorkommen,
    # tauchen sonst nie in der Lehrernamen-Tabelle auf - man koennte sie also nicht
    # benennen. Sie werden hier (mit leerem Klarnamen) angelegt, damit sie in der
    # UI zum Ausfuellen erscheinen. Schulmanager liefert nur das Kuerzel.
    if kind.get("schulmanager"):
        try:
            verz = kind.setdefault("lehrer_namen", {})
            for a in quellen.hole_aenderungen(kind, heute):
                kz = (a.get("lehrer") or "").strip()
                if kz and not a.get("entfall") \
                        and not any(k.lower() == kz.lower() for k in verz):
                    verz[kz] = ""
                    stats["geaendert"] = True
        except Exception:
            log.debug("Vertretungslehrer-Entdeckung uebersprungen (%s)", kind.get("name"))
    return stats


DATUMSPLAN_WOCHEN_VOR = 8    # so viele Wochen vorausschauen (Quelle liefert oft nur wenige)
DATUMSPLAN_WOCHEN_ZURUECK = 6  # so weit rueckwaerts abrufen, um Historie zu archivieren


def _import_datumsplan(kind: dict, heute: date, details: dict,
                       fach_sicherstellen, stats: dict) -> None:
    """Fuellt kind["tagesplan"] = {iso: [{von,bis,kz,raum,lehrer}]} aus der
    datumsgenauen Quelle - jede Woche bleibt an ihrem Datum (Archiv).

    Zwei Regeln schuetzen die Historie:
      - Tage in der Vergangenheit werden nur ergaenzt, nie ueberschrieben
        (einmal gelaufener Schultag ist eingefroren, auch wenn WebUntis ihn
        spaeter anders/gar nicht mehr liefert).
      - Tage ausserhalb des Abrufzeitraums bleiben ohnehin unberuehrt."""
    heute_iso = heute.isoformat()
    von = heute - timedelta(days=heute.weekday() + 7 * DATUMSPLAN_WOCHEN_ZURUECK)
    bis = heute + timedelta(weeks=DATUMSPLAN_WOCHEN_VOR)
    try:
        bereich = quellen.hole_zeitplan_bereich(kind, von, bis)
    except Exception as exc:
        log.warning("Datumsgenauer Import fuer %s fehlgeschlagen: %s",
                    kind.get("name"), exc)
        return
    tage = bereich.get("tage") or {}
    # Namen/Raeume kuenftiger Faecher, die in der Referenzwoche fehlen, nachziehen
    for kz, det in (bereich.get("details") or {}).items():
        details.setdefault(kz, det)
    tp = kind.setdefault("tagesplan", {})
    neu_tage = 0
    for iso, stunden in tage.items():
        # Vergangenen Tag nicht ueberschreiben, wenn schon archiviert
        if iso < heute_iso and iso in tp:
            continue
        neu = []
        for s in stunden:
            kz = s.get("kz")
            if not kz:
                continue
            match = fach_sicherstellen(kz)
            eintrag = (kind.get("fach_details") or {}).get(match, {})
            raum = (s.get("raum") or eintrag.get("raum") or "").strip()
            lehrer = (eintrag.get("lehrer") or "").strip()
            neu.append({"von": s["von"], "bis": s["bis"], "kz": match,
                        "raum": raum, "lehrer": lehrer})
        neu.sort(key=lambda x: (x["von"], x["bis"]))
        if tp.get(iso) != neu:
            tp[iso] = neu
            stats["geaendert"] = True
            neu_tage += 1
    stats["datumsplan"] = True
    stats["datums_tage"] = neu_tage
    stats["datums_gesamt"] = sum(1 for l in tp.values() if l)
    if kind.get("modus") == "block":
        _bloecke_aus_webuntis(kind, stats)


def _bloecke_aus_webuntis(kind: dict, stats: dict) -> None:
    """Leitet die Blockzeitraeume aus den echten WebUntis-Schultagen ab -
    aber nur im tatsaechlich abgedeckten Zeitraum. Bloecke ausserhalb (schon
    aus dem WebUntis-Fenster gefallene Vergangenheit ODER noch nicht
    veroeffentlichte Zukunft) bleiben unangetastet, damit von Hand gepflegte
    kuenftige Bloecke nicht verloren gehen. Aufeinanderfolgende Schulwochen
    bilden je einen Block; Labels ueberlappender Handbloecke werden uebernommen."""
    tp = kind.get("tagesplan") or {}
    schul = sorted(iso for iso, l in tp.items() if l)
    if not schul:
        return
    ab, bis_auth = schul[0], schul[-1]          # von WebUntis abgedeckter Bereich

    def mo_iso(iso):
        d = date.fromisoformat(iso)
        return (d - timedelta(days=d.weekday())).isoformat()

    def plus(iso, tage):
        return (date.fromisoformat(iso) + timedelta(days=tage)).isoformat()

    # Schulwochen (Montage) zu aufeinanderfolgenden Bloecken gruppieren
    montage = sorted({mo_iso(x) for x in schul})
    gruppen = []
    for mo in montage:
        if gruppen and plus(gruppen[-1][-1], 7) == mo:
            gruppen[-1].append(mo)
        else:
            gruppen.append([mo])
    alt = kind.get("bloecke") or []

    def label_fuer(von, bis):
        for a in alt:
            if a.get("label") and not (a.get("bis", "") < von or a.get("von", "") > bis):
                return a["label"]
        return ""

    abgeleitet = []
    for g in gruppen:
        ende = plus(g[-1], 6)
        tage = [d for d in schul if g[0] <= d <= ende]
        von, bis = tage[0], tage[-1]
        abgeleitet.append({"label": label_fuer(von, bis), "von": von, "bis": bis})
    # Handbloecke ausserhalb des abgedeckten Bereichs behalten (Historie + Zukunft)
    behalten = [b for b in alt
                if b.get("bis", "") < ab or b.get("von", "") > bis_auth]
    neu = sorted(behalten + abgeleitet, key=lambda b: b.get("von", ""))
    if neu != alt:
        kind["bloecke"] = neu
        stats["geaendert"] = True
        stats["bloecke_abgeleitet"] = len(abgeleitet)


DEFAULT_ZEITEN = ["06:30", "07:00", "07:15"]


def _import_zeiten(einstellungen: dict) -> list:
    """Konfigurierte Auto-Import-Zeiten (Liste oder Komma-String),
    Default kurz vor Schulbeginn."""
    roh = einstellungen.get("auto_import_zeiten") \
        or einstellungen.get("auto_import_zeit") \
        or DEFAULT_ZEITEN
    if isinstance(roh, str):
        roh = roh.split(",")
    zeiten = [z.strip() for z in roh if z and z.strip()]
    return zeiten or list(DEFAULT_ZEITEN)


class AutoImportScheduler:
    """Fuehrt den Import mehrmals morgens vor Schulbeginn aus (Default
    06:30, 07:00, 07:15) fuer Kinder mit auto_import=true - so werden auch
    kurzfristig eingetragene Vertretungen noch erfasst. Jeder Zeitpunkt
    laeuft genau einmal pro Tag; vor Aenderungen wird ein Backup angelegt."""

    def __init__(self, load_data_fn, save_data_fn, backup_fn, publish_fn=None):
        self._load = load_data_fn
        self._save = save_data_fn
        self._backup = backup_fn
        self._publish = publish_fn
        self._stop = threading.Event()
        self._gelaufen = set()  # {(date, "HH:MM")}

    def start(self):
        threading.Thread(target=self._loop, daemon=True).start()
        log.info("Auto-Import-Scheduler gestartet")

    def _loop(self):
        while not self._stop.wait(30):
            try:
                self._tick()
            except Exception:
                log.exception("Fehler im Auto-Import")

    def _tick(self):
        jetzt = datetime.now()
        data = self._load()
        zeiten = _import_zeiten(data.get("einstellungen", {}) or {})
        zeit = jetzt.strftime("%H:%M")
        if zeit not in zeiten or (jetzt.date(), zeit) in self._gelaufen:
            return
        self._gelaufen = {(d, z) for d, z in self._gelaufen if d == jetzt.date()}
        self._gelaufen.add((jetzt.date(), zeit))
        kandidaten = [k for k in data.get("kinder", [])
                      if k.get("auto_import") and k.get("schulmanager")]
        if not kandidaten:
            return
        quellen.aktualisiere_quellen(kandidaten)
        backup_gemacht = False
        geaendert = False
        for kind in kandidaten:
            try:
                stats = fuehre_import_aus(data, kind, jetzt.date())
            except Exception as exc:
                log.warning("Auto-Import fuer %s fehlgeschlagen: %s",
                            kind["name"], exc)
                continue
            if stats["geaendert"] and not backup_gemacht:
                self._backup("autoimport")
                backup_gemacht = True
            geaendert = geaendert or stats["geaendert"]
            log.info("Auto-Import %s (%s): %s uebernommen, %d neue Faecher, %d ergaenzt%s",
                     kind["name"], stats["kw"],
                     ", ".join(stats["importiert"]) or "nichts",
                     stats["neue_faecher"], stats["ergaenzt"],
                     " (unveraendert)" if not stats["geaendert"] else "")
        if geaendert:
            self._save(data)
            if self._publish:
                self._publish()
