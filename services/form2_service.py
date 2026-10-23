"""Form2 — saisonale Team-Durchschnitte (gesamt + Home/Away-Split).

Naming B (lesbar):
  hometeam_home_xg  = Heimteam Ø-xG in Heimspielen (vor Kickoff)
  hometeam_away_xg  = Heimteam Ø-xG in Auswärtsspielen
  awayteam_home_xg  = Gast Ø-xG in Heimspielen
  awayteam_away_xg  = Gast Ø-xG in Auswärtsspielen
  (+ _xga, _gf, _ga, _n)
  hometeam_pred_xg / awayteam_pred_xg = Venue-Pred
    (Heim-Ø-xG + Gast-Auswärts-Ø-xGA) / 2  bzw. umgekehrt
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from services.european_competition_service import EURO_LEAGUE_IDS
from services.world_cup_service import WORLD_CUP_LEAGUE_ID

FORM2_TABLE = "game_form2"

EXCLUDED_LEAGUE_IDS: Set[int] = set(int(x) for x in EURO_LEAGUE_IDS) | {int(WORLD_CUP_LEAGUE_ID)}

# Gesamt (wie bisher) + Venue-Split (Namen B)
_VENUE_COLS = (
    "hometeam_home_n", "hometeam_home_xg", "hometeam_home_xga", "hometeam_home_gf", "hometeam_home_ga",
    "hometeam_away_n", "hometeam_away_xg", "hometeam_away_xga", "hometeam_away_gf", "hometeam_away_ga",
    "awayteam_home_n", "awayteam_home_xg", "awayteam_home_xga", "awayteam_home_gf", "awayteam_home_ga",
    "awayteam_away_n", "awayteam_away_xg", "awayteam_away_xga", "awayteam_away_gf", "awayteam_away_ga",
    "hometeam_pred_xg", "awayteam_pred_xg",
)

CREATE_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {FORM2_TABLE} (
    game_id INTEGER PRIMARY KEY,
    home_n INTEGER NOT NULL DEFAULT 0,
    home_avg_xg REAL,
    home_avg_xga REAL,
    home_avg_gf REAL,
    home_avg_ga REAL,
    away_n INTEGER NOT NULL DEFAULT 0,
    away_avg_xg REAL,
    away_avg_xga REAL,
    away_avg_gf REAL,
    away_avg_ga REAL,
    home_xg REAL,
    away_xg REAL,
    hometeam_home_n INTEGER NOT NULL DEFAULT 0,
    hometeam_home_xg REAL,
    hometeam_home_xga REAL,
    hometeam_home_gf REAL,
    hometeam_home_ga REAL,
    hometeam_away_n INTEGER NOT NULL DEFAULT 0,
    hometeam_away_xg REAL,
    hometeam_away_xga REAL,
    hometeam_away_gf REAL,
    hometeam_away_ga REAL,
    awayteam_home_n INTEGER NOT NULL DEFAULT 0,
    awayteam_home_xg REAL,
    awayteam_home_xga REAL,
    awayteam_home_gf REAL,
    awayteam_home_ga REAL,
    awayteam_away_n INTEGER NOT NULL DEFAULT 0,
    awayteam_away_xg REAL,
    awayteam_away_xga REAL,
    awayteam_away_gf REAL,
    awayteam_away_ga REAL,
    hometeam_pred_xg REAL,
    awayteam_pred_xg REAL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE
);
"""

CREATE_INDEX_SQL = f"""
CREATE INDEX IF NOT EXISTS idx_form2_game_id ON {FORM2_TABLE}(game_id);
"""


def ensure_form2_schema(conn: sqlite3.Connection) -> None:
    conn.execute(CREATE_TABLE_SQL)
    conn.execute(CREATE_INDEX_SQL)
    existing = {
        str(r[1])
        for r in conn.execute(f"PRAGMA table_info({FORM2_TABLE})").fetchall()
    }
    for col in _VENUE_COLS:
        if col in existing:
            continue
        typ = "INTEGER NOT NULL DEFAULT 0" if col.endswith("_n") else "REAL"
        try:
            conn.execute(f"ALTER TABLE {FORM2_TABLE} ADD COLUMN {col} {typ}")
        except sqlite3.OperationalError:
            pass
    conn.commit()


def is_form2_league(league_id: Any) -> bool:
    try:
        lid = int(league_id)
    except (TypeError, ValueError):
        return False
    return lid not in EXCLUDED_LEAGUE_IDS


def _avg(sum_v: float, n: int) -> Optional[float]:
    if n <= 0:
        return None
    return float(sum_v) / float(n)


def _predict_xg(own_avg_xg: Optional[float], opp_avg_xga: Optional[float]) -> Optional[float]:
    if own_avg_xg is None or opp_avg_xga is None:
        return None
    return (float(own_avg_xg) + float(opp_avg_xga)) / 2.0


def _empty_bucket() -> Dict[str, Any]:
    return {"n": 0, "xg": 0.0, "xga": 0.0, "gf": 0.0, "ga": 0.0}


def _empty_team() -> Dict[str, Dict[str, Any]]:
    return {"all": _empty_bucket(), "home": _empty_bucket(), "away": _empty_bucket()}


def _snap(bucket: Dict[str, Any]) -> Dict[str, Any]:
    n = int(bucket.get("n") or 0)
    return {
        "n": n,
        "xg": _avg(bucket["xg"], n),
        "xga": _avg(bucket["xga"], n),
        "gf": _avg(bucket["gf"], n),
        "ga": _avg(bucket["ga"], n),
    }


def _add_side(bucket: Dict[str, Any], *, xg: float, xga: float, gf: float, ga: float) -> None:
    bucket["xg"] += xg
    bucket["xga"] += xga
    bucket["gf"] += gf
    bucket["ga"] += ga
    bucket["n"] += 1


def _apply_match(
    home_team: Dict[str, Dict[str, Any]],
    away_team: Dict[str, Dict[str, Any]],
    *,
    hxg: float,
    axg: float,
    hg: float,
    ag: float,
) -> None:
    # Gesamt
    _add_side(home_team["all"], xg=hxg, xga=axg, gf=hg, ga=ag)
    _add_side(away_team["all"], xg=axg, xga=hxg, gf=ag, ga=hg)
    # Venue-Split: Heimteam nur „home“, Gast nur „away“
    _add_side(home_team["home"], xg=hxg, xga=axg, gf=hg, ga=ag)
    _add_side(away_team["away"], xg=axg, xga=hxg, gf=ag, ga=hg)


def _upsert_row(
    conn: sqlite3.Connection,
    game_id: int,
    home_team: Dict[str, Dict[str, Any]],
    away_team: Dict[str, Dict[str, Any]],
) -> None:
    h_all = _snap(home_team["all"])
    a_all = _snap(away_team["all"])
    hh = _snap(home_team["home"])
    ha = _snap(home_team["away"])
    ah = _snap(away_team["home"])
    aa = _snap(away_team["away"])

    # Gesamt-Pred (wie bisher)
    home_xg = _predict_xg(h_all["xg"], a_all["xga"])
    away_xg = _predict_xg(a_all["xg"], h_all["xga"])
    # Venue-Pred: Heimteam zu Hause vs Gast auswärts
    hometeam_pred_xg = _predict_xg(hh["xg"], aa["xga"])
    awayteam_pred_xg = _predict_xg(aa["xg"], hh["xga"])

    now = datetime.now().isoformat()
    conn.execute(
        f"""
        INSERT INTO {FORM2_TABLE} (
            game_id,
            home_n, home_avg_xg, home_avg_xga, home_avg_gf, home_avg_ga,
            away_n, away_avg_xg, away_avg_xga, away_avg_gf, away_avg_ga,
            home_xg, away_xg,
            hometeam_home_n, hometeam_home_xg, hometeam_home_xga, hometeam_home_gf, hometeam_home_ga,
            hometeam_away_n, hometeam_away_xg, hometeam_away_xga, hometeam_away_gf, hometeam_away_ga,
            awayteam_home_n, awayteam_home_xg, awayteam_home_xga, awayteam_home_gf, awayteam_home_ga,
            awayteam_away_n, awayteam_away_xg, awayteam_away_xga, awayteam_away_gf, awayteam_away_ga,
            hometeam_pred_xg, awayteam_pred_xg,
            updated_at
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?
        )
        ON CONFLICT(game_id) DO UPDATE SET
            home_n=excluded.home_n,
            home_avg_xg=excluded.home_avg_xg,
            home_avg_xga=excluded.home_avg_xga,
            home_avg_gf=excluded.home_avg_gf,
            home_avg_ga=excluded.home_avg_ga,
            away_n=excluded.away_n,
            away_avg_xg=excluded.away_avg_xg,
            away_avg_xga=excluded.away_avg_xga,
            away_avg_gf=excluded.away_avg_gf,
            away_avg_ga=excluded.away_avg_ga,
            home_xg=excluded.home_xg,
            away_xg=excluded.away_xg,
            hometeam_home_n=excluded.hometeam_home_n,
            hometeam_home_xg=excluded.hometeam_home_xg,
            hometeam_home_xga=excluded.hometeam_home_xga,
            hometeam_home_gf=excluded.hometeam_home_gf,
            hometeam_home_ga=excluded.hometeam_home_ga,
            hometeam_away_n=excluded.hometeam_away_n,
            hometeam_away_xg=excluded.hometeam_away_xg,
            hometeam_away_xga=excluded.hometeam_away_xga,
            hometeam_away_gf=excluded.hometeam_away_gf,
            hometeam_away_ga=excluded.hometeam_away_ga,
            awayteam_home_n=excluded.awayteam_home_n,
            awayteam_home_xg=excluded.awayteam_home_xg,
            awayteam_home_xga=excluded.awayteam_home_xga,
            awayteam_home_gf=excluded.awayteam_home_gf,
            awayteam_home_ga=excluded.awayteam_home_ga,
            awayteam_away_n=excluded.awayteam_away_n,
            awayteam_away_xg=excluded.awayteam_away_xg,
            awayteam_away_xga=excluded.awayteam_away_xga,
            awayteam_away_gf=excluded.awayteam_away_gf,
            awayteam_away_ga=excluded.awayteam_away_ga,
            hometeam_pred_xg=excluded.hometeam_pred_xg,
            awayteam_pred_xg=excluded.awayteam_pred_xg,
            updated_at=excluded.updated_at
        """,
        (
            int(game_id),
            h_all["n"], h_all["xg"], h_all["xga"], h_all["gf"], h_all["ga"],
            a_all["n"], a_all["xg"], a_all["xga"], a_all["gf"], a_all["ga"],
            home_xg, away_xg,
            hh["n"], hh["xg"], hh["xga"], hh["gf"], hh["ga"],
            ha["n"], ha["xg"], ha["xga"], ha["gf"], ha["ga"],
            ah["n"], ah["xg"], ah["xga"], ah["gf"], ah["ga"],
            aa["n"], aa["xg"], aa["xga"], aa["gf"], aa["ga"],
            hometeam_pred_xg, awayteam_pred_xg,
            now,
        ),
    )


def recompute_league_season(
    conn: sqlite3.Connection,
    league_id: int,
    season_year: int,
) -> Dict[str, int]:
    ensure_form2_schema(conn)
    lid = int(league_id)
    yr = int(season_year)
    if not is_form2_league(lid):
        return {"skipped": 1, "written": 0, "updated_teams": 0}

    rows = conn.execute(
        """
        SELECT id, date, home_team_id, away_team_id,
               home_ft_result, away_ft_result,
               calculated_xg_home, calculated_xg_away
        FROM games
        WHERE league_id = ? AND season_year = ?
          AND home_team_id IS NOT NULL AND away_team_id IS NOT NULL
        ORDER BY date ASC, id ASC
        """,
        (lid, yr),
    ).fetchall()

    ids = [int(r[0]) for r in rows]
    for i in range(0, len(ids), 500):
        chunk = ids[i : i + 500]
        ph = ",".join("?" * len(chunk))
        conn.execute(f"DELETE FROM {FORM2_TABLE} WHERE game_id IN ({ph})", chunk)

    teams: Dict[int, Dict[str, Dict[str, Any]]] = {}
    written = 0
    updated_teams = 0

    for r in rows:
        gid = int(r[0])
        hid = int(r[2])
        aid = int(r[3])
        if hid not in teams:
            teams[hid] = _empty_team()
        if aid not in teams:
            teams[aid] = _empty_team()

        _upsert_row(conn, gid, teams[hid], teams[aid])
        written += 1

        hg, ag, hxg, axg = r[4], r[5], r[6], r[7]
        if hg is None or ag is None or hxg is None or axg is None:
            continue
        try:
            hxg_f, axg_f = float(hxg), float(axg)
            hg_f, ag_f = float(hg), float(ag)
        except (TypeError, ValueError):
            continue
        _apply_match(teams[hid], teams[aid], hxg=hxg_f, axg=axg_f, hg=hg_f, ag=ag_f)
        updated_teams += 1

    conn.commit()
    return {"skipped": 0, "written": written, "updated_teams": updated_teams}


def list_league_seasons(
    conn: sqlite3.Connection,
    *,
    league_id: Optional[int] = None,
    season_year: Optional[int] = None,
) -> List[Tuple[int, int]]:
    clauses = ["league_id IS NOT NULL", "season_year IS NOT NULL"]
    params: List[Any] = []
    if league_id:
        clauses.append("league_id = ?")
        params.append(int(league_id))
    if season_year:
        clauses.append("season_year = ?")
        params.append(int(season_year))
    if EXCLUDED_LEAGUE_IDS:
        ph = ",".join("?" * len(EXCLUDED_LEAGUE_IDS))
        clauses.append(f"league_id NOT IN ({ph})")
        params.extend(sorted(EXCLUDED_LEAGUE_IDS))
    where = " AND ".join(clauses)
    rows = conn.execute(
        f"""
        SELECT DISTINCT league_id, season_year
        FROM games
        WHERE {where}
        ORDER BY league_id, season_year
        """,
        tuple(params),
    ).fetchall()
    return [(int(a), int(b)) for a, b in rows]


def backfill_all(
    conn: sqlite3.Connection,
    *,
    league_id: Optional[int] = None,
    season_year: Optional[int] = None,
    progress_every: int = 25,
    log=print,
) -> Dict[str, int]:
    ensure_form2_schema(conn)
    pairs = list_league_seasons(conn, league_id=league_id, season_year=season_year)
    totals = {"pairs": len(pairs), "written": 0, "updated_teams": 0, "skipped": 0}
    for i, (lid, yr) in enumerate(pairs, start=1):
        stats = recompute_league_season(conn, lid, yr)
        totals["written"] += int(stats.get("written") or 0)
        totals["updated_teams"] += int(stats.get("updated_teams") or 0)
        totals["skipped"] += int(stats.get("skipped") or 0)
        if progress_every and (i % progress_every == 0 or i == len(pairs)):
            log(f"form2: {i}/{len(pairs)} league={lid} season={yr} +{stats.get('written', 0)} rows")
    return totals


def refresh_for_game(conn: sqlite3.Connection, game_id: int) -> Dict[str, int]:
    ensure_form2_schema(conn)
    row = conn.execute(
        "SELECT league_id, season_year FROM games WHERE id = ?",
        (int(game_id),),
    ).fetchone()
    if not row or row[0] is None or row[1] is None:
        return {"skipped": 1, "written": 0, "updated_teams": 0}
    stats = recompute_league_season(conn, int(row[0]), int(row[1]))
    up = upsert_upcoming_for_league_season(conn, int(row[0]), int(row[1]))
    stats["upcoming_written"] = int(up.get("written") or 0)
    return stats


def _build_team_state_for_season(
    conn: sqlite3.Connection,
    league_id: int,
    season_year: int,
) -> Dict[int, Dict[str, Dict[str, Any]]]:
    """Team-Buckets aus fertigen Spielen (nach Datum), Stand „jetzt“."""
    teams: Dict[int, Dict[str, Dict[str, Any]]] = {}
    rows = conn.execute(
        """
        SELECT home_team_id, away_team_id,
               home_ft_result, away_ft_result,
               calculated_xg_home, calculated_xg_away
        FROM games
        WHERE league_id = ? AND season_year = ?
          AND home_team_id IS NOT NULL AND away_team_id IS NOT NULL
          AND home_ft_result IS NOT NULL AND away_ft_result IS NOT NULL
          AND calculated_xg_home IS NOT NULL AND calculated_xg_away IS NOT NULL
        ORDER BY date ASC, id ASC
        """,
        (int(league_id), int(season_year)),
    ).fetchall()
    for r in rows:
        hid, aid = int(r[0]), int(r[1])
        if hid not in teams:
            teams[hid] = _empty_team()
        if aid not in teams:
            teams[aid] = _empty_team()
        try:
            hxg, axg = float(r[4]), float(r[5])
            hg, ag = float(r[2]), float(r[3])
        except (TypeError, ValueError):
            continue
        _apply_match(teams[hid], teams[aid], hxg=hxg, axg=axg, hg=hg, ag=ag)
    return teams


def upsert_upcoming_for_league_season(
    conn: sqlite3.Connection,
    league_id: int,
    season_year: int,
) -> Dict[str, int]:
    """Form2-Snapshot für bevorstehende Spiele dieser Liga/Saison (Stand vor Kickoff)."""
    ensure_form2_schema(conn)
    lid, yr = int(league_id), int(season_year)
    if not is_form2_league(lid):
        return {"skipped": 1, "written": 0}

    teams = _build_team_state_for_season(conn, lid, yr)
    upcoming = conn.execute(
        """
        SELECT id, home_team_id, away_team_id
        FROM upcoming_games
        WHERE league_id = ? AND season_year = ?
          AND home_team_id IS NOT NULL AND away_team_id IS NOT NULL
          AND (home_ft_result IS NULL OR away_ft_result IS NULL)
          AND IFNULL(status, 0) NOT IN (7, 8, 9, 10, 15)
        """,
        (lid, yr),
    ).fetchall()

    written = 0
    for r in upcoming:
        gid = int(r[0])
        hid, aid = int(r[1]), int(r[2])
        if hid not in teams:
            teams[hid] = _empty_team()
        if aid not in teams:
            teams[aid] = _empty_team()
        _upsert_row(conn, gid, teams[hid], teams[aid])
        written += 1
    conn.commit()
    return {"skipped": 0, "written": written}


def ensure_form2_for_upcoming_rows(
    conn: sqlite3.Connection,
    rows: List[Dict[str, Any]],
) -> Dict[str, int]:
    """Für Upcoming-Zeilen fehlende Form2-Snapshots nachziehen (pro Liga/Saison)."""
    ensure_form2_schema(conn)
    pairs: Set[Tuple[int, int]] = set()
    for r in rows:
        lid, yr = r.get("league_id"), r.get("season_year")
        hid, aid = r.get("home_team_id"), r.get("away_team_id")
        if lid is None or yr is None or hid is None or aid is None:
            continue
        try:
            lid_i, yr_i = int(lid), int(yr)
        except (TypeError, ValueError):
            continue
        if not is_form2_league(lid_i):
            continue
        pairs.add((lid_i, yr_i))

    written = 0
    for lid, yr in sorted(pairs):
        written += int(upsert_upcoming_for_league_season(conn, lid, yr).get("written") or 0)
    return {"pairs": len(pairs), "written": written}
