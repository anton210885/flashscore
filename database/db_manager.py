"""Database manager for SQLite game statistics database"""
import sqlite3
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path


class DatabaseManager:
    """Manages SQLite database for game statistics"""
    
    def __init__(self, db_path: str = "data/flashscore.db"):
        """Initialize database manager
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = None
        self._init_database()
    
    def _init_database(self):
        """Initialize database schema"""
        schema_file = Path(__file__).parent / "schema.sql"
        if schema_file.exists():
            with open(schema_file, 'r', encoding='utf-8') as f:
                schema = f.read()
            # Set timeout to 30 seconds to handle database locks
            self.conn = sqlite3.connect(str(self.db_path), timeout=30.0)
            # Enable WAL mode for better concurrency (allows multiple readers)
            self.conn.execute("PRAGMA journal_mode = WAL")
            self.conn.executescript(schema)
            self.conn.commit()
        else:
            # Create connection if schema file doesn't exist
            # Set timeout to 30 seconds to handle database locks
            self.conn = sqlite3.connect(str(self.db_path), timeout=30.0)
            # Enable WAL mode for better concurrency (allows multiple readers)
            self.conn.execute("PRAGMA journal_mode = WAL")
            self.conn.execute("PRAGMA foreign_keys = ON")
            self.conn.commit()
        
        # Odds-Pivot-View (DROP+CREATE); "already exists" bei parallelem Init ignorieren
        try:
            odds_view_file = Path(__file__).parent / "create_odds_view.sql"
            if odds_view_file.exists():
                with open(odds_view_file, 'r', encoding='utf-8') as f:
                    odds_view_sql = f.read()
                self.conn.executescript(odds_view_sql)
                self.conn.commit()
        except sqlite3.OperationalError as e:
            if "already exists" not in str(e).lower():
                raise
        except Exception:
            pass
        
        # Form2 table (saisonale Avgs) — auch bei bestehender DB
        try:
            from services.form2_service import ensure_form2_schema
            ensure_form2_schema(self.conn)
        except Exception:
            pass

        # Create upcoming_games table if it doesn't exist (for existing databases)
        try:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS upcoming_games (
                    id INTEGER PRIMARY KEY,
                    flash_id TEXT,
                    date TEXT NOT NULL,
                    date_utc INTEGER,
                    status INTEGER,
                    status_name TEXT,
                    elapsed INTEGER,
                    extra_minutes INTEGER,
                    home_result INTEGER,
                    away_result INTEGER,
                    home_ht_result INTEGER,
                    away_ht_result INTEGER,
                    home_ft_result INTEGER,
                    away_ft_result INTEGER,
                    home_team_id INTEGER,
                    home_team_name TEXT,
                    away_team_id INTEGER,
                    away_team_name TEXT,
                    league_id INTEGER,
                    league_name TEXT,
                    country_code TEXT,
                    country_name TEXT,
                    season_uid TEXT,
                    season_year INTEGER,
                    round_name TEXT,
                    venue_name TEXT,
                    venue_city TEXT,
                    referee_name TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(id)
                )
            """)
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_upcoming_games_date ON upcoming_games(date)")
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_upcoming_games_league_id ON upcoming_games(league_id)")
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_upcoming_games_status ON upcoming_games(status)")
            self.conn.commit()
        except Exception as e:
            # Table might already exist, that's okay
            pass
    
    def get_connection(self):
        """Get database connection"""
        # Check if connection exists and is still open
        if self.conn is None:
            # Set timeout to 30 seconds to handle database locks
            self.conn = sqlite3.connect(str(self.db_path), timeout=30.0)
            # Enable WAL mode for better concurrency (allows multiple readers)
            self.conn.execute("PRAGMA journal_mode = WAL")
            self.conn.execute("PRAGMA foreign_keys = ON")
        else:
            # Check if connection is closed and reopen if necessary
            try:
                self.conn.execute("SELECT 1")
            except (sqlite3.ProgrammingError, sqlite3.OperationalError):
                # Connection is closed, create a new one
                # Set timeout to 30 seconds to handle database locks
                self.conn = sqlite3.connect(str(self.db_path), timeout=30.0)
                # Enable WAL mode for better concurrency (allows multiple readers)
                self.conn.execute("PRAGMA journal_mode = WAL")
                self.conn.execute("PRAGMA foreign_keys = ON")
        return self.conn
    
    def save_game(self, game_data: Dict[str, Any]) -> bool:
        """Save a complete game with all statistics to database
        This method is for FINISHED games only - they go into the 'games' table for historical statistics
        
        Args:
            game_data: Complete game data from API (from /Games/{id} endpoint)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            conn = self.get_connection()
            
            # Handle API response structure: {"status": "OK", "data": {"game": {...}, "statistics": {...}}}
            # or {"game": {...}, "statistics": {...}} or just {"game": {...}}
            if "data" in game_data and isinstance(game_data["data"], dict):
                # API returns {"data": {"game": {...}, "statistics": {...}}}
                data = game_data["data"]
                game = data.get("game", data)
                stats = data.get("statistics", {})
            elif "game" in game_data:
                # Already wrapped as {"game": {...}}
                game = game_data["game"]
                stats = game_data.get("statistics", game.get("statistics", {}))
            else:
                # Direct game object
                game = game_data
                stats = game.get("statistics", {})
            # API liefert bei manchen Spielen "statistics": null
            if not isinstance(stats, dict):
                stats = {}

            # Extract basic game info
            game_id = game.get("id")
            if not game_id:
                return False
            
            # Check if game is finished - if not, use save_upcoming_game instead
            # Wichtig: bloße Scores (z.B. Live 0:0) zählen NICHT als Finished
            status = game.get("status")
            status_name = str(game.get("statusName") or game.get("status_name") or "")
            sn = status_name.lower()
            try:
                status_i = int(status) if status is not None else None
            except (TypeError, ValueError):
                status_i = None
            is_finished = (
                status_i in (7, 8, 9, 10)
                or "finished" in sn
                or "after penalties" in sn
                or "after extra time" in sn
            )
            
            if not is_finished:
                # Game is not finished, save to upcoming_games instead
                return self.save_upcoming_game(game_data)
            
            # Calculate derived values (explizit None-check, 0 ist gültiges Ergebnis)
            home_ft = game.get("homeFTResult")
            away_ft = game.get("awayFTResult")
            if home_ft is None:
                home_ft = game.get("homeResult")
            if away_ft is None:
                away_ft = game.get("awayResult")
            home_goals = 0 if home_ft is None else int(home_ft)
            away_goals = 0 if away_ft is None else int(away_ft)
            total_goals = int(home_goals) + int(away_goals)
            
            # Extract team info
            home_team = game.get("homeTeam", {})
            away_team = game.get("awayTeam", {})
            
            # Extract league/season info
            season = game.get("season", {})
            league = season.get("league", {})
            country = league.get("country", {})
            
            # Extract xG from statistics (now correctly from data.statistics)
            # Try calculatedXg first, fallback to expectedGoals if not available
            calculated_xg_home = stats.get("calculatedXgHome")
            calculated_xg_away = stats.get("calculatedXgAway")
            
            # Fallback to expectedGoals if calculatedXg is not available
            if calculated_xg_home is None:
                calculated_xg_home = stats.get("expectedGoalsHome")
            if calculated_xg_away is None:
                calculated_xg_away = stats.get("expectedGoalsAway")
            
            # Extract venue
            venue = game.get("venue", {})
            
            # Insert/update game
            # Total: 36 columns
            # Count: id(1), flash_id(2), date(3), date_utc(4), status(5), status_name(6),
            #        elapsed(7), extra_minutes(8), home_result(9), away_result(10),
            #        home_ht_result(11), away_ht_result(12), home_ft_result(13), away_ft_result(14),
            #        home_team_id(15), home_team_name(16), away_team_id(17), away_team_name(18),
            #        league_id(19), league_name(20), country_code(21), country_name(22),
            #        season_uid(23), season_year(24), round_name(25),
            #        venue_name(26), venue_city(27), referee_name(28),
            #        calculated_xg_home(29), calculated_xg_away(30),
            #        total_goals(31), over_25(32), over_35(33), over_45(34),
            #        created_at(35), updated_at(36)
            conn.execute("""
                INSERT OR REPLACE INTO games (
                    id, flash_id, date, date_utc, status, status_name,
                    elapsed, extra_minutes,
                    home_result, away_result, home_ht_result, away_ht_result,
                    home_ft_result, away_ft_result,
                    home_team_id, home_team_name,
                    away_team_id, away_team_name,
                    league_id, league_name, country_code, country_name,
                    season_uid, season_year, round_name,
                    venue_name, venue_city, referee_name,
                    calculated_xg_home, calculated_xg_away,
                    total_goals, over_25, over_35, over_45,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE((SELECT created_at FROM games WHERE id = ?), CURRENT_TIMESTAMP), ?)
            """, (
                game_id,  # 1
                game.get("flashId"),  # 2
                game.get("date"),  # 3
                game.get("dateUtc"),  # 4
                game.get("status"),  # 5
                game.get("statusName"),  # 6
                game.get("elapsed"),  # 7
                game.get("extraMinutes"),  # 8
                home_goals,  # 9
                away_goals,  # 10
                game.get("homeHTResult"),  # 11
                game.get("awayHTResult"),  # 12
                home_goals,  # 13 home_ft_result
                away_goals,  # 14 away_ft_result
                home_team.get("id"),  # 15
                home_team.get("name"),  # 16
                away_team.get("id"),  # 17
                away_team.get("name"),  # 18
                league.get("id"),  # 19
                league.get("name"),  # 20
                country.get("code"),  # 21
                country.get("name"),  # 22
                season.get("uid"),  # 23
                season.get("year"),  # 24
                game.get("roundName"),  # 25
                venue.get("name"),  # 26
                venue.get("city"),  # 27
                game.get("refereeName"),  # 28
                calculated_xg_home,  # 29
                calculated_xg_away,  # 30
                total_goals,  # 31
                1 if total_goals > 2.5 else 0,  # 32
                1 if total_goals > 3.5 else 0,  # 33
                1 if total_goals > 4.5 else 0,  # 34
                game_id,  # 35 - For COALESCE to preserve created_at on REPLACE
                datetime.now().isoformat()  # 36 - updated_at
            ))
            
            # Save statistics
            if stats:
                conn.execute("""
                    INSERT OR REPLACE INTO game_statistics (
                        game_id, shots_on_goal_home, shots_on_goal_away,
                        shots_off_goal_home, shots_off_goal_away,
                        total_shots_home, total_shots_away,
                        blocked_shots_home, blocked_shots_away,
                        shots_inside_box_home, shots_inside_box_away,
                        shots_outside_box_home, shots_outside_box_away,
                        ball_possession_home, ball_possession_away,
                        total_passes_home, total_passes_away,
                        passes_accurate_home, passes_accurate_away,
                        fouls_home, fouls_away,
                        corner_kicks_home, corner_kicks_away,
                        yellow_cards_home, yellow_cards_away,
                        red_cards_home, red_cards_away,
                        goalkeeper_saves_home, goalkeeper_saves_away,
                        offsides_home, offsides_away,
                        expected_goals_home, expected_goals_away,
                        expected_assists_home, expected_assists_away,
                        big_chances_home, big_chances_away,
                        goals_prevented_home, goals_prevented_away,
                        other_stats_home, other_stats_away
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    game_id,
                    stats.get("shotsOnGoalHome"),
                    stats.get("shotsOnGoalAway"),
                    stats.get("shotsOffGoalHome"),
                    stats.get("shotsOffGoalAway"),
                    stats.get("totalShotsHome"),
                    stats.get("totalShotsAway"),
                    stats.get("blockedShotsHome"),
                    stats.get("blockedShotsAway"),
                    stats.get("shotsInsideBoxHome"),
                    stats.get("shotsInsideBoxAway"),
                    stats.get("shotsOutsideBoxHome"),
                    stats.get("shotsOutsideBoxAway"),
                    stats.get("ballPossessionHome"),
                    stats.get("ballPossessionAway"),
                    stats.get("totalPassesHome"),
                    stats.get("totalPassesAway"),
                    stats.get("passesAccurateHome"),
                    stats.get("passesAccurateAway"),
                    stats.get("foulsHome"),
                    stats.get("foulsAway"),
                    stats.get("cornerKicksHome"),
                    stats.get("cornerKicksAway"),
                    stats.get("yellowCardsHome"),
                    stats.get("yellowCardsAway"),
                    stats.get("redCardsHome"),
                    stats.get("redCardsAway"),
                    stats.get("goalkeeperSavesHome"),
                    stats.get("goalkeeperSavesAway"),
                    stats.get("offsidesHome"),
                    stats.get("offsidesAway"),
                    stats.get("expectedGoalsHome"),
                    stats.get("expectedGoalsAway"),
                    stats.get("expectedAssistsHome"),
                    stats.get("expectedAssistsAway"),
                    stats.get("bigChancesHome"),
                    stats.get("bigChancesAway"),
                    stats.get("goalsPreventedHome"),
                    stats.get("goalsPreventedAway"),
                    json.dumps(stats.get("otherStatsHome", {})) if stats.get("otherStatsHome") else None,
                    json.dumps(stats.get("otherStatsAway", {})) if stats.get("otherStatsAway") else None
                ))
            
            # Save events
            events = game.get("events", [])
            if events:
                conn.execute("DELETE FROM game_events WHERE game_id = ?", (game_id,))
                for event in events:
                    player = event.get("player", {})
                    assist_player = event.get("assistPlayer")
                    conn.execute("""
                        INSERT INTO game_events (
                            game_id, event_id, team_id, elapsed, extra_minutes,
                            type, name, player_id, player_name,
                            assist_player_id, assist_player_name
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        game_id,
                        event.get("id"),
                        event.get("teamId"),
                        event.get("elapsed"),
                        event.get("extra"),
                        event.get("type"),
                        event.get("name"),
                        player.get("id"),
                        player.get("name"),
                        assist_player.get("id") if assist_player else None,
                        assist_player.get("name") if assist_player else None
                    ))
            
            # Save lineups
            lineups = game.get("lineupPlayers", [])
            if lineups:
                conn.execute("DELETE FROM game_lineups WHERE game_id = ?", (game_id,))
                for player in lineups:
                    conn.execute("""
                        INSERT INTO game_lineups (
                            game_id, team_id, player_id, player_name,
                            number, position, grid, start_xi
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        game_id,
                        player.get("teamId"),
                        player.get("playerId"),
                        player.get("playerName"),
                        player.get("number"),
                        player.get("position"),
                        player.get("grid"),
                        1 if player.get("startXI") else 0
                    ))
            
            # Save player statistics
            player_stats = game.get("playerStats", [])
            if player_stats:
                conn.execute("DELETE FROM player_statistics WHERE game_id = ?", (game_id,))
                for ps in player_stats:
                    conn.execute("""
                        INSERT INTO player_statistics (
                            game_id, player_id, team_id, minutes, captain, substitute,
                            shots_total, shots_on, goals_total, goals_assists,
                            goals_conceded, goals_saves,
                            passes_total, passes_key, passes_accuracy,
                            tackles_total, tackles_blocks, tackles_interceptions,
                            duels_total, duels_won,
                            dribbles_attempts, dribbles_success, dribbles_past,
                            fouls_drawn, fouls_committed,
                            cards_yellow, cards_red,
                            penalty_won, penalty_committed,
                            penalty_scored, penalty_missed, penalty_saved,
                            offsides, rating
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        game_id,
                        ps.get("playerId"),
                        ps.get("teamId") if "teamId" in ps else None,
                        ps.get("minutes"),
                        1 if ps.get("capitan") else 0,
                        1 if ps.get("substitute") else 0,
                        ps.get("shotsTotal"),
                        ps.get("shotsOn"),
                        ps.get("goalsTotal"),
                        ps.get("goalsAssists"),
                        ps.get("goalsConceded"),
                        ps.get("goalsSaves"),
                        ps.get("passesTotal"),
                        ps.get("passesKey"),
                        ps.get("passesAccuracy"),
                        ps.get("tacklesTotal"),
                        ps.get("tacklesBlocks"),
                        ps.get("tacklesInterceptions"),
                        ps.get("duelsTotal"),
                        ps.get("duelsWon"),
                        ps.get("dribblesAttempts"),
                        ps.get("dribblesSuccess"),
                        ps.get("dribblesPast"),
                        ps.get("foulsDrawn"),
                        ps.get("foulsCommitted"),
                        ps.get("cardsYellow"),
                        ps.get("cardsRed"),
                        ps.get("penaltyWon"),
                        ps.get("penaltyCommited"),
                        ps.get("penaltyScored"),
                        ps.get("penaltyMissed"),
                        ps.get("penaltySaved"),
                        ps.get("offsides"),
                        ps.get("rating")
                    ))
            
            # Odds aus /Games nur, wenn noch keine da sind: das sind gerundete Werte eines
            # anderen Buchmachers ohne Opening — vorhandene Pinnacle-Quoten nicht überschreiben
            odds_list = game.get("odds", [])
            has_odds = conn.execute(
                "SELECT 1 FROM game_odds WHERE game_id = ? LIMIT 1", (game_id,)
            ).fetchone()
            if odds_list and not has_odds:
                for market in odds_list:
                    market_odds = market.get("odds", [])
                    for odd in market_odds:
                        conn.execute("""
                            INSERT INTO game_odds (
                                game_id, market_id, market_name, name, value, opening_value
                            ) VALUES (?, ?, ?, ?, ?, ?)
                        """, (
                            game_id,
                            market.get("marketId"),
                            market.get("marketName"),
                            odd.get("name"),
                            odd.get("value"),
                            odd.get("openingValue")
                        ))
            
            # Fertige Spiele nicht mehr in upcoming_games behalten (sonst „Heute“-Bug)
            conn.execute("DELETE FROM upcoming_games WHERE id = ?", (game_id,))

            conn.commit()
            return True
            
        except Exception as e:
            import traceback
            print(f"Error saving game {game_id}: {e}")
            print(f"Game data keys: {list(game.keys()) if isinstance(game, dict) else 'Not a dict'}")
            if isinstance(game, dict) and "statistics" in game:
                print(f"Statistics keys: {list(game['statistics'].keys()) if isinstance(game['statistics'], dict) else 'Not a dict'}")
            traceback.print_exc()
            if conn:
                conn.rollback()
            return False
    
    def save_upcoming_game(self, game_data: Dict[str, Any]) -> bool:
        """Save an upcoming/future game to the upcoming_games table
        This table can be cleaned up without affecting historical statistics
        
        Args:
            game_data: Game data from API (can be minimal or complete)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            conn = self.get_connection()
            
            # Handle different API response structures
            if "data" in game_data and isinstance(game_data["data"], dict):
                data = game_data["data"]
                game = data.get("game", data)
            elif "game" in game_data:
                game = game_data["game"]
            else:
                game = game_data
            
            game_id = game.get("id")
            if not game_id:
                return False
            
            # Extract team info
            home_team = game.get("homeTeam", {})
            away_team = game.get("awayTeam", {})
            
            # Extract league/season info
            season = game.get("season", {})
            league = season.get("league", {})
            country = league.get("country", {})
            
            # Extract venue
            venue = game.get("venue", {})
            
            # Insert/update in upcoming_games table
            conn.execute("""
                INSERT OR REPLACE INTO upcoming_games (
                    id, flash_id, date, date_utc, status, status_name,
                    elapsed, extra_minutes,
                    home_result, away_result, home_ht_result, away_ht_result,
                    home_ft_result, away_ft_result,
                    home_team_id, home_team_name,
                    away_team_id, away_team_name,
                    league_id, league_name, country_code, country_name,
                    season_uid, season_year, round_name,
                    venue_name, venue_city, referee_name,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE((SELECT created_at FROM upcoming_games WHERE id = ?), CURRENT_TIMESTAMP), CURRENT_TIMESTAMP)
            """, (
                game_id,
                game.get("flashId"),
                game.get("date"),
                game.get("dateUtc"),
                game.get("status"),
                game.get("statusName"),
                game.get("elapsed"),
                game.get("extraMinutes"),
                game.get("homeResult"),
                game.get("awayResult"),
                game.get("homeHTResult"),
                game.get("awayHTResult"),
                game.get("homeFTResult"),
                game.get("awayFTResult"),
                home_team.get("id") if isinstance(home_team, dict) else None,
                home_team.get("name") if isinstance(home_team, dict) else str(home_team) if home_team else None,
                away_team.get("id") if isinstance(away_team, dict) else None,
                away_team.get("name") if isinstance(away_team, dict) else str(away_team) if away_team else None,
                league.get("id"),
                league.get("name"),
                country.get("code"),
                country.get("name"),
                season.get("uid"),
                season.get("year"),
                game.get("roundName"),
                venue.get("name"),
                venue.get("city"),
                game.get("refereeName"),
                game_id  # For COALESCE in created_at
            ))
            
            conn.commit()
            return True
            
        except Exception as e:
            import traceback
            print(f"Error saving upcoming game {game_id if 'game_id' in locals() else 'unknown'}: {e}")
            traceback.print_exc()
            if conn:
                conn.rollback()
            return False
    
    def upsert_odds_markets(
        self,
        game_id: int,
        markets: Any,
        *,
        as_opening: bool = False,
    ) -> int:
        """Merge Odds-Märkte in game_odds.

        as_opening=False → schreibt Closing in ``value`` (opening_value bleibt).
        as_opening=True  → schreibt Opening in ``opening_value`` (value bleibt).

        ``markets``: Liste wie in der API unter bookmaker.odds:
        [{marketId, marketName, odds: [{name, value}, ...]}, ...]
        """
        if not markets or not isinstance(markets, list):
            return 0
        conn = self.get_connection()
        n = 0
        for market in markets:
            if not isinstance(market, dict):
                continue
            mid = market.get("marketId")
            mname = market.get("marketName")
            for odd in market.get("odds") or []:
                if not isinstance(odd, dict):
                    continue
                name = odd.get("name")
                val = odd.get("value")
                if name is None or val is None:
                    continue
                try:
                    val_f = float(val)
                except (TypeError, ValueError):
                    continue
                row = conn.execute(
                    """
                    SELECT value, opening_value FROM game_odds
                    WHERE game_id = ? AND market_id IS ? AND name = ?
                    """,
                    (game_id, mid, name),
                ).fetchone()
                if row:
                    if as_opening:
                        conn.execute(
                            """
                            UPDATE game_odds SET opening_value = ?, market_name = COALESCE(?, market_name)
                            WHERE game_id = ? AND market_id IS ? AND name = ?
                            """,
                            (val_f, mname, game_id, mid, name),
                        )
                    else:
                        conn.execute(
                            """
                            UPDATE game_odds SET value = ?, market_name = COALESCE(?, market_name)
                            WHERE game_id = ? AND market_id IS ? AND name = ?
                            """,
                            (val_f, mname, game_id, mid, name),
                        )
                else:
                    conn.execute(
                        """
                        INSERT INTO game_odds (
                            game_id, market_id, market_name, name, value, opening_value
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            game_id,
                            mid,
                            mname,
                            name,
                            None if as_opening else val_f,
                            val_f if as_opening else None,
                        ),
                    )
                n += 1
        conn.commit()
        return n

    def save_glicko(self, game_id: int, glicko_data: Dict[str, Any]) -> bool:
        """Save Glicko ratings and predictions for a game
        
        Args:
            game_id: Game ID
            glicko_data: Glicko data from API (from /Games/glicko/{id} endpoint)
                Expected format: {"status": "OK", "data": {"glicko": {...}}} or {"glicko": {...}}
                
        Returns:
            True if successful, False otherwise
        """
        try:
            conn = self.get_connection()
            
            # Handle API response structure
            # API can return: {"data": {"glicko": {...}}} or {"glicko": {...}} or just {...}
            if isinstance(glicko_data, dict):
                if "data" in glicko_data and isinstance(glicko_data["data"], dict):
                    # Format: {"data": {"glicko": {...}}}
                    glicko = glicko_data["data"].get("glicko", {})
                elif "glicko" in glicko_data:
                    # Format: {"glicko": {...}}
                    glicko = glicko_data["glicko"]
                else:
                    # Format: direct glicko object
                    glicko = glicko_data
            else:
                glicko = {}
            
            if not glicko or not isinstance(glicko, dict):
                return False
            
            # Calculate draw probability
            home_win_prob = glicko.get("homeWinProbability")
            away_win_prob = glicko.get("awayWinProbability")
            draw_prob = None
            if home_win_prob is not None and away_win_prob is not None:
                draw_prob = max(0.0, 1.0 - home_win_prob - away_win_prob)
            
            # Insert or replace Glicko data
            conn.execute("""
                INSERT OR REPLACE INTO game_glicko (
                    game_id,
                    home_rating, home_rd, home_volatility,
                    away_rating, away_rd, away_volatility,
                    home_xg, away_xg,
                    home_win_probability, away_win_probability, draw_probability,
                    updated, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                game_id,
                glicko.get("homeRating"),
                glicko.get("homeRd"),
                glicko.get("homeVolatility"),
                glicko.get("awayRating"),
                glicko.get("awayRd"),
                glicko.get("awayVolatility"),
                glicko.get("homeXg"),
                glicko.get("awayXg"),
                home_win_prob,
                away_win_prob,
                draw_prob,
                glicko.get("updated"),
                datetime.now().isoformat()
            ))
            
            conn.commit()
            return True
            
        except Exception as e:
            print(f"Error saving Glicko data for game {game_id}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def save_profits(self, game_id: int, profits_data: Dict[str, Any]) -> bool:
        """Save profit data for a game
        
        Args:
            game_id: Game ID
            profits_data: Profit data from API (from /Games/profits endpoint)
                Expected format: {"status": "OK", "data": {"home": [...], "away": [...], ...}}
                
        Returns:
            True if successful, False otherwise
        """
        try:
            conn = self.get_connection()
            
            # Handle API response structure
            if isinstance(profits_data, dict):
                if "data" in profits_data and isinstance(profits_data["data"], dict):
                    data = profits_data["data"]
                else:
                    data = profits_data
            else:
                return False
            
            # Team types to process
            team_types = ["home", "away", "homeFirstHalf", "awayFirstHalf", "homeSecondHalf", "awaySecondHalf"]
            
            # Delete existing profits for this game first
            conn.execute("DELETE FROM game_profits WHERE game_id = ?", (game_id,))
            conn.commit()  # Commit the delete before inserting
            
            saved_count = 0
            
            # Process each team type
            for team_type in team_types:
                markets = data.get(team_type, [])
                if not isinstance(markets, list):
                    continue
                
                for market_data in markets:
                    market_name = market_data.get("market", "")
                    outcomes = market_data.get("outcomes", [])
                    
                    if not isinstance(outcomes, list):
                        continue
                    
                    for outcome in outcomes:
                        outcome_name = outcome.get("name", "")
                        profit = outcome.get("profit")
                        profit_history = outcome.get("profitHistory", [])
                        games_count = outcome.get("gamesCount")
                        win_count = outcome.get("winCount")
                        
                        # Store profit_history as JSON
                        profit_history_json = json.dumps(profit_history) if profit_history else None
                        
                        # Insert or replace profit data (to handle duplicates)
                        conn.execute("""
                            INSERT OR REPLACE INTO game_profits (
                                game_id, team_type, market, outcome_name,
                                profit, profit_history, games_count, win_count
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            game_id,
                            team_type,
                            market_name,
                            outcome_name,
                            profit,
                            profit_history_json,
                            games_count,
                            win_count
                        ))
                        saved_count += 1
            
            conn.commit()
            return saved_count > 0
            
        except Exception as e:
            print(f"Error saving profit data for game {game_id}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def get_game(self, game_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve a game from database (games or upcoming_games)."""
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()
        if row:
            return dict(row)
        row = conn.execute("SELECT * FROM upcoming_games WHERE id = ?", (game_id,)).fetchone()
        if row:
            return dict(row)
        return None
    
    def get_games_by_league(self, league_id: int, year: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get all games for a league, optionally filtered by year"""
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        if year:
            rows = conn.execute("""
                SELECT * FROM games 
                WHERE league_id = ? AND season_year = ? AND status IN (7, 8, 9, 10)
                ORDER BY date DESC
            """, (league_id, year)).fetchall()
        else:
            rows = conn.execute("""
                SELECT * FROM games 
                WHERE league_id = ? AND status IN (7, 8, 9, 10)
                ORDER BY date DESC
            """, (league_id,)).fetchall()
        return [dict(row) for row in rows]
    
    def get_database_size(self) -> Dict[str, Any]:
        """Get database size information"""
        conn = self.get_connection()
        db_size = self.db_path.stat().st_size if self.db_path.exists() else 0
        
        # Get row counts
        game_count = conn.execute("SELECT COUNT(*) FROM games").fetchone()[0]
        stats_count = conn.execute("SELECT COUNT(*) FROM game_statistics").fetchone()[0]
        events_count = conn.execute("SELECT COUNT(*) FROM game_events").fetchone()[0]
        
        return {
            "file_size_mb": round(db_size / (1024 * 1024), 2),
            "games": game_count,
            "statistics": stats_count,
            "events": events_count,
            "avg_size_per_game_mb": round(db_size / (1024 * 1024) / max(game_count, 1), 4)
        }
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            self.conn = None


