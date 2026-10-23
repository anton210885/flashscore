"""Katalog aller relevanten SStats-Parameter (Glicko, xG, Stats, Odds, Profits)."""
from __future__ import annotations

import csv
import io
import json
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

from config import config as cfg
from api.sstats_client import SStatsClient
from database import DatabaseManager

DB_PATH = "data/flashscore.db"


# Statische Feldkataloge mit Bedeutung
GLICKO_FIELDS = [
    {"key": "homeRating", "label": "Home Glicko Rating", "when": "pre", "group": "glicko",
     "desc": "Glicko-2 Stärke Home vor dem Spiel"},
    {"key": "awayRating", "label": "Away Glicko Rating", "when": "pre", "group": "glicko",
     "desc": "Glicko-2 Stärke Away vor dem Spiel"},
    {"key": "homeRd", "label": "Home RD", "when": "pre", "group": "glicko",
     "desc": "Rating Deviation Home (Unsicherheit)"},
    {"key": "awayRd", "label": "Away RD", "when": "pre", "group": "glicko",
     "desc": "Rating Deviation Away"},
    {"key": "homeVolatility", "label": "Home Volatility", "when": "pre", "group": "glicko",
     "desc": "Volatilität Home"},
    {"key": "awayVolatility", "label": "Away Volatility", "when": "pre", "group": "glicko",
     "desc": "Volatilität Away"},
    {"key": "homeXg", "label": "Home xG (Modell)", "when": "pre", "group": "glicko",
     "desc": "Erwartete Tore Home laut Glicko-Modell (nicht Match-xG)"},
    {"key": "awayXg", "label": "Away xG (Modell)", "when": "pre", "group": "glicko",
     "desc": "Erwartete Tore Away laut Glicko-Modell"},
    {"key": "homeWinProbability", "label": "P(Home Win)", "when": "pre", "group": "glicko",
     "desc": "Siegwahrscheinlichkeit Home"},
    {"key": "awayWinProbability", "label": "P(Away Win)", "when": "pre", "group": "glicko",
     "desc": "Siegwahrscheinlichkeit Away"},
    {"key": "drawProbability", "label": "P(Draw) berechnet", "when": "pre", "group": "glicko",
     "desc": "1 − homeWin − awayWin (lokal berechnet)"},
    {"key": "updated", "label": "Updated", "when": "pre", "group": "glicko",
     "desc": "Update-Zeitstempel vom Modell"},
]

GAME_FIELDS = [
    {"key": "id", "label": "Game ID", "when": "both", "group": "game", "desc": "SStats Match-ID"},
    {"key": "flashId", "label": "Flashscore ID", "when": "both", "group": "game", "desc": "Flashscore-Referenz"},
    {"key": "date", "label": "Kickoff", "when": "both", "group": "game", "desc": "Anstoßzeit (ISO)"},
    {"key": "dateUtc", "label": "Kickoff UTC", "when": "both", "group": "game", "desc": "Unix-Timestamp"},
    {"key": "status", "label": "Status Code", "when": "both", "group": "game", "desc": "z.B. 8 = Finished"},
    {"key": "statusName", "label": "Status Name", "when": "both", "group": "game", "desc": "Finished / 1st Half / …"},
    {"key": "elapsed", "label": "Spielminute", "when": "live", "group": "game", "desc": "Aktuelle Minute"},
    {"key": "extraMinutes", "label": "Nachspielzeit", "when": "live", "group": "game", "desc": "Extra Minuten"},
    {"key": "homeResult", "label": "Home Result", "when": "post", "group": "game", "desc": "Aktueller Stand Home"},
    {"key": "awayResult", "label": "Away Result", "when": "post", "group": "game", "desc": "Aktueller Stand Away"},
    {"key": "homeHTResult", "label": "Home HT", "when": "post", "group": "game", "desc": "Halbzeit Home"},
    {"key": "awayHTResult", "label": "Away HT", "when": "post", "group": "game", "desc": "Halbzeit Away"},
    {"key": "homeFTResult", "label": "Home FT", "when": "post", "group": "game", "desc": "Endstand Home"},
    {"key": "awayFTResult", "label": "Away FT", "when": "post", "group": "game", "desc": "Endstand Away"},
    {"key": "roundName", "label": "Runde", "when": "both", "group": "game", "desc": "Spieltag / Runde"},
    {"key": "homeTeam.id", "label": "Home Team ID", "when": "both", "group": "game", "desc": "Team-ID Home"},
    {"key": "homeTeam.name", "label": "Home Team", "when": "both", "group": "game", "desc": "Teamname Home"},
    {"key": "awayTeam.id", "label": "Away Team ID", "when": "both", "group": "game", "desc": "Team-ID Away"},
    {"key": "awayTeam.name", "label": "Away Team", "when": "both", "group": "game", "desc": "Teamname Away"},
    {"key": "season.year", "label": "Saisonjahr", "when": "both", "group": "game", "desc": "season_year"},
    {"key": "season.league.id", "label": "Liga ID", "when": "both", "group": "game", "desc": "league_id"},
    {"key": "season.league.name", "label": "Liga", "when": "both", "group": "game", "desc": "Liganame"},
]

# Match-Statistiken (Home/Away-Paare)
_STAT_PAIRS = [
    ("expectedGoals", "Match-xG (Shot-basiert)", "xg"),
    ("calculatedXg", "Berechnetes xG (oft null)", "xg"),
    ("xgOnTarget", "xG on Target (xGOT)", "xg"),
    ("xgotFaced", "xGOT faced (Torwart)", "xg"),
    ("goalsPrevented", "Goals Prevented", "xg"),
    ("expectedAssists", "Expected Assists (xA)", "xg"),
    ("bigChances", "Große Chancen", "xg"),
    ("totalShots", "Schüsse gesamt", "shots"),
    ("shotsOnGoal", "Torschüsse", "shots"),
    ("shotsOffGoal", "Schüsse daneben", "shots"),
    ("shotsInsideBox", "Schüsse im Strafraum", "shots"),
    ("shotsOutsideBox", "Schüsse außerhalb", "shots"),
    ("blockedShots", "Geblockte Schüsse", "shots"),
    ("ballPossession", "Ballbesitz %", "possession"),
    ("attacks", "Angriffe", "attacks"),
    ("dangerousAttacks", "Gefährliche Angriffe", "attacks"),
    ("totalPasses", "Pässe gesamt", "passing"),
    ("passesAccurate", "Angekommene Pässe", "passing"),
    ("passesInFinalThird", "Pässe im letzten Drittel", "passing"),
    ("accurateThroughPasses", "Steilpässe angekommen", "passing"),
    ("longPasses", "Lange Bälle", "passing"),
    ("crosses", "Flanken", "passing"),
    ("crossesCompleted", "Flanken angekommen", "passing"),
    ("totalTackles", "Tackles", "defense"),
    ("successTackles", "Erfolgreiche Tackles", "defense"),
    ("interceptions", "Abfangaktionen", "defense"),
    ("clearances", "Klärungsaktionen", "defense"),
    ("clearancesCompleted", "Klärungen erfolgreich", "defense"),
    ("duelsWon", "Zweikämpfe gewonnen", "defense"),
    ("goalkeeperSaves", "Paraden", "defense"),
    ("cornerKicks", "Ecken", "setpieces"),
    ("freeKicks", "Freistöße", "setpieces"),
    ("throwins", "Einwürfe", "setpieces"),
    ("fouls", "Fouls", "discipline"),
    ("yellowCards", "Gelbe Karten", "discipline"),
    ("redCards", "Rote Karten", "discipline"),
    ("offsides", "Abseits", "discipline"),
    ("headedGoals", "Kopftore", "goals"),
    ("hitTheWoodwork", "Holz", "shots"),
    ("errorsLeadingToShot", "Fehler → Schuss", "errors"),
    ("errorsLeadingToGoal", "Fehler → Tor", "errors"),
    ("touchesInOppositionBox", "Touches im gegn. Strafraum", "attacks"),
    ("distanceCovered", "Laufleistung", "physical"),
]

STATS_FIELDS: List[Dict[str, Any]] = []
for base, label, subgroup in _STAT_PAIRS:
    for side, side_label in (("Home", "Home"), ("Away", "Away")):
        STATS_FIELDS.append({
            "key": f"{base}{side}",
            "label": f"{label} ({side_label})",
            "when": "post",
            "group": "statistics",
            "subgroup": subgroup,
            "desc": f"Match-Statistik {label} – {side_label}",
        })

ODDS_FIELDS = [
    {"key": "bookmakerId", "label": "Bookie ID", "when": "both", "group": "odds", "desc": "Buchmacher-ID"},
    {"key": "bookmakerName", "label": "Bookie", "when": "both", "group": "odds", "desc": "Buchmacher-Name"},
    {"key": "marketId", "label": "Market ID", "when": "both", "group": "odds", "desc": "Markt-ID"},
    {"key": "marketName", "label": "Market", "when": "both", "group": "odds",
     "desc": "z.B. Match Winner, Goals Over/Under, BTTS"},
    {"key": "odds[].name", "label": "Outcome", "when": "both", "group": "odds", "desc": "Home/Draw/Away/Over…"},
    {"key": "odds[].value", "label": "Quote", "when": "both", "group": "odds", "desc": "Dezimalquote"},
    {"key": "opening", "label": "Opening-Flag", "when": "pre", "group": "odds",
     "desc": "Query ?opening=true für Eröffnungsquoten"},
]

PROFITS_FIELDS = [
    {"key": "home|away|…", "label": "Team-Scope", "when": "post", "group": "profits",
     "desc": "home / away / homeFirstHalf / awayFirstHalf / …"},
    {"key": "market", "label": "Market", "when": "post", "group": "profits", "desc": "z.B. Match Winner"},
    {"key": "outcomes[].name", "label": "Outcome", "when": "post", "group": "profits", "desc": "Win/Draw/Lose…"},
    {"key": "outcomes[].profit", "label": "Profit", "when": "post", "group": "profits",
     "desc": "Kumulativer Profit über Historie"},
    {"key": "outcomes[].gamesCount", "label": "Spiele", "when": "post", "group": "profits", "desc": "Anzahl Spiele"},
    {"key": "outcomes[].winCount", "label": "Treffer", "when": "post", "group": "profits", "desc": "Gewonnene Wetten"},
    {"key": "outcomes[].profitHistory", "label": "Profit-Verlauf", "when": "post", "group": "profits",
     "desc": "Array der Profit-Kurve"},
]

ENDPOINTS = [
    {
        "path": "/games/list",
        "method": "GET",
        "desc": "Spiele-Liste (Filter: Liga, Datum, Status, …)",
        "auth": "apikey Query",
    },
    {
        "path": "/Games/{id}",
        "method": "GET",
        "desc": "Spiel-Detail: game + statistics + lineups + events",
        "auth": "Bearer / apikey",
    },
    {
        "path": "/games/glicko/{id}",
        "method": "GET",
        "desc": "Pre-Match Glicko Rating, Modell-xG, Win-Probabilities",
        "auth": "apikey Query",
    },
    {
        "path": "/Odds/{id}",
        "method": "GET",
        "desc": "Quoten je Bookmaker (?opening=true für Opening)",
        "auth": "apikey Query",
    },
    {
        "path": "/Games/profits",
        "method": "GET",
        "desc": "Historische Profitabilität der Teams",
        "auth": "apikey Query",
    },
]


def _nested_get(obj: Any, path: str) -> Any:
    cur = obj
    for part in path.split("."):
        if cur is None:
            return None
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _pick_sample_game_id() -> Optional[int]:
    try:
        conn = DatabaseManager(DB_PATH).get_connection()
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT id FROM games
            WHERE home_ft_result IS NOT NULL AND away_ft_result IS NOT NULL
            ORDER BY date DESC LIMIT 1
            """
        ).fetchone()
        return int(row["id"]) if row else None
    except Exception:
        return None


def build_catalog(live: bool = True, game_id: Optional[int] = None) -> Dict[str, Any]:
    """Vollständiger Parameter-Katalog + optionale Live-Stichprobe."""
    fields: List[Dict[str, Any]] = []
    for block in (GLICKO_FIELDS, GAME_FIELDS, STATS_FIELDS, ODDS_FIELDS, PROFITS_FIELDS):
        fields.extend(block)

    sample: Dict[str, Any] = {}
    sample_values: Dict[str, Any] = {}
    gid = game_id or _pick_sample_game_id()
    error = None

    if live and gid:
        try:
            client = SStatsClient(base_url=cfg.BASE_URL, api_key=getattr(cfg, "API_KEY", None))
            raw = client.get_game(gid)
            data = raw.get("data", raw) if isinstance(raw, dict) else {}
            game = data.get("game", {}) if isinstance(data, dict) else {}
            stats = data.get("statistics", {}) if isinstance(data, dict) else {}

            glicko_raw = client.get_game_glicko(gid)
            if isinstance(glicko_raw, dict):
                glicko = glicko_raw.get("glicko") or (
                    glicko_raw.get("data", {}).get("glicko") if isinstance(glicko_raw.get("data"), dict) else glicko_raw
                )
            else:
                glicko = {}

            odds_raw = client.get_game_odds(gid)
            odds = odds_raw.get("data", odds_raw) if isinstance(odds_raw, dict) else odds_raw

            sample = {
                "game_id": gid,
                "match": f"{(game.get('homeTeam') or {}).get('name')} – {(game.get('awayTeam') or {}).get('name')}",
                "date": game.get("date"),
                "league": ((game.get("season") or {}).get("league") or {}).get("name"),
                "glicko": glicko if isinstance(glicko, dict) else {},
                "statistics_keys": sorted(stats.keys()) if isinstance(stats, dict) else [],
                "odds_bookmakers": (
                    [o.get("bookmakerName") for o in odds[:8]] if isinstance(odds, list) else []
                ),
            }

            # Werte an Felder hängen
            for f in fields:
                key = f["key"]
                val = None
                if f["group"] == "glicko" and isinstance(glicko, dict):
                    if key == "drawProbability":
                        hw = glicko.get("homeWinProbability")
                        aw = glicko.get("awayWinProbability")
                        if hw is not None and aw is not None:
                            val = max(0.0, 1.0 - float(hw) - float(aw))
                    else:
                        val = glicko.get(key)
                elif f["group"] == "game":
                    val = _nested_get(game, key)
                elif f["group"] == "statistics" and isinstance(stats, dict):
                    val = stats.get(key)
                sample_values[key] = val
                f["sample"] = val

        except Exception as e:
            error = str(e)

    # Felder ohne Live-Sample trotzdem listen
    for f in fields:
        f.setdefault("sample", sample_values.get(f["key"]))

    by_group: Dict[str, List[Dict[str, Any]]] = {}
    for f in fields:
        by_group.setdefault(f["group"], []).append(f)

    return {
        "base_url": cfg.BASE_URL,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "endpoints": ENDPOINTS,
        "groups": [
            {"id": "glicko", "title": "Glicko (vor dem Spiel)", "count": len(by_group.get("glicko", []))},
            {"id": "game", "title": "Spiel-Grunddaten", "count": len(by_group.get("game", []))},
            {"id": "statistics", "title": "Match-Statistiken / xG", "count": len(by_group.get("statistics", []))},
            {"id": "odds", "title": "Quoten", "count": len(by_group.get("odds", []))},
            {"id": "profits", "title": "Profits", "count": len(by_group.get("profits", []))},
        ],
        "fields": fields,
        "sample": sample,
        "error": error,
        "field_count": len(fields),
    }


def catalog_to_csv(catalog: Dict[str, Any]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=["group", "subgroup", "key", "label", "when", "desc", "sample"],
        extrasaction="ignore",
    )
    writer.writeheader()
    for f in catalog.get("fields", []):
        writer.writerow({
            "group": f.get("group"),
            "subgroup": f.get("subgroup", ""),
            "key": f.get("key"),
            "label": f.get("label"),
            "when": f.get("when"),
            "desc": f.get("desc"),
            "sample": "" if f.get("sample") is None else f.get("sample"),
        })
    return buf.getvalue()


def save_catalog_files(catalog: Dict[str, Any], out_dir: str = "data") -> Dict[str, str]:
    import os

    os.makedirs(out_dir, exist_ok=True)
    json_path = os.path.join(out_dir, "sstats_parameters.json")
    csv_path = os.path.join(out_dir, "sstats_parameters.csv")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2, default=str)
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        f.write(catalog_to_csv(catalog))
    return {"json": json_path, "csv": csv_path}
