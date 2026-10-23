"""World Cup (league_id=1) – Jahre, Phasen, Statistik, DB-Abfragen."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

WORLD_CUP_LEAGUE_ID = 1
WORLD_CUP_NAME = "World Cup"
WORLD_CUP_COUNTRY = "World"
WORLD_CUP_COUNTRY_CODE = "INT"

# FIFA-Weltmeisterschaften (inkl. WM 2026 zum Aktualisieren)
WORLD_CUP_YEARS: Tuple[int, ...] = (2002, 2006, 2010, 2014, 2018, 2022, 2026)
WORLD_CUP_UPCOMING_YEAR = 2026

# Grafik-Vergleich
COMPARE_WM_YEARS: Tuple[int, ...] = (2018, 2022, 2026)

CHART_SEGMENTS: Tuple[Tuple[str, str], ...] = (
    ("gesamt", "Gesamt"),
    ("md1", "Spieltag 1"),
    ("md2", "Spieltag 2"),
    ("md3", "Spieltag 3"),
    ("ko", "K.-o.-Phase"),
)

OVER_THRESHOLDS: Tuple[float, ...] = (0.5, 1.5, 2.5, 3.5, 4.5)


def classify_wc_phase(round_name: Optional[str]) -> str:
    """'group', 'ko', or 'other'."""
    if not round_name or not str(round_name).strip():
        return "other"
    r = str(round_name).lower().strip()

    if r.startswith("group") or "gruppe" in r or "gruppen" in r:
        return "group"
    if "group stage" in r or "gruppenphase" in r:
        return "group"

    if "semi" in r or "halbfinale" in r or "1/2" in r:
        return "ko"
    if any(
        m in r
        for m in (
            "round of 16",
            "last 16",
            "achtelfinale",
            "8th finals",
            "1/8",
            "quarter",
            "viertel",
            "1/4",
            "3rd place",
            "third place",
            "platz 3",
            "play-off",
            "knockout",
        )
    ):
        return "ko"
    if r == "final" or r.endswith(" final") or " - final" in r:
        return "ko"
    if "final" in r and "semi" not in r:
        return "ko"

    return "other"


def extract_group_matchday(round_name: Optional[str]) -> Optional[int]:
    """
    Spieltag 1–3 aus round_name, z. B. „Group A - 1“ oder „Group Stage - 2“.
    """
    if not round_name:
        return None
    s = str(round_name).strip()

    m = re.search(r"[-–]\s*(\d+)\s*$", s)
    if m:
        n = int(m.group(1))
        if 1 <= n <= 3:
            return n

    m = re.search(r"(?:matchday|spieltag|runde|round)\s*[-#:]?\s*(\d+)", s, re.I)
    if m:
        n = int(m.group(1))
        if 1 <= n <= 3:
            return n

    m = re.search(r"\b([123])\s*(?:\.?\s*(?:spieltag|match|runde))?\b", s, re.I)
    if m:
        return int(m.group(1))

    return None


def total_goals(game: Dict[str, Any]) -> Optional[int]:
    h, a = game.get("home_ft_result"), game.get("away_ft_result")
    if h is None or a is None:
        return None
    try:
        return int(h) + int(a)
    except (TypeError, ValueError):
        return None


def compute_over_stats(games: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Over X.5 Treffer für eine Spielmenge."""
    with_score = 0
    overs: Dict[str, Dict[str, Any]] = {
        str(t): {"count": 0, "pct": 0.0} for t in OVER_THRESHOLDS
    }
    for g in games:
        tg = total_goals(g)
        if tg is None:
            continue
        with_score += 1
        for t in OVER_THRESHOLDS:
            if tg > t:
                overs[str(t)]["count"] += 1

    if with_score > 0:
        for t in OVER_THRESHOLDS:
            overs[str(t)]["pct"] = round(100.0 * overs[str(t)]["count"] / with_score, 1)

    return {
        "total": len(games),
        "with_score": with_score,
        "overs": overs,
    }


def split_group_by_matchday(games: List[Dict[str, Any]]) -> Dict[Optional[int], List[Dict[str, Any]]]:
    buckets: Dict[Optional[int], List[Dict[str, Any]]] = {1: [], 2: [], 3: [], None: []}
    for g in games:
        md = extract_group_matchday(g.get("round_name"))
        key = md if md in (1, 2, 3) else None
        buckets[key].append(g)
    for key in buckets:
        buckets[key] = sorted(buckets[key], key=lambda x: (str(x.get("round_name") or ""), x.get("date") or ""))
    return buckets


def _ko_sort_key(round_name: Optional[str]) -> int:
    if not round_name:
        return 99
    r = str(round_name).lower()
    if "round of 16" in r or "achtelfinale" in r or "last 16" in r or "1/8" in r:
        return 10
    if "quarter" in r or "viertel" in r or "1/4" in r:
        return 20
    if "semi" in r or "halb" in r or "1/2" in r:
        return 30
    if "3rd" in r or "third" in r or "platz 3" in r:
        return 40
    if "final" in r:
        return 50
    return 60


def sort_games_for_display(games: List[Dict[str, Any]], phase: str) -> List[Dict[str, Any]]:
    if phase == "group":
        return sorted(games, key=lambda g: (str(g.get("round_name") or ""), g.get("date") or ""))
    if phase == "ko":
        return sorted(
            games,
            key=lambda g: (_ko_sort_key(g.get("round_name")), g.get("date") or ""),
        )
    return sorted(games, key=lambda g: g.get("date") or "")


def fetch_world_cup_games_from_db(db_manager, year: int) -> List[Dict[str, Any]]:
    import sqlite3

    conn = db_manager.get_connection()
    conn.row_factory = sqlite3.Row
    year_int = int(year)

    rows = conn.execute(
        """
        SELECT id, date, home_team_name, away_team_name,
               home_ft_result, away_ft_result, round_name, status_name,
               season_year, league_name, country_name
        FROM games
        WHERE league_id = ?
          AND season_year = ?
        ORDER BY date ASC
        """,
        (WORLD_CUP_LEAGUE_ID, year_int),
    ).fetchall()

    if rows:
        return [dict(row) for row in rows]

    prefix = f"{year_int}-%"
    rows = conn.execute(
        """
        SELECT id, date, home_team_name, away_team_name,
               home_ft_result, away_ft_result, round_name, status_name,
               season_year, league_name, country_name
        FROM games
        WHERE league_id = ?
          AND substr(date, 1, 10) LIKE ?
        ORDER BY date ASC
        """,
        (WORLD_CUP_LEAGUE_ID, prefix),
    ).fetchall()
    return [dict(row) for row in rows]


def split_by_phase(games: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    groups: Dict[str, List[Dict[str, Any]]] = {"group": [], "ko": [], "other": []}
    for g in games:
        phase = classify_wc_phase(g.get("round_name"))
        groups[phase].append(g)
    groups["group"] = sort_games_for_display(groups["group"], "group")
    groups["ko"] = sort_games_for_display(groups["ko"] + groups["other"], "ko")
    return groups


def build_statistics_segments(games: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Statistik-Zeilen: Gesamt, Gruppenphase, Spieltag 1–3, KO.
    """
    phases = split_by_phase(games)
    by_md = split_group_by_matchday(phases["group"])

    segments: List[Tuple[str, List[Dict[str, Any]]]] = [
        ("Gesamt", games),
        ("Gruppenphase (alle)", phases["group"]),
        ("Gruppe · Spieltag 1", by_md[1]),
        ("Gruppe · Spieltag 2", by_md[2]),
        ("Gruppe · Spieltag 3", by_md[3]),
        ("K.-o.-Phase", phases["ko"]),
    ]
    if by_md[None]:
        segments.insert(5, ("Gruppe · ohne Spieltag", by_md[None]))

    out = []
    for label, subset in segments:
        out.append({"label": label, "stats": compute_over_stats(subset)})
    return out


def get_games_for_segment(games: List[Dict[str, Any]], segment_key: str) -> List[Dict[str, Any]]:
    """Spielmenge für Grafik-Bereich (gesamt, md1–3, ko)."""
    phases = split_by_phase(games)
    by_md = split_group_by_matchday(phases["group"])
    mapping = {
        "gesamt": games,
        "gruppe": phases["group"],
        "md1": by_md[1],
        "md2": by_md[2],
        "md3": by_md[3],
        "ko": phases["ko"],
    }
    return mapping.get(segment_key, games)


def compute_goals_distribution(games: List[Dict[str, Any]]) -> Dict[int, int]:
    """Wie viele Spiele mit 0, 1, 2, … Gesamttoren (z. B. zwei 0:0 → {0: 2})."""
    dist: Dict[int, int] = {}
    for g in games:
        tg = total_goals(g)
        if tg is None:
            continue
        dist[tg] = dist.get(tg, 0) + 1
    return dist


def load_wm_years_from_db(db_manager, years: Tuple[int, ...] = COMPARE_WM_YEARS) -> Dict[int, List[Dict[str, Any]]]:
    return {int(y): fetch_world_cup_games_from_db(db_manager, int(y)) for y in years}


def over_percentages_for_segment(games: List[Dict[str, Any]], segment_key: str) -> List[float]:
    subset = get_games_for_segment(games, segment_key)
    stats = compute_over_stats(subset)
    if stats["with_score"] == 0:
        return [0.0] * len(OVER_THRESHOLDS)
    return [stats["overs"][str(t)]["pct"] for t in OVER_THRESHOLDS]


def format_over_cell(stats: Dict[str, Any], threshold: float) -> str:
    o = stats["overs"][str(threshold)]
    if stats["with_score"] == 0:
        return "–"
    return f"{o['count']} ({o['pct']:.1f}%)"


def ensure_world_cup_league_row(db_manager) -> None:
    from datetime import datetime

    conn = db_manager.get_connection()
    now = datetime.now().isoformat()
    row = conn.execute(
        "SELECT league_id FROM leagues WHERE league_id = ?", (WORLD_CUP_LEAGUE_ID,)
    ).fetchone()
    if row:
        conn.execute(
            """
            UPDATE leagues
            SET league_name = ?, country_name = ?, country_code = ?, updated_at = ?
            WHERE league_id = ?
            """,
            (WORLD_CUP_NAME, WORLD_CUP_COUNTRY, WORLD_CUP_COUNTRY_CODE, now, WORLD_CUP_LEAGUE_ID),
        )
    else:
        conn.execute(
            """
            INSERT INTO leagues (league_id, league_name, country_name, country_code, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (WORLD_CUP_LEAGUE_ID, WORLD_CUP_NAME, WORLD_CUP_COUNTRY, WORLD_CUP_COUNTRY_CODE, now),
        )
    conn.commit()
