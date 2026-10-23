"""Welche Ligen aktiv verfolgt werden: Ligen-Tab und Endergebnis-Job der Pipeline.

Quelle: data/tracked_leagues.json + data/liga128_leagues.json + data/league_watchlist.json.
Fehlt tracked_leagues.json, gilt keine Begrenzung (None) — wie vor der Liste.
Daten anderer Ligen bleiben in der Datenbank, sie werden nur nicht angezeigt/aktualisiert.
"""
from __future__ import annotations

import json
import os
from typing import Optional, Set

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TRACKED_PATH = os.path.join(ROOT, "data", "tracked_leagues.json")
EXTRA_PATHS = (
    os.path.join(ROOT, "data", "liga128_leagues.json"),
    os.path.join(ROOT, "data", "league_watchlist.json"),
)


def _read_ids(path: str) -> Optional[Set[int]]:
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        data = data.get("league_ids", [])
    return {int(x) for x in data}


def active_league_ids() -> Optional[Set[int]]:
    """Aktive Liga-IDs, oder None wenn keine Liste gepflegt ist (= alle Ligen)."""
    ids = _read_ids(TRACKED_PATH)
    if ids is None:
        return None
    for path in EXTRA_PATHS:
        ids |= _read_ids(path) or set()
    return ids
