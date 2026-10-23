"""Spiele-Liste für Web-UI: Status-Filter, Glicko, Quoten (Pinnacle bevorzugt)."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from database import DatabaseManager
from services.match_status import FINISHED_STATUS_CODES

DB_PATH = "data/flashscore.db"
PINNACLE_BOOKMAKER_ID = 4


def _conn() -> sqlite3.Connection:
    c = DatabaseManager(DB_PATH).get_connection()
    c.row_factory = sqlite3.Row
    try:
        c.execute("PRAGMA busy_timeout = 15000")
    except Exception:
        pass
    return c


def classify_status(status: Any, status_name: Any) -> str:
    sn = str(status_name or "").strip().lower()
    try:
        st = int(status) if status is not None else None
    except (TypeError, ValueError):
        st = None

    if st in FINISHED_STATUS_CODES or sn.startswith("finished"):
        return "finished"
    # Name hat Vorrang vor Status-Code (API: oft status=2 + "Not Started")
    if any(
        t in sn
        for t in (
            "not started",
            "scheduled",
            "delayed",
            "postponed",
            "to be announced",
            "tba",
        )
    ):
        return "not_started"
    if st == 1:
        return "not_started"
    if (
        sn.startswith("live")
        or "1st half" in sn
        or "2nd half" in sn
        or "half time" in sn
        or "extra time" in sn
        or "penalt" in sn
        or "in progress" in sn
        or st in (2, 3, 4, 5, 6, 11, 19)
    ):
        return "live"
    if st in (0, 12) or not sn:
        return "not_started"
    return "other"


def _date_key(val: Any) -> str:
    return str(val or "").replace("T", " ")[:10]


def _fetch_upcoming_from_db(date_from: str, date_to: str) -> List[Dict[str, Any]]:
    """Fallback/Ergänzung: bevorstehende Spiele aus upcoming_games."""
    conn = _conn()
    try:
        rows = conn.execute(
            """
            SELECT id, date, status, status_name,
                   home_team_name, away_team_name,
                   home_ft_result, away_ft_result, home_result, away_result,
                   league_id, league_name, country_name, round_name
            FROM upcoming_games
            WHERE substr(replace(COALESCE(date, ''), 'T', ' '), 1, 10) BETWEEN ? AND ?
              AND (home_ft_result IS NULL OR away_ft_result IS NULL)
            ORDER BY date ASC
            LIMIT 800
            """,
            (date_from, date_to),
        ).fetchall()
    except Exception:
        return []
    out = []
    for r in rows:
        home_ft = r["home_ft_result"] if r["home_ft_result"] is not None else r["home_result"]
        away_ft = r["away_ft_result"] if r["away_ft_result"] is not None else r["away_result"]
        score = None
        if home_ft is not None and away_ft is not None:
            score = f"{home_ft}:{away_ft}"
        st = r["status"]
        sn = r["status_name"]
        bucket = classify_status(st, sn)
        out.append(
            {
                "id": int(r["id"]),
                "date": r["date"],
                "status": st,
                "status_name": sn or "Not Started",
                "status_bucket": bucket,
                "home": r["home_team_name"],
                "away": r["away_team_name"],
                "score": score,
                "league_id": r["league_id"],
                "league": r["league_name"],
                "country": r["country_name"],
                "round": r["round_name"],
                "source": "upcoming_db",
            }
        )
    return out


def _team_name(obj: Any, *fallbacks: str) -> str:
    if isinstance(obj, dict):
        return obj.get("name") or obj.get("teamName") or ""
    for f in fallbacks:
        if f:
            return str(f)
    return str(obj or "")


def _parse_markets_list(markets: Any) -> Dict[str, Any]:
    """Parst 1X2 + O/U 2.5 aus einer Markets-Liste (marketId 1 / 5)."""
    out = {
        "odd_home": None,
        "odd_draw": None,
        "odd_away": None,
        "odd_over_25": None,
        "odd_under_25": None,
    }
    if not isinstance(markets, list):
        return out
    for market in markets:
        if not isinstance(market, dict):
            continue
        mid = market.get("marketId")
        mname = str(market.get("marketName") or "")
        odds_list = market.get("odds") or []
        if mid == 1 or "Match Winner" in mname or "1X2" in mname:
            for odd in odds_list:
                n, v = odd.get("name"), odd.get("value")
                if n == "Home":
                    out["odd_home"] = v
                elif n == "Draw":
                    out["odd_draw"] = v
                elif n == "Away":
                    out["odd_away"] = v
        elif mid == 5 or mname.strip() in ("Goals Over/Under", "Over/Under"):
            for odd in odds_list:
                n, v = odd.get("name"), odd.get("value")
                if n == "Over 2.5":
                    out["odd_over_25"] = v
                elif n == "Under 2.5":
                    out["odd_under_25"] = v
    return out


def _parse_pinnacle_odds(odds_payload: Any) -> Dict[str, Any]:
    out = {
        "odd_home": None,
        "odd_draw": None,
        "odd_away": None,
        "odd_over_25": None,
        "odd_under_25": None,
        "bookmaker": None,
        "bookmaker_id": None,
    }
    data = odds_payload.get("data", odds_payload) if isinstance(odds_payload, dict) else odds_payload
    if not isinstance(data, list) or not data:
        return out

    # Format A: [{bookmakerId, bookmakerName, odds: [markets...]}]
    if isinstance(data[0], dict) and ("bookmakerId" in data[0] or "bookmakerName" in data[0] or "odds" in data[0]):
        bookie = None
        for b in data:
            name = str(b.get("bookmakerName") or "")
            bid = b.get("bookmakerId")
            if bid == PINNACLE_BOOKMAKER_ID or "pinnacle" in name.lower():
                bookie = b
                break
        if bookie is None:
            bookie = data[0]
        out["bookmaker"] = bookie.get("bookmakerName")
        out["bookmaker_id"] = bookie.get("bookmakerId")
        out.update(_parse_markets_list(bookie.get("odds") or []))
        return out

    # Format B: direkt Markets [{marketId, odds: [...]}] (wie in /games/list Today)
    parsed = _parse_markets_list(data)
    out.update(parsed)
    out["bookmaker"] = "API"
    return out


def fetch_pinnacle_odds(game_id: int) -> Dict[str, Any]:
    try:
        from config import config as cfg
        from api.sstats_client import SStatsClient

        client = SStatsClient(base_url=cfg.BASE_URL, api_key=getattr(cfg, "API_KEY", None))
        try:
            raw = client.get_game_odds(game_id, bookmaker_id=PINNACLE_BOOKMAKER_ID, opening=False)
        except Exception:
            raw = client.get_game_odds(game_id, bookmaker_id=None, opening=False)
        parsed = _parse_pinnacle_odds(raw)
        if parsed.get("odd_home") is None:
            raw2 = client.get_game_odds(game_id, bookmaker_id=None, opening=False)
            parsed = _parse_pinnacle_odds(raw2)
        return parsed
    except Exception as e:
        return {"error": str(e)}


def _glicko_and_db_odds(conn, ids: List[int]):
    glicko_map: Dict[int, Any] = {}
    odds_map: Dict[int, Any] = {}
    if not ids:
        return glicko_map, odds_map
    for i in range(0, len(ids), 400):
        chunk = ids[i : i + 400]
        ph = ",".join("?" * len(chunk))
        for gr in conn.execute(
            f"""
            SELECT game_id,
                   home_rating, home_rd, home_volatility,
                   away_rating, away_rd, away_volatility,
                   home_xg, away_xg,
                   home_win_probability, away_win_probability, draw_probability,
                   updated
            FROM game_glicko WHERE game_id IN ({ph})
            """,
            chunk,
        ).fetchall():
            glicko_map[int(gr["game_id"])] = gr
        try:
            for od in conn.execute(
                f"""
                SELECT game_id, odd_home, odd_draw, odd_away, odd_over_25, odd_under_25
                FROM game_odds_pivoted WHERE game_id IN ({ph})
                """,
                chunk,
            ).fetchall():
                odds_map[int(od["game_id"])] = od
        except Exception:
            pass
    return glicko_map, odds_map


def _fetch_today_from_api() -> List[Dict[str, Any]]:
    """Heutige Spiele (live / not started / finished heute) von SStats."""
    from config import config as cfg
    from api.sstats_client import SStatsClient

    client = SStatsClient(base_url=cfg.BASE_URL, api_key=getattr(cfg, "API_KEY", None))
    params = {"Today": True}
    try:
        params["TimeZone"] = getattr(cfg, "TIMEZONE", 2)
    except Exception:
        pass
    raw = client.get_games(params) or []
    out = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        gid = item.get("id") or item.get("Id") or item.get("gameId")
        if not gid:
            continue
        home = _team_name(item.get("homeTeam"), item.get("homeTeamName"), item.get("home"))
        away = _team_name(item.get("awayTeam"), item.get("awayTeamName"), item.get("away"))
        season = item.get("season") or {}
        league = season.get("league") if isinstance(season, dict) else {}
        if not isinstance(league, dict):
            league = {}
        country = league.get("country") if isinstance(league.get("country"), dict) else {}
        status = item.get("status")
        status_name = item.get("statusName") or item.get("status_name")
        home_ft = item.get("homeFTResult")
        away_ft = item.get("awayFTResult")
        if home_ft is None:
            home_ft = item.get("homeResult")
        if away_ft is None:
            away_ft = item.get("awayResult")
        score = None
        if home_ft is not None and away_ft is not None:
            score = f"{home_ft}:{away_ft}"

        embedded = _parse_markets_list(item.get("odds"))
        has_embedded = any(embedded.get(k) is not None for k in embedded)

        row = {
            "id": int(gid),
            "date": item.get("date"),
            "status": status,
            "status_name": status_name,
            "status_bucket": classify_status(status, status_name),
            "home": home,
            "away": away,
            "score": score,
            "league_id": league.get("id"),
            "league": league.get("name") or item.get("leagueName"),
            "country": country.get("name") if isinstance(country, dict) else None,
            "round": item.get("roundName"),
            "source": "api_today",
        }
        if has_embedded:
            row.update(embedded)
            row["has_odds"] = True
            row["odds_source"] = "api_today"
            row["bookmaker"] = "API"
        out.append(row)
    return out


def _fetch_finished_from_db(date_from: str, date_to: str) -> List[Dict[str, Any]]:
    conn = _conn()
    rows = conn.execute(
        """
        SELECT id, date, status, status_name,
               home_team_name, away_team_name,
               home_ft_result, away_ft_result,
               league_id, league_name, country_name, round_name
        FROM games
        WHERE substr(date, 1, 10) BETWEEN ? AND ?
          AND home_ft_result IS NOT NULL AND away_ft_result IS NOT NULL
        ORDER BY date DESC
        """,
        (date_from, date_to),
    ).fetchall()
    out = []
    for r in rows:
        out.append(
            {
                "id": int(r["id"]),
                "date": r["date"],
                "status": r["status"],
                "status_name": r["status_name"] or "Finished",
                "status_bucket": "finished",
                "home": r["home_team_name"],
                "away": r["away_team_name"],
                "score": f"{r['home_ft_result']}:{r['away_ft_result']}",
                "league_id": r["league_id"],
                "league": r["league_name"],
                "country": r["country_name"],
                "round": r["round_name"],
                "source": "games",
            }
        )
    return out


def list_games(
    status: str = "all",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    pinnacle: bool = False,
) -> Dict[str, Any]:
    today = datetime.now().strftime("%Y-%m-%d")
    if not date_from:
        date_from = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    if not date_to:
        date_to = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    limit = max(1, min(int(limit), 300))
    offset = max(0, int(offset))
    wanted = status if status in ("live", "finished", "not_started", "all") else "all"

    games: List[Dict[str, Any]] = []
    api_error = None
    seen: set = set()

    # Live / Not Started / All → API Today
    need_api = wanted in ("live", "not_started", "all")
    if need_api:
        try:
            for g in _fetch_today_from_api():
                if g["id"] not in seen:
                    games.append(g)
                    seen.add(g["id"])
        except Exception as e:
            api_error = str(e)
        # DB-Upcoming ergänzen (API-Limit/429 → Spiele fehlen sonst)
        for g in _fetch_upcoming_from_db(date_from, date_to):
            if g["id"] not in seen:
                games.append(g)
                seen.add(g["id"])

    # Finished (+ all) → DB im Datumsbereich
    if wanted in ("finished", "all"):
        finished = _fetch_finished_from_db(date_from, date_to)
        for g in finished:
            if g["id"] not in seen:
                games.append(g)
                seen.add(g["id"])

    # Datumsfenster auf alle Quellen anwenden
    games = [
        g
        for g in games
        if date_from <= _date_key(g.get("date")) <= date_to
    ]

    # Enrich glicko + DB odds
    conn = _conn()
    glicko_map, odds_map = _glicko_and_db_odds(conn, [g["id"] for g in games])
    for g in games:
        gl = glicko_map.get(g["id"])
        od = odds_map.get(g["id"])
        g["rating_h"] = gl["home_rating"] if gl else None
        g["rating_a"] = gl["away_rating"] if gl else None
        g["rd_h"] = gl["home_rd"] if gl else None
        g["rd_a"] = gl["away_rd"] if gl else None
        g["vol_h"] = gl["home_volatility"] if gl else None
        g["vol_a"] = gl["away_volatility"] if gl else None
        g["xg_glicko_h"] = gl["home_xg"] if gl else None
        g["xg_glicko_a"] = gl["away_xg"] if gl else None
        g["p_home"] = gl["home_win_probability"] if gl else None
        g["p_draw"] = gl["draw_probability"] if gl else None
        g["p_away"] = gl["away_win_probability"] if gl else None
        g["glicko_updated"] = gl["updated"] if gl else None
        # DB-Quoten nur setzen, wenn noch keine aus Today-API da sind
        if not g.get("has_odds") and od:
            g["odd_home"] = od["odd_home"]
            g["odd_draw"] = od["odd_draw"]
            g["odd_away"] = od["odd_away"]
            g["odd_over_25"] = od["odd_over_25"]
            g["odd_under_25"] = od["odd_under_25"]
            g["odds_source"] = "db"
            g["bookmaker"] = "DB"
            g["has_odds"] = any(
                od[k] is not None
                for k in ("odd_home", "odd_draw", "odd_away", "odd_over_25", "odd_under_25")
            )
        elif "has_odds" not in g:
            g["has_odds"] = False
            g.setdefault("odd_home", None)
            g.setdefault("odd_draw", None)
            g.setdefault("odd_away", None)
            g.setdefault("odd_over_25", None)
            g.setdefault("odd_under_25", None)
        # Tore aus Score parsen (für Winner-Markierung)
        hg = ag = None
        if g.get("score") and ":" in str(g["score"]):
            try:
                parts = str(g["score"]).split(":")
                hg, ag = int(parts[0]), int(parts[1])
            except (TypeError, ValueError, IndexError):
                pass
        g["home_goals"] = hg
        g["away_goals"] = ag
        g["total_goals"] = (hg + ag) if hg is not None and ag is not None else None
        if hg is not None and ag is not None:
            if hg > ag:
                g["winner_1x2"] = "home"
            elif hg < ag:
                g["winner_1x2"] = "away"
            else:
                g["winner_1x2"] = "draw"
            g["winner_ou25"] = "over" if (hg + ag) > 2.5 else "under"
        else:
            g["winner_1x2"] = None
            g["winner_ou25"] = None

    # Filter + Suche
    counts = {"all": 0, "live": 0, "finished": 0, "not_started": 0, "other": 0}
    q_norm = (q or "").strip().lower()
    filtered: List[Dict[str, Any]] = []
    for g in games:
        bucket = g.get("status_bucket") or classify_status(g.get("status"), g.get("status_name"))
        g["status_bucket"] = bucket
        counts["all"] += 1
        counts[bucket] = counts.get(bucket, 0) + 1
        if wanted != "all" and bucket != wanted:
            continue
        if q_norm:
            hay = " ".join(
                str(x or "")
                for x in (g.get("home"), g.get("away"), g.get("league"), g.get("country"), g.get("id"))
            ).lower()
            if q_norm not in hay:
                continue
        filtered.append(g)

    # Sort: mit Quoten zuerst, dann Status, dann Kickoff
    order = {"live": 0, "not_started": 1, "finished": 2, "other": 3}
    filtered.sort(
        key=lambda x: (
            0 if x.get("has_odds") else 1,
            order.get(x["status_bucket"], 9),
            x.get("date") or "",
        )
    )

    total = len(filtered)
    with_odds_count = sum(1 for g in filtered if g.get("has_odds"))
    page = filtered[offset : offset + limit]

    if pinnacle and page:
        for item in page[:40]:
            pin = fetch_pinnacle_odds(item["id"])
            if pin.get("odd_home") is not None or pin.get("odd_away") is not None:
                item["odd_home"] = pin.get("odd_home")
                item["odd_draw"] = pin.get("odd_draw")
                item["odd_away"] = pin.get("odd_away")
                item["odd_over_25"] = pin.get("odd_over_25")
                item["odd_under_25"] = pin.get("odd_under_25")
                item["bookmaker"] = pin.get("bookmaker") or "Pinnacle"
                item["odds_source"] = "pinnacle"
                item["has_odds"] = True
            elif pin.get("error"):
                item["odds_error"] = pin["error"]

    return {
        "date_from": date_from,
        "date_to": date_to,
        "today": today,
        "status": wanted,
        "pinnacle_bookmaker_id": PINNACLE_BOOKMAKER_ID,
        "counts": counts,
        "total": total,
        "with_odds": with_odds_count,
        "limit": limit,
        "offset": offset,
        "games": page,
        "api_error": api_error,
    }
