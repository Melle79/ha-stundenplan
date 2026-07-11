"""Stundenplan Manager - Backups und Snapshots.

- Taegliches Backup zur konfigurierten Uhrzeit (Add-on-Optionen backup_zeit /
  backup_anzahl), Rotation der aeltesten Dateien
- Manuelle Snapshots (z.B. vor einem Schulmanager-Import) mit eigener Rotation
- Restore ersetzt die aktuelle stundenplan.json atomar
"""
import logging
import os
import re
import shutil
import threading
from datetime import datetime
from pathlib import Path

log = logging.getLogger("stundenplan.backup")

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
BACKUP_DIR = DATA_DIR / "backups"
DATEI_MUSTER = re.compile(r"^[a-z]+-\d{8}-\d{6}\.json$")
SNAPSHOT_BEHALTEN = 5


def _quelle() -> Path:
    return DATA_DIR / "stundenplan.json"


def backup_erstellen(prefix: str = "taeglich") -> str | None:
    """Kopiert die Daten nach backups/{prefix}-YYYYMMDD-HHMMSS.json."""
    if not _quelle().exists():
        return None
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{prefix}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    shutil.copy2(_quelle(), BACKUP_DIR / name)
    log.info("Backup erstellt: %s", name)
    _rotieren(prefix, SNAPSHOT_BEHALTEN if prefix != "taeglich"
              else int(os.environ.get("BACKUP_ANZAHL", 7)))
    return name


def _rotieren(prefix: str, behalten: int):
    dateien = sorted(BACKUP_DIR.glob(f"{prefix}-*.json"))
    for alt in dateien[:-behalten] if behalten > 0 else []:
        alt.unlink(missing_ok=True)
        log.debug("Altes Backup entfernt: %s", alt.name)


def liste_backups() -> list:
    if not BACKUP_DIR.exists():
        return []
    dateien = []
    for p in sorted(BACKUP_DIR.glob("*.json"), reverse=True):
        if DATEI_MUSTER.match(p.name):
            dateien.append({"datei": p.name,
                            "groesse": p.stat().st_size,
                            "zeit": datetime.fromtimestamp(p.stat().st_mtime)
                            .strftime("%d.%m.%Y %H:%M")})
    return dateien


def backup_wiederherstellen(datei: str) -> bool:
    """Stellt ein Backup atomar wieder her. Nur validierte Dateinamen."""
    if not DATEI_MUSTER.match(datei):
        raise ValueError("Ungueltiger Backup-Dateiname")
    pfad = BACKUP_DIR / datei
    if not pfad.exists():
        raise FileNotFoundError(datei)
    tmp = _quelle().with_suffix(".restore-tmp")
    shutil.copy2(pfad, tmp)
    tmp.replace(_quelle())
    log.info("Backup wiederhergestellt: %s", datei)
    return True


class BackupScheduler:
    """Erstellt taeglich zur BACKUP_ZEIT ein Backup."""

    def __init__(self):
        self._zuletzt = None

    def start(self):
        threading.Thread(target=self._loop, daemon=True).start()
        log.info("Backup-Scheduler gestartet (taeglich %s, behalte %s)",
                 os.environ.get("BACKUP_ZEIT", "03:30"),
                 os.environ.get("BACKUP_ANZAHL", 7))

    def _loop(self):
        import time
        while True:
            time.sleep(30)
            try:
                jetzt = datetime.now()
                if jetzt.strftime("%H:%M") != os.environ.get("BACKUP_ZEIT", "03:30"):
                    continue
                if self._zuletzt == jetzt.date():
                    continue
                self._zuletzt = jetzt.date()
                backup_erstellen("taeglich")
            except Exception:
                log.exception("Fehler im Backup-Scheduler")
