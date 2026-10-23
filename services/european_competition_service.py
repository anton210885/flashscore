"""UEFA-Klubwettbewerbe: Champions League, Europa League, Conference League."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

from services.match_status import SQL_FILTER_STILL_PENDING, is_match_still_pending

EURO_COMPETITIONS: Tuple[Dict[str, Any], ...] = (
    {"id": 2, "name": "UEFA Champions League", "short": "UCL"},
    {"id": 3, "name": "UEFA Europa League", "short": "UEL"},
    {"id": 848, "name": "UEFA Europa Conference League", "short": "UECL"},
)

EURO_LEAGUE_IDS: Tuple[int, ...] = tuple(int(c["id"]) for c in EURO_COMPETITIONS)

EURO_PHASES: Tuple[Tuple[str, str], ...] = (
    ("all", "Gesamt"),
    ("qualification", "Qualifikation"),
    ("league_phase", "Liga-Phase"),
    ("playoffs", "Playoffs"),
    ("knockout", "K.-o."),
)

PHASE_INDEX = {
    "all": 0,
    "qualification": 1,
    "league_phase": 2,
    "playoffs": 3,
    "knockout": 4,
}
INDEX_PHASE = {v: k for k, v in PHASE_INDEX.items()}

OVER_LINES: Tuple[float, ...] = (2.5, 3.5, 4.5, 5.5)


def encode_row_id(league_id: int, phase: str) -> int:
    """Eindeutige Zeilen-ID: league_id * 10 + Phasen-Code."""
    return int(league_id) * 10 + int(PHASE_INDEX.get(phase, 0))


def decode_row_id(row_id: int) -> Tuple[int, str]:
    """Synthetic ID → (echte Liga-ID, Phase)."""
    rid = int(row_id)
    if rid in EURO_LEAGUE_IDS:
        return rid, "all"
    source, code = divmod(rid, 10)
    if source in EURO_LEAGUE_IDS and code in INDEX_PHASE:
        return source, INDEX_PHASE[code]
    return rid, "all"


def phase_from_label(name: str) -> str:
    raw = (name or "").replace("⚠", "").strip()
    raw = raw.lstrip("·").strip()
    for key, label in EURO_PHASES:
        if raw.lower() == label.lower():
            return key
    return "all"


def competition_by_id(league_id: int) -> Optional[Dict[str, Any]]:
    for c in EURO_COMPETITIONS:
        if int(c["id"]) == int(league_id):
            return c
    return None


def classify_uefa_phase(round_name: Optional[str]) -> str:
    """Ordnet round_name einer UEFA-Phase zu."""
    if not round_name or not str(round_name).strip():
        return "other"
    r = str(round_name).lower().strip()

    # K.-o. nach Liga-Phase (nicht Play-offs)
    knockout_tokens = (
        "round of 16", "last 16", "achtelfinale", "8th finals", "1/8",
        "quarter", "viertel", "1/4",
        "semi", "halbfinale", "1/2",
        "3rd place", "third place", "platz 3",
    )
    if any(t in r for t in knockout_tokens):
        return "knockout"
    if r == "final" or r.endswith(" final") or " - final" in r:
        if "qualif" in r or "play" in r:
            return "playoffs" if "play" in r else "qualification"
        return "knockout"
    if "final" in r and "qualif" not in r and "play" not in r:
        return "knockout"

    # Play-offs (Quali-Play-offs und Knockout Round Play-offs)
    if "play-off" in r or "playoff" in r or "play offs" in r:
        return "playoffs"

    if any(t in r for t in ("qualif", "preliminary", "vorqualif")):
        return "qualification"

    if any(
        t in r
        for t in (
            "league stage", "league phase", "liga-phase", "ligaphase",
            "group stage", "gruppenphase", "group", "gruppe",
        )
    ):
        return "league_phase"
    if "matchday" in r or "spieltag" in r:
        return "league_phase"

    return "other"


def phase_matches(round_name: Optional[str], phase: str) -> bool:
    if not phase or phase == "all":
        return True
    return classify_uefa_phase(round_name) == phase


def _row_to_dict(row: Any) -> Dict[str, Any]:
    if row is None:
        return {}
    if isinstance(row, dict):
        return dict(row)
    try:
        return dict(row)
    except Exception:
        pass
    keys = getattr(row, "keys", None)
    if callable(keys):
        return {k: row[k] for k in keys()}
    return {}


def _goals(home: Any, away: Any) -> Optional[float]:
    try:
        if home is None or away is None:
            return None
        return float(home) + float(away)
    except (TypeError, ValueError):
        return None


def compute_over_stats(games: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Over-Quoten, Last 10/20 und Under-Streaks für 2.5/3.5/4.5/5.5."""
    totals: List[float] = []
    for g in games:
        t = g.get("total_goals")
        if t is None:
            t = _goals(g.get("home_ft_result"), g.get("away_ft_result"))
        if t is None:
            continue
        totals.append(float(t))

    n = len(totals)
    out: Dict[str, Any] = {"n": n}

    def pct(count: int, denom: int) -> str:
        if denom <= 0:
            return "0.0%"
        return f"{(count / denom * 100.0):.1f}%"

    for line in OVER_LINES:
        key = str(line).replace(".", "")
        over_n = sum(1 for t in totals if t > line)
        out[f"over{key}"] = pct(over_n, n)
        out[f"over{key}_count"] = over_n

        last10 = totals[:10]
        last20 = totals[:20]
        n10, n20 = len(last10), len(last20)
        out[f"last10_over{key}"] = pct(sum(1 for t in last10 if t > line), n10) if n10 >= 10 else pct(sum(1 for t in last10 if t > line), n10)
        out[f"last20_over{key}"] = pct(sum(1 for t in last20 if t > line), n20) if n20 >= 20 else pct(sum(1 for t in last20 if t > line), n20)

        streak = 0
        if totals and totals[0] <= line:
            for t in totals:
                if t <= line:
                    streak += 1
                else:
                    break
            streak = -streak
        out[f"streak{key}"] = streak

    return out


def fetch_finished_games(
    conn,
    league_id: int,
    year: int,
    phase: str = "all",
) -> List[Dict[str, Any]]:
    cur = conn.execute(
        """
        SELECT id, date, round_name, home_team_name, away_team_name,
               home_ft_result, away_ft_result,
               COALESCE(home_ft_result, 0) + COALESCE(away_ft_result, 0) AS total_goals
        FROM games
        WHERE league_id = ?
          AND season_year = ?
          AND home_ft_result IS NOT NULL
          AND away_ft_result IS NOT NULL
        ORDER BY date DESC
        """,
        (int(league_id), int(year)),
    )
    cols = [c[0] for c in (cur.description or [])]
    games = []
    for row in cur.fetchall():
        if hasattr(row, "keys"):
            d = _row_to_dict(row)
        else:
            d = dict(zip(cols, row))
        if phase_matches(d.get("round_name"), phase):
            games.append(d)
    return games


def _infer_round_name(conn, league_id: int, game: Dict[str, Any]) -> Optional[str]:
    """Füllt fehlendes round_name aus games (gleiche ID oder aktuelle Saison-Runde)."""
    existing = str(game.get("round_name") or "").strip()
    if existing:
        return existing

    gid = game.get("id")
    if gid:
        try:
            row = conn.execute(
                "SELECT round_name FROM games WHERE id = ? AND round_name IS NOT NULL LIMIT 1",
                (gid,),
            ).fetchone()
            if row:
                name = row[0] if not hasattr(row, "keys") else row["round_name"]
                if name and str(name).strip():
                    return str(name).strip()
        except Exception:
            pass

    year = game.get("season_year")
    if not year:
        try:
            row = conn.execute(
                "SELECT MAX(season_year) FROM games WHERE league_id = ?",
                (int(league_id),),
            ).fetchone()
            year = row[0] if row else None
        except Exception:
            year = None

    sql = """
        SELECT round_name FROM games
        WHERE league_id = ?
          AND round_name IS NOT NULL
    """
    params: List[Any] = [int(league_id)]
    if year:
        sql += " AND season_year = ?"
        params.append(int(year))
    sql += " ORDER BY date DESC LIMIT 1"
    try:
        row = conn.execute(sql, tuple(params)).fetchone()
    except Exception:
        return None
    if not row:
        return None
    name = row[0] if not hasattr(row, "keys") else row["round_name"]
    if name and str(name).strip():
        return str(name).strip()
    return None


def fetch_today_games(
    conn,
    league_id: int,
    phase: str = "all",
    today_str: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Heutige offene Spiele (upcoming_games ∪ games), ohne bereits beendete."""
    if not today_str:
        today_str = datetime.now().strftime("%Y-%m-%d")
    pending = SQL_FILTER_STILL_PENDING
    cur = conn.execute(
        f"""
        SELECT id, date, round_name, home_team_name, away_team_name,
               status_name, home_ft_result, away_ft_result, season_year, status, updated_at, source
        FROM (
            SELECT id, date, round_name, home_team_name, away_team_name,
                   status_name, home_ft_result, away_ft_result, season_year, status, updated_at,
                   'upcoming' AS source
            FROM upcoming_games
            WHERE league_id = ?
              AND substr(date, 1, 10) = ?
              {pending}
            UNION
            SELECT id, date, round_name, home_team_name, away_team_name,
                   status_name, home_ft_result, away_ft_result, season_year, status, updated_at,
                   'games' AS source
            FROM games
            WHERE league_id = ?
              AND substr(date, 1, 10) = ?
              {pending}
        ) AS merged_today
        ORDER BY date ASC
        """,
        (int(league_id), today_str, int(league_id), today_str),
    )
    cols = [c[0] for c in (cur.description or [])]
    seen = set()
    games = []
    for row in cur.fetchall():
        if hasattr(row, "keys"):
            d = _row_to_dict(row)
        else:
            d = dict(zip(cols, row))
        gid = d.get("id")
        if gid in seen:
            continue
        seen.add(gid)
        if not is_match_still_pending(
            d.get("status"),
            d.get("status_name"),
            d.get("home_ft_result"),
            d.get("away_ft_result"),
            d.get("updated_at"),
        ):
            continue
        if not str(d.get("round_name") or "").strip():
            inferred = _infer_round_name(conn, int(league_id), d)
            if inferred:
                d["round_name"] = inferred
        if phase_matches(d.get("round_name"), phase):
            games.append(d)
    return games


def today_counts_by_phase(conn, league_id: int, today_str: Optional[str] = None) -> Dict[str, int]:
    """Anzahl heutiger Spiele je Phase inkl. 'all'."""
    games = fetch_today_games(conn, league_id, "all", today_str)
    counts = {key: 0 for key, _label in EURO_PHASES}
    for g in games:
        ph = classify_uefa_phase(g.get("round_name"))
        if ph in counts:
            counts[ph] += 1
        counts["all"] += 1
    return counts


def stats_for_league_year(conn, league_id: int, year: int, phase: str = "all") -> Dict[str, Any]:
    games = fetch_finished_games(conn, league_id, year, phase)
    stats = compute_over_stats(games)
    stats["total"] = len(games)
    stats["total_finished"] = len(games)
    return stats


def ensure_european_league_rows(db_manager) -> None:
    conn = db_manager.get_connection()
    now = datetime.utcnow().isoformat()
    for comp in EURO_COMPETITIONS:
        exists = conn.execute(
            "SELECT league_id FROM leagues WHERE league_id = ?",
            (comp["id"],),
        ).fetchone()
        if exists:
            conn.execute(
                """
                UPDATE leagues
                SET league_name = ?, country_name = 'World', country_code = 'INT', updated_at = ?
                WHERE league_id = ?
                """,
                (comp["name"], now, comp["id"]),
            )
        else:
            try:
                conn.execute(
                    """
                    INSERT INTO leagues (league_id, league_name, country_name, country_code, updated_at)
                    VALUES (?, ?, 'World', 'INT', ?)
                    """,
                    (comp["id"], comp["name"], now),
                )
            except Exception:
                pass
    try:
        conn.commit()
    except Exception:
        pass
