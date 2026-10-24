"""Welche Spiele bei Swisslos Sporttip wettbar sind — über die Liga (data/swisslos_leagues.json).

Die Liste wird beim Ändern der Datei automatisch neu gelesen (kein Neustart nötig).
Es ist eine Liga-Zuordnung: einzelne Spiele, die Swisslos in einer dieser Ligen
nicht anbietet, gelten trotzdem als Swisslos.
"""
from __future__ import annotations

import json
import os
import sqlite3
from typing import Any, Dict, Iterable, Set

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SWISSLOS_PATH = os.path.join(ROOT, "data", "swisslos_leagues.json")

_cache: Dict[str, Any] = {"mtime": None, "ids": frozenset()}


def swisslos_league_ids() -> Set[int]:
    try:
        mtime = os.path.getmtime(SWISSLOS_PATH)
    except OSError:
        return set()
    if _cache["mtime"] != mtime:
        with open(SWISSLOS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            data = data.get("league_ids", [])
        _cache["ids"] = frozenset(int(x) for x in data)
        _cache["mtime"] = mtime
    return set(_cache["ids"])


def is_swisslos(league_id: Any) -> bool:
    try:
        return int(league_id) in swisslos_league_ids()
    except (TypeError, ValueError):
        return False


def league_ids_for_games(conn: sqlite3.Connection, game_ids: Iterable[Any]) -> Dict[int, int]:
    """game_id → league_id aus upcoming_games bzw. games."""
    ids = sorted({int(g) for g in game_ids if g is not None})
    out: Dict[int, int] = {}
    for i in range(0, len(ids), 500):
        chunk = ids[i : i + 500]
        ph = ",".join("?" * len(chunk))
        for table in ("games", "upcoming_games"):
            for gid, lid in conn.execute(
                f"SELECT id, league_id FROM {table} WHERE id IN ({ph}) AND league_id IS NOT NULL", chunk
            ):
                out.setdefault(int(gid), int(lid))
    return out
