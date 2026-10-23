"""Reads league catalogs from Excel and writes rows to SQLite + Liga-128 JSON."""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd

LIGA128_REL_PATH = os.path.join("data", "liga128_leagues.json")


def _normalize_header(h: Any) -> str:
    return str(h).strip().lower().replace(" ", "_")


def parse_leagues_workbook(path: str) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Read first worksheet. Expected columns (flexible names):
      id: league_id, id, liga_id, ...
      name: league_name, name, liga, ...
      country: country_name, country, land, ...
      code: country_code, code, iso, ...

    Each row dict: league_id:int, league_name:str, country_name:str, country_code:str
    Returns (rows, error_message).
    """
    try:
        df = pd.read_excel(path, sheet_name=0, dtype=object)
    except Exception as e:
        return [], str(e)

    if df.empty:
        return [], "Die Datei enthält keine Zeilen."

    col_map_raw = {_normalize_header(c): c for c in df.columns}

    def pick(columns: List[str]) -> Optional[str]:
        for key in columns:
            if key in col_map_raw:
                return col_map_raw[key]
        # fuzzy: any column ending with suffix
        for norm, original in col_map_raw.items():
            for key in columns:
                if norm == key or norm.endswith("_" + key) or norm.endswith(key):
                    return original
        return None

    id_col = pick(["league_id", "id", "liga_id", "lid"])
    name_col = pick(["league_name", "name", "liga", "league"])
    country_col = pick(["country_name", "country", "land", "nation"])
    code_col = pick(["country_code", "code", "iso", "cc"])

    if not id_col:
        return [], (
            "Keine Liga-ID-Spalte gefunden. Erwartet z. B. „league_id“ oder „id“ "
            "(erste Zeile = Spaltenüberschriften)."
        )
    if not name_col:
        return [], (
            'Keine Liganamen-Spalte gefunden (z. B. „league_name“ oder „name“).'
        )

    rows_out: List[Dict[str, Any]] = []

    def to_int(cell: Any) -> Optional[int]:
        if pd.isna(cell):
            return None
        try:
            return int(float(str(cell).strip()))
        except (TypeError, ValueError):
            return None

    def to_str(cell: Any) -> str:
        if pd.isna(cell):
            return ""
        return str(cell).strip()

    seen_ids: Set[int] = set()
    for _, row in df.iterrows():
        lid = to_int(row.get(id_col))
        if lid is None:
            continue
        if lid in seen_ids:
            continue
        seen_ids.add(lid)
        cn = to_str(row.get(country_col)) if country_col else ""
        cc = to_str(row.get(code_col)) if code_col else ""
        rows_out.append(
            {
                "league_id": lid,
                "league_name": to_str(row.get(name_col)) or f"League {lid}",
                "country_name": cn or "Unknown",
                "country_code": cc,
            }
        )

    rows_out.sort(key=lambda r: (r["country_name"], r["league_name"], r["league_id"]))
    if not rows_out:
        return [], "Keine gültigen Liga-IDs in der Datei."

    return rows_out, None


def upsert_league_row(conn: sqlite3.Connection, league_id: int, league_name: str,
                      country_name: str, country_code: str) -> None:
    now = datetime.now().isoformat()
    row = conn.execute(
        "SELECT league_id FROM leagues WHERE league_id = ?", (league_id,)
    ).fetchone()
    if row:
        conn.execute(
            """
            UPDATE leagues
            SET league_name = ?, country_name = ?, country_code = ?, updated_at = ?
            WHERE league_id = ?
            """,
            (
                league_name,
                country_name,
                country_code or "",
                now,
                league_id,
            ),
        )
    else:
        conn.execute(
            """
            INSERT INTO leagues
            (league_id, league_name, country_name, country_code, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (league_id, league_name, country_name, country_code or "", now),
        )


def load_liga128_ids(path: Optional[str] = None) -> List[int]:
    p = path or LIGA128_REL_PATH
    try:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return sorted({int(x) for x in data if isinstance(x, int)})
    except Exception as e:
        print(f"[WARNING] load_liga128_ids: {e}")
    return sorted({128})


def save_liga128_ids(ids: List[int], path: Optional[str] = None) -> None:
    p = path or LIGA128_REL_PATH
    os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
    uniq = sorted({int(i) for i in ids})
    with open(p, "w", encoding="utf-8") as f:
        json.dump(uniq, f, indent=0)


def set_league_visibility_tab(league_id: int, destination: str) -> None:
    """
    destination: \"league\" = main League tab (remove from liga128 json if present).
                 \"liga128\" = add to liga128 json.
    """
    ids = load_liga128_ids()
    s = set(ids)
    if destination == "liga128":
        s.add(int(league_id))
        save_liga128_ids(sorted(s))
        return
    if destination == "league":
        s.discard(int(league_id))
        save_liga128_ids(sorted(s))
        return
    raise ValueError(f"destination must be league or liga128, got {destination!r}")
