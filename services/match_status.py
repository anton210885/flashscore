"""Hilfen: ist ein Spiel noch offen oder bereits beendet?"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional

FINISHED_STATUS_CODES = (7, 8, 9, 10)
# SStats: 1=Not Started, 2=1st Half, 3=HT, 4=2nd Half, 5=ET, …
LIVE_STATUS_CODES = (2, 3, 4, 5, 6)

# Live-Zeilen ohne frisches Update gelten als veraltet (fertig / nicht mehr „heute offen“)
STALE_LIVE_HOURS = 2

# SQL-Suffix für Tabellen mit status / status_name / home_ft_result / away_ft_result / updated_at
SQL_FILTER_STILL_PENDING = f"""
    AND (home_ft_result IS NULL OR away_ft_result IS NULL)
    AND (status IS NULL OR status NOT IN (7, 8, 9, 10))
    AND (
        status_name IS NULL OR trim(status_name) = ''
        OR (
            lower(status_name) NOT LIKE '%finished%'
            AND lower(status_name) NOT LIKE '%after penalties%'
            AND lower(status_name) NOT LIKE '%after extra time%'
        )
    )
    AND NOT (
        (
            status IN (2, 3, 4, 5, 6)
            OR lower(COALESCE(status_name, '')) LIKE '%half%'
            OR lower(COALESCE(status_name, '')) LIKE 'live%'
        )
        AND (
            updated_at IS NULL
            OR datetime(replace(substr(updated_at, 1, 19), 'T', ' '))
               < datetime('now', '-{STALE_LIVE_HOURS} hours')
        )
    )
"""


def _is_live_status(status: Any = None, status_name: Any = None) -> bool:
    try:
        if status is not None and int(status) in LIVE_STATUS_CODES:
            return True
    except (TypeError, ValueError):
        pass
    sn = str(status_name or "").lower()
    return ("half" in sn) or sn.startswith("live")


def _is_stale_updated_at(updated_at: Any, hours: int = STALE_LIVE_HOURS) -> bool:
    if updated_at is None or updated_at == "":
        return True
    raw = str(updated_at).strip().replace("T", " ")[:19]
    try:
        ts = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        try:
            ts = datetime.fromisoformat(str(updated_at).replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            return True
    return ts < datetime.now() - timedelta(hours=hours)


def is_match_still_pending(
    status: Any = None,
    status_name: Any = None,
    home_ft_result: Any = None,
    away_ft_result: Any = None,
    updated_at: Any = None,
) -> bool:
    """True = noch nicht abgeschlossen (soll in „Heute offen“ gezählt werden)."""
    if home_ft_result is not None and away_ft_result is not None:
        return False
    try:
        if status is not None and int(status) in FINISHED_STATUS_CODES:
            return False
    except (TypeError, ValueError):
        pass
    sn = str(status_name or "").lower()
    if any(tok in sn for tok in ("finished", "after penalties", "after extra time")):
        return False
    # Veraltete Live-Snapshots (z.B. ewig „1st Half“) nicht als offen zählen
    if _is_live_status(status, status_name) and _is_stale_updated_at(updated_at):
        return False
    return True
