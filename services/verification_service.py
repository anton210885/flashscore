"""Verifikation: Strategie-Treffer vor dem Spiel festhalten und nach dem Spiel abrechnen.

Ab dem ersten Scan wird jedes bevorstehende Spiel, das zu einer gespeicherten Strategie
passt, mit Quote und Strategie-Einstellungen gespeichert (wie eine platzierte Wette).
Passt es später nicht mehr (z. B. Quote verschoben), bleibt es drin — still_matches = 0.
Nach dem Spiel kommt das Endergebnis aus `games`; abgerechnet wird mit der Quote,
die die Strategie verwendet (odds_type opening/closing).
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services import strategy_service as strat

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS verification_bets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id TEXT NOT NULL,
    strategy_name TEXT,
    filters_json TEXT,
    game_id INTEGER NOT NULL,
    market TEXT NOT NULL,
    date TEXT,
    country TEXT,
    league TEXT,
    home TEXT,
    away TEXT,
    odds_type TEXT,
    odds_first REAL,
    odds_opening REAL,
    odds_closing REAL,
    first_seen_at TEXT,
    last_seen_at TEXT,
    still_matches INTEGER NOT NULL DEFAULT 1,
    home_score INTEGER,
    away_score INTEGER,
    won INTEGER,
    profit REAL,
    settled_at TEXT,
    UNIQUE(strategy_id, game_id, market)
);
CREATE INDEX IF NOT EXISTS idx_verification_open ON verification_bets(settled_at, game_id);
CREATE TABLE IF NOT EXISTS verification_strategy_stats (
    strategy_id TEXT PRIMARY KEY,
    strategy_name TEXT,
    backtest_n INTEGER,
    backtest_roi REAL,
    updated_at TEXT
);
"""


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    conn.commit()


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _not_started(date: Any) -> bool:
    try:
        ko = datetime.fromisoformat(str(date))
    except (TypeError, ValueError):
        return False
    if ko.tzinfo is None:
        return ko >= datetime.now()
    return ko >= datetime.now(timezone.utc)


def record_upcoming(conn: sqlite3.Connection, presets: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Bevorstehende Treffer aller Strategien eintragen bzw. Quoten aktualisieren."""
    from services import web_strategy_service as web_strat

    ensure_schema(conn)
    stats: Dict[str, Any] = {"strategies": 0, "new": 0, "updated": 0, "no_longer_matching": 0, "errors": []}
    now = _now()
    for p in presets or []:
        sid, name, filters = p.get("id"), p.get("name"), p.get("filters") or {}
        if not sid:
            continue
        try:
            a = web_strat.analyze(filters, limit_results=200)
        except Exception as e:
            stats["errors"].append(f"{name}: {e}")
            continue
        if not a.get("ok"):
            stats["errors"].append(f"{name}: {a.get('error')}")
            continue
        stats["strategies"] += 1
        m = a.get("metrics") or {}
        conn.execute(
            """
            INSERT INTO verification_strategy_stats (strategy_id, strategy_name, backtest_n, backtest_roi, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(strategy_id) DO UPDATE SET
                strategy_name = excluded.strategy_name,
                backtest_n = excluded.backtest_n,
                backtest_roi = excluded.backtest_roi,
                updated_at = excluded.updated_at
            """,
            (sid, name, int(m.get("n") or 0), m.get("roi_pct"), now),
        )
        up = a.get("upcoming") or {}
        if up.get("skipped"):
            continue
        odds_type = str(filters.get("odds_type") or "closing")
        filters_json = json.dumps(filters, ensure_ascii=False, sort_keys=True)
        seen = set()
        for x in up.get("matches") or []:
            if not _not_started(x.get("date")) or x.get("game_id") is None:
                continue
            key = (int(x["game_id"]), str(x.get("market")))
            seen.add(key)
            known = conn.execute(
                "SELECT 1 FROM verification_bets WHERE strategy_id = ? AND game_id = ? AND market = ?",
                (sid, key[0], key[1]),
            ).fetchone()
            cur = conn.execute(
                """
                INSERT INTO verification_bets (
                    strategy_id, strategy_name, filters_json, game_id, market, date, country,
                    league, home, away, odds_type, odds_first, odds_opening, odds_closing,
                    first_seen_at, last_seen_at, still_matches
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(strategy_id, game_id, market) DO UPDATE SET
                    date = excluded.date,
                    odds_opening = COALESCE(excluded.odds_opening, verification_bets.odds_opening),
                    odds_closing = COALESCE(excluded.odds_closing, verification_bets.odds_closing),
                    last_seen_at = excluded.last_seen_at,
                    still_matches = 1
                WHERE verification_bets.settled_at IS NULL
                """,
                (
                    sid, name, filters_json, key[0], key[1], x.get("date"), x.get("country"),
                    x.get("league"), x.get("home"), x.get("away"), odds_type, x.get("odds"),
                    x.get("odds_opening"), x.get("odds_closing"), now, now,
                ),
            )
            if cur.rowcount:
                stats["updated" if known else "new"] += 1
        # Noch offene, nicht angepfiffene Einträge, die diesmal nicht mehr passen: behalten, markieren
        for gid, market, date in conn.execute(
            """
            SELECT game_id, market, date FROM verification_bets
            WHERE strategy_id = ? AND settled_at IS NULL AND still_matches = 1
            """,
            (sid,),
        ).fetchall():
            if (int(gid), str(market)) not in seen and _not_started(date):
                conn.execute(
                    "UPDATE verification_bets SET still_matches = 0 WHERE strategy_id = ? AND game_id = ? AND market = ?",
                    (sid, gid, market),
                )
                stats["no_longer_matching"] += 1
        conn.commit()
    return stats


def settle(conn: sqlite3.Connection) -> Dict[str, int]:
    """Offene Einträge mit Endergebnis aus `games` abrechnen."""
    ensure_schema(conn)
    rows = conn.execute(
        """
        SELECT v.id, v.market, v.odds_type, v.odds_first, v.odds_opening, v.odds_closing,
               g.home_ft_result, g.away_ft_result
        FROM verification_bets v
        JOIN games g ON g.id = v.game_id
        WHERE v.settled_at IS NULL
          AND g.home_ft_result IS NOT NULL AND g.away_ft_result IS NOT NULL
        """
    ).fetchall()
    settled = 0
    now = _now()
    for vid, market, odds_type, o_first, o_open, o_close, h, a in rows:
        odds = (o_open if odds_type == "opening" else o_close) or o_first
        profit = strat.settle_market(market, h, a, odds)
        if profit is None:
            continue
        conn.execute(
            """
            UPDATE verification_bets
            SET home_score = ?, away_score = ?, won = ?, profit = ?, settled_at = ?
            WHERE id = ?
            """,
            (int(h), int(a), 1 if profit > 0 else 0, float(profit), now, vid),
        )
        settled += 1
    conn.commit()
    return {"settled": settled, "open_with_result": len(rows)}


def _streak(bets: List[Dict[str, Any]]) -> Dict[str, int]:
    lose = win = 0
    for b in sorted(bets, key=lambda r: str(r.get("date") or "")):
        if b.get("won") == 1:
            win, lose = win + 1, 0
        else:
            lose, win = lose + 1, 0
    return {"losing_streak": lose, "winning_streak": win}


def report(conn: sqlite3.Connection, strategy_id: Optional[str] = None) -> Dict[str, Any]:
    """Alle Einträge + Zusammenfassung pro Strategie."""
    ensure_schema(conn)
    conn.row_factory = sqlite3.Row
    where, params = ("WHERE strategy_id = ?", [strategy_id]) if strategy_id else ("", [])
    bets = [
        {k: r[k] for k in r.keys() if k != "filters_json"}
        for r in conn.execute(f"SELECT * FROM verification_bets {where} ORDER BY date ASC, strategy_name ASC", params)
    ]
    for b in bets:
        b["odds_used"] = (
            (b["odds_opening"] if b["odds_type"] == "opening" else b["odds_closing"]) or b["odds_first"]
        )
        b["status"] = "offen" if b["settled_at"] is None else ("gewonnen" if b["won"] == 1 else "verloren")
    backtest = {
        r["strategy_id"]: dict(r) for r in conn.execute("SELECT * FROM verification_strategy_stats")
    }
    by_strategy: Dict[str, List[Dict[str, Any]]] = {}
    for b in bets:
        by_strategy.setdefault(b["strategy_id"], []).append(b)
    summary = []
    for sid, items in by_strategy.items():
        done = [b for b in items if b["settled_at"] is not None]
        wins = sum(1 for b in done if b["won"] == 1)
        profit = sum(float(b["profit"] or 0) for b in done)
        bt = backtest.get(sid) or {}
        summary.append(
            {
                "strategy_id": sid,
                "strategy": items[-1]["strategy_name"],
                "bets": len(items),
                "open": len(items) - len(done),
                "settled": len(done),
                "won": wins,
                "lost": len(done) - wins,
                "win_rate": (wins / len(done) * 100.0) if done else None,
                "profit": profit,
                "roi_pct": (profit / len(done) * 100.0) if done else None,
                "backtest_n": bt.get("backtest_n"),
                "backtest_roi": bt.get("backtest_roi"),
                **_streak(done),
            }
        )
    summary.sort(key=lambda s: str(s["strategy"] or ""))
    return {"ok": True, "bets": bets, "summary": summary}
