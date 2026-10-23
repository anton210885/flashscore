"""Tkinter based main window with tabs.

Provides a `run_gui()` entrypoint which starts a simple UI showing Live
matches (refreshing periodically) and a placeholder Analytics tab.
"""
import tkinter as tk
from tkinter import ttk
from typing import Optional
import sqlite3

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from config import config as cfg
from api.sstats_client import SStatsClient
from services.live_service import LiveService
from ui.tabs.analytics_tab import AnalyticsTab
from ui.tabs.leagues_hub_tab import LeaguesHubTab
from ui.tabs.database_tab import DatabaseTab
from ui.tabs.world_cup_tab import WorldCupTab
from ui.tabs.strategy_tab import StrategyTab
from services.analytics_service import AnalyticsService


class MainWindow:
    def __init__(self, root: tk.Tk, refresh_seconds: int = 60):
        self.root = root
        self.refresh_seconds = refresh_seconds * 1000
        self.client = SStatsClient(base_url=cfg.BASE_URL, api_key=getattr(cfg, 'API_KEY', None))
        self.live_service = LiveService(self.client)
        from services.glicko_service import GlickoService
        self.glicko_service = GlickoService(self.client)
        self.analytics_service = AnalyticsService(self.client)
        # Live-Spiele werden nicht mehr angezeigt um Einfrieren zu verhindern
        
        # Cache for odds - load only once per game
        self.odds_cache = {}  # game_id -> (odd_home, odd_draw, odd_away, odd_over, odd_under)
        
        # Initialize database manager for odds
        try:
            from database import DatabaseManager
            self.db_manager = DatabaseManager("data/flashscore.db")
        except Exception as e:
            print(f"[WARNING] Could not initialize database manager: {e}")
            self.db_manager = None
        
        # Allowed countries for filtering
        self.allowed_countries = ["Australia", "Italy", "England", "Scotland", "Great Britain", "United Kingdom", "Turkey", "Greece", "Switzerland", "Austria"]
        
        # Allowed leagues for England (Great Britain)
        self.allowed_england_leagues = [
            "Premier League",
            "Championship", 
            "League One",
            "League Two"
        ]
        
        # Allowed leagues for Scotland
        self.allowed_scotland_leagues = [
            "Premiership",
            "Championship"
        ]
        
        # Allowed leagues for Turkey
        self.allowed_turkey_leagues = [
            "Süper Lig",
            "1. Lig"
        ]
        
        # Allowed leagues for Greece
        self.allowed_greece_leagues = [
            "Super League 1"
        ]
        
        # Allowed leagues for Switzerland
        self.allowed_switzerland_leagues = [
            "Super League",
            "Challenge League"
        ]
        
        # Allowed leagues for Austria
        self.allowed_austria_leagues = [
            "Bundesliga",
            "2. Liga"
        ]
        
        # Track if we've loaded games from API (only once)
        self.api_games_loaded = False
        # Track if odds have been loaded for current games (to avoid reloading on refresh)
        self.odds_auto_loaded = False
        
        # Clean up finished games from upcoming_games table on startup
        # This moves finished games to 'games' table and removes them from 'upcoming_games'
        # The 'games' table is never cleaned up automatically to preserve historical statistics
        self._cleanup_finished_games()
        
        self._build()
    
    def _cleanup_finished_games(self):
        """Remove finished games from upcoming_games table on startup
        The 'games' table is for historical data and should never be cleaned up automatically
        """
        if not self.db_manager:
            return
        
        try:
            import sqlite3
            conn = self.db_manager.get_connection()
            # Delete finished games from upcoming_games table only
            # Also move finished games from upcoming_games to games table before deleting
            finished_games = conn.execute("""
                SELECT * FROM upcoming_games 
                WHERE status IN (7, 8, 9, 10) 
                   OR (home_ft_result IS NOT NULL AND away_ft_result IS NOT NULL AND status NOT IN (0, 1, 2, 3, 4, 5, 6, 11, 19))
            """).fetchall()
            
            # Move finished games to games table before deleting
            if finished_games:
                for row in finished_games:
                    # Check if already exists in games table
                    existing = conn.execute("SELECT id FROM games WHERE id = ?", (row[0],)).fetchone()
                    if not existing:
                        # Insert into games table (minimal data, full details can be loaded later if needed)
                        conn.execute("""
                            INSERT OR IGNORE INTO games (
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
                            ) SELECT 
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
                            FROM upcoming_games WHERE id = ?
                        """, (row[0],))
            
            # Now delete finished games from upcoming_games
            deleted = conn.execute("""
                DELETE FROM upcoming_games 
                WHERE status IN (7, 8, 9, 10) 
                   OR (home_ft_result IS NOT NULL AND away_ft_result IS NOT NULL AND status NOT IN (0, 1, 2, 3, 4, 5, 6, 11, 19))
            """).rowcount
            conn.commit()
            if deleted > 0:
                print(f"[INFO] Cleaned up {deleted} finished games from upcoming_games table (moved to games table for history)")
        except Exception as e:
            print(f"[WARNING] Error cleaning up finished games: {e}")
    
    def _build(self):
        self.root.title('FlashscoreTool')
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True)

        # Live tab (Treeview for selectable rows)
        self.live_frame = ttk.Frame(self.notebook)
        cols = ("id", "country", "league", "home", "away", "score", "status", 
                "odd_home", "odd_draw", "odd_away", "odd_over", "odd_under",
                "profit_home", "profit_draw", "profit_away")
        self.tree = ttk.Treeview(self.live_frame, columns=cols, show='headings', height=20)
        self.tree.heading('id', text='ID')
        self.tree.heading('country', text='Country')
        self.tree.heading('league', text='League')
        self.tree.heading('home', text='Home')
        self.tree.heading('away', text='Away')
        self.tree.heading('score', text='Score')
        self.tree.heading('status', text='Status')
        self.tree.heading('odd_home', text='Odds H')
        self.tree.heading('odd_draw', text='Odds D')
        self.tree.heading('odd_away', text='Odds A')
        self.tree.heading('odd_over', text='Odds O2.5')
        self.tree.heading('odd_under', text='Odds U2.5')
        self.tree.heading('profit_home', text='Profit H')
        self.tree.heading('profit_draw', text='Profit D')
        self.tree.heading('profit_away', text='Profit A')
        self.tree.column('id', width=60, anchor='center')
        self.tree.column('country', width=90)
        self.tree.column('league', width=130)
        self.tree.column('home', width=110)
        self.tree.column('away', width=110)
        self.tree.column('score', width=60, anchor='center')
        self.tree.column('status', width=70, anchor='center')
        self.tree.column('odd_home', width=60, anchor='center')
        self.tree.column('odd_draw', width=60, anchor='center')
        self.tree.column('odd_away', width=60, anchor='center')
        self.tree.column('odd_over', width=70, anchor='center')
        self.tree.column('odd_under', width=70, anchor='center')
        self.tree.column('profit_home', width=70, anchor='center')
        self.tree.column('profit_draw', width=70, anchor='center')
        self.tree.column('profit_away', width=70, anchor='center')
        
        # Add scrollbars
        scrollbar_y = ttk.Scrollbar(self.live_frame, orient='vertical', command=self.tree.yview)
        scrollbar_x = ttk.Scrollbar(self.live_frame, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)
        
        # Pack tree and scrollbars
        self.tree.pack(side='left', fill='both', expand=True)
        scrollbar_y.pack(side='right', fill='y')
        scrollbar_x.pack(side='bottom', fill='x')

        # Bind double-click to load analytics
        self.tree.bind("<Double-1>", self._on_tree_double_click)
        
        # Context menu for right-click
        self.context_menu = tk.Menu(self.tree, tearoff=0)
        self.context_menu.add_command(label="ID kopieren", command=self._copy_match_id)
        self.context_menu.add_command(label="Analytics laden", command=self._load_analytics_for_selected)
        self.tree.bind("<Button-3>", self._show_context_menu)

        # Configure row colors
        self.tree.tag_configure('live', background='lightblue')
        self.tree.tag_configure('finished', background='lightsalmon')
        
        # Configure style for profit columns
        # Since Treeview doesn't support individual cell coloring,
        # we'll use visual indicators (green text/symbols) for positive values
        style = ttk.Style()
        
        # Create custom tags for profit columns with green text
        # Note: We'll apply these via item tags, but they affect the whole row
        # So we'll use a workaround: format the values with visual indicators
        
        # Tags for profit columns (positive = green background)
        # Note: Tkinter Treeview doesn't support individual cell coloring,
        # so we'll use a workaround with custom styling
        self.tree.tag_configure('profit_positive_home', background='#90EE90')  # Light green
        self.tree.tag_configure('profit_positive_draw', background='#90EE90')
        self.tree.tag_configure('profit_positive_away', background='#90EE90')
        self.tree.tag_configure('profit_negative', background='#FFB6C1')  # Light pink for negative

        # Right-side controls
        ctrl = ttk.Frame(self.live_frame)
        ctrl.pack(fill='y', side='right', padx=6, pady=6)
        self.btn_refresh = ttk.Button(ctrl, text='Refresh', command=self._refresh)
        self.btn_refresh.pack(fill='x', pady=4)
        # Live-Spiele Checkbox entfernt - Live-Spiele werden nicht mehr angezeigt um Einfrieren zu verhindern
        self.btn_update_odds = ttk.Button(ctrl, text='📊 Quoten aktualisieren', command=self._update_odds_for_all_games)
        self.btn_update_odds.pack(fill='x', pady=4)
        self.btn_glicko = ttk.Button(ctrl, text='Show Glicko', command=self._show_selected_glicko)
        self.btn_glicko.pack(fill='x', pady=4)

        self.notebook.add(self.live_frame, text='Today\'s Matches 📅')

        # Analytics tab
        self.analytics_tab = AnalyticsTab(self.notebook, services={'live_service': self.live_service, 'glicko_service': self.glicko_service, 'analytics_service': self.analytics_service, 'client': self.client})
        self.notebook.add(self.analytics_tab, text='Analytics 📊')

        # Ligen-Hub: Meisterschaften (26/27) · Liga 128 (Kalender 2026) · European
        self.leagues_hub = LeaguesHubTab(self.notebook, services={'client': self.client})
        self.notebook.add(self.leagues_hub, text='Ligen 🏆')
        self.league_tab = self.leagues_hub.meisterschaften_tab
        self.league_128_tab = self.leagues_hub.liga128_tab
        self.european_tab = self.leagues_hub.european_tab

        # World Cup tab (league_id=1)
        self.world_cup_tab = WorldCupTab(self.notebook, services={'client': self.client})
        self.notebook.add(self.world_cup_tab, text='WM 🌍')

        # Database tab
        self.database_tab = DatabaseTab(
            self.notebook,
            services={
                "client": self.client,
                "league_tab": self.league_tab,
                "league_128_tab": self.league_128_tab,
            },
        )
        self.notebook.add(self.database_tab, text='Database 💾')
        
        # Strategy tab
        self.strategy_tab = StrategyTab(self.notebook, services={
            'client': self.client,
            'db_manager': self.db_manager,
            'live_service': self.live_service,
            'analytics_tab': self.analytics_tab,
            'main_notebook': self.notebook,
        })
        self.notebook.add(self.strategy_tab, text='Strategie 🎯')

    def _get_tag(self, status_num):
        try:
            s = int(status_num)
            if s in {3, 4, 5, 6, 7, 11, 19}:
                return 'live'
            elif s in {8, 9, 10}:
                return 'finished'
        except ValueError:
            pass
        return ''

    def start_refresh(self):
        self._refresh()

    def _refresh(self):
        try:
            # Load Serie A (135), Serie B (136), Turkey Süper Lig (203), and Turkey 1. Lig (204) from upcoming_games table
            db_games = []
            if self.db_manager:
                try:
                    import sqlite3
                    conn = self.db_manager.get_connection()
                    conn.row_factory = sqlite3.Row
                    
                    # Get only NOT STARTED games (no live games to reduce API load and freezing)
                    # Status: 0=Unknown/Upcoming, 1=Not Started, 2=Scheduled
                    # EXCLUDE Live games: 3=First Half, 4=Half Time, 5=Second Half, 6=Extra Time, 11=Live, 19=Live
                    rows = conn.execute("""
                        SELECT id, date, status, status_name, 
                               home_team_name, away_team_name,
                               home_ft_result, away_ft_result,
                               country_name, league_name, league_id
                        FROM upcoming_games 
                        WHERE (status IN (0, 1, 2) OR status IS NULL)
                        ORDER BY date DESC
                        LIMIT 50
                    """).fetchall()
                    
                    for row in rows:
                        # Convert to dict-like object for compatibility
                        game_dict = {
                            'id': row['id'],
                            'country': row['country_name'],
                            'league_name': row['league_name'],
                            'league_id': row['league_id'],
                            'home_team': row['home_team_name'],
                            'away_team': row['away_team_name'],
                            'status': row['status'],
                            'status_text': row['status_name'],
                            'score_home': row['home_ft_result'] if row['home_ft_result'] is not None else 0,
                            'score_away': row['away_ft_result'] if row['away_ft_result'] is not None else 0,
                            'from_db': True  # Mark as from database
                        }
                        db_games.append(game_dict)
                    
                    # Don't close the connection - it's managed by DatabaseManager
                    # conn.close()  # Removed - connection is persistent
                except Exception as e:
                    print(f"[WARNING] Error loading games from DB: {e}")
            
            # Load other games from API - only once, then use DB
            api_games = []
            if not self.api_games_loaded:
                print("[INFO] Loading games from API (first time only)...")
                api_games = self.live_service.fetch_live_games()
                self.api_games_loaded = True
                print(f"[INFO] Loaded {len(list(api_games))} games from API")
            else:
                # After first load, get upcoming games from DB
                print("[INFO] Using games from database (API already loaded)")
                try:
                    import sqlite3
                    conn = self.db_manager.get_connection()
                    conn.row_factory = sqlite3.Row
                    rows = conn.execute("""
                        SELECT id, date, status, status_name, 
                               home_team_name, away_team_name,
                               home_ft_result, away_ft_result,
                               country_name, league_name, league_id
                        FROM games 
                        WHERE (status IN (0, 1, 2) OR status IS NULL)
                          AND (home_ft_result IS NULL OR away_ft_result IS NULL)
                        ORDER BY date DESC
                        LIMIT 50
                    """).fetchall()
                    
                    for row in rows:
                        game_dict = {
                            'id': row['id'],
                            'country': row['country_name'],
                            'league_name': row['league_name'],
                            'league_id': row['league_id'],
                            'home_team': row['home_team_name'],
                            'away_team': row['away_team_name'],
                            'status': row['status'],
                            'status_text': row['status_name'],
                            'score_home': row['home_ft_result'] if row['home_ft_result'] is not None else 0,
                            'score_away': row['away_ft_result'] if row['away_ft_result'] is not None else 0,
                            'from_db': True
                        }
                        api_games.append(game_dict)
                    print(f"[INFO] Loaded {len(api_games)} upcoming games from database")
                except Exception as e:
                    print(f"[WARNING] Error loading games from DB: {e}")
            
            # Combine games (DB games first, then API games)
            all_games = db_games + list(api_games)
            print(f"[DEBUG] Live Tab: {len(db_games)} Spiele aus DB, {len(list(api_games))} Spiele aus API, Gesamt: {len(all_games)}")
            
            # Show ALL games - no country/league filtering
            # All games from database are already filtered by status (only live/upcoming)
            games = all_games
            print(f"[DEBUG] Live Tab: Alle Spiele (keine Filterung): {len(games)} Spiele")
            
            # Filter: Only show games that are NOT STARTED (NO live games to prevent freezing)
            # Status: 0=Unknown/Upcoming, 1=Not Started, 2=Scheduled
            # EXCLUDE all live games: 3=First Half, 4=Half Time, 5=Second Half, 6=Extra Time, 11=Live, 19=Live
            # EXCLUDE finished: 7=Finished, 8=Postponed, 9=Cancelled, etc.
            not_started_statuses = {0, 1, 2}
            finished_statuses = {7, 8, 9, 10, 12, 13, 14, 15, 16, 17, 18, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30}
            live_statuses = {3, 4, 5, 6, 11, 19}  # Live games - EXCLUDED
            filtered_by_status = []
            for g in games:
                status_num = getattr(g, 'status', None) or (g.get('status') if isinstance(g, dict) else 0)
                try:
                    status_int = int(status_num) if status_num is not None else 0
                    # Only include if status is "Not Started" and NOT live and NOT finished
                    if status_int in not_started_statuses and status_int not in live_statuses and status_int not in finished_statuses:
                        filtered_by_status.append(g)
                except (ValueError, TypeError):
                    # If status can't be converted, only include if it's None (might be upcoming)
                    if status_num is None:
                        filtered_by_status.append(g)
            games = filtered_by_status
            print(f"[DEBUG] Live Tab: Nach Status-Filterung: {len(games)} Spiele")
            
            # populate tree
            for i in self.tree.get_children():
                self.tree.delete(i)
            
            inserted_count = 0
            for g in games:
                # Handle both dict (from DB) and object (from API) formats
                if isinstance(g, dict):
                    gid = g.get('id')
                    country = g.get('country') or g.get('country_name', '')
                    league = g.get('league_name', '')
                    home = g.get('home_team') or g.get('home_team_name', '')
                    away = g.get('away_team') or g.get('away_team_name', '')
                else:
                    gid = getattr(g, 'id', None)
                    country = getattr(g, 'country', None) or ''
                    league = getattr(g, 'league_name', None) or ''
                    home = getattr(g, 'home_team', None) or ''
                    away = getattr(g, 'away_team', None) or ''
                
                if not gid:
                    print(f"[DEBUG] Live Tab: Spiel ohne ID übersprungen: {home} vs {away}")
                    continue
                
                gid_str = str(gid)
                
                # Get scores - prefer current scores, fallback to FT result
                if isinstance(g, dict):
                    sh = g.get('score_home') or g.get('home_ft_result', 0)
                    sa = g.get('score_away') or g.get('away_ft_result', 0)
                    status_num = g.get('status', '')
                    status_text = g.get('status_text') or g.get('status_name') or str(status_num)
                else:
                    sh = getattr(g, 'score_home', None) or getattr(g, 'home_ft_result', 0) or 0
                    sa = getattr(g, 'score_away', None) or getattr(g, 'away_ft_result', 0) or 0
                    status_num = getattr(g, 'status', None) or ''
                    status_text = getattr(g, 'status_text', None) or str(status_num)
                
                if sh is None:
                    sh = 0
                if sa is None:
                    sa = 0
                score = f"{sh}-{sa}"
                tag = self._get_tag(status_num)
                
                # Get odds - only load once, then use cache (skip API calls to prevent freezing)
                # Only use cached odds or database odds, no new API calls during refresh
                if gid_str not in self.odds_cache:
                    # Try to get from database first (fast, no API call)
                    try:
                        game_id_int = int(gid)
                        if self.db_manager:
                            conn = self.db_manager.get_connection()
                            conn.row_factory = sqlite3.Row
                            row = conn.execute(
                                "SELECT odd_home, odd_draw, odd_away, odd_over_25, odd_under_25 FROM game_odds_pivoted WHERE game_id = ?",
                                (game_id_int,)
                            ).fetchone()
                            if row:
                                odd_home = f"{row['odd_home']:.2f}" if row['odd_home'] is not None else ""
                                odd_draw = f"{row['odd_draw']:.2f}" if row['odd_draw'] is not None else ""
                                odd_away = f"{row['odd_away']:.2f}" if row['odd_away'] is not None else ""
                                odd_over = f"{row['odd_over_25']:.2f}" if row['odd_over_25'] is not None else ""
                                odd_under = f"{row['odd_under_25']:.2f}" if row['odd_under_25'] is not None else ""
                                self.odds_cache[gid_str] = (odd_home, odd_draw, odd_away, odd_over, odd_under)
                            else:
                                # No odds in DB - use empty values (don't call API during refresh to prevent freezing)
                                self.odds_cache[gid_str] = ("", "", "", "", "")
                        else:
                            self.odds_cache[gid_str] = ("", "", "", "", "")
                    except Exception:
                        self.odds_cache[gid_str] = ("", "", "", "", "")
                
                odd_home, odd_draw, odd_away, odd_over, odd_under = self.odds_cache[gid_str]
                
                # Get profit from database only (no API calls during refresh to prevent freezing)
                profit_home, profit_draw, profit_away = "", "", ""
                try:
                    game_id_int = int(gid)
                    if self.db_manager:
                        conn = self.db_manager.get_connection()
                        conn.row_factory = sqlite3.Row
                        profit_home_row = conn.execute(
                            "SELECT profit FROM game_profits WHERE game_id = ? AND team_type = 'home' AND market = 'Match Winner' AND outcome_name = 'Win' LIMIT 1",
                            (game_id_int,)
                        ).fetchone()
                        profit_draw_row = conn.execute(
                            "SELECT profit FROM game_profits WHERE game_id = ? AND team_type = 'home' AND market = 'Match Winner' AND outcome_name = 'Draw' LIMIT 1",
                            (game_id_int,)
                        ).fetchone()
                        profit_away_row = conn.execute(
                            "SELECT profit FROM game_profits WHERE game_id = ? AND team_type = 'home' AND market = 'Match Winner' AND outcome_name = 'Lose' LIMIT 1",
                            (game_id_int,)
                        ).fetchone()
                        
                        if profit_home_row:
                            p = profit_home_row[0]
                            profit_home = f"● {p:+.2f}" if p > 0 else f"{p:.2f}"
                        if profit_draw_row:
                            p = profit_draw_row[0]
                            profit_draw = f"● {p:+.2f}" if p > 0 else f"{p:.2f}"
                        if profit_away_row:
                            p = profit_away_row[0]
                            profit_away = f"● {p:+.2f}" if p > 0 else f"{p:.2f}"
                except Exception:
                    pass
                
                # Save game to database if not already saved (only for API games, not DB games)
                if not isinstance(g, dict) or not g.get('from_db'):
                    # This is an API game - save it to DB
                    try:
                        # Convert game object to dict format for saving
                        game_data = {
                            'id': gid,
                            'country': country,
                            'league_name': league,
                            'home_team': home,
                            'away_team': away,
                            'status': status_num,
                            'statusName': status_text,
                            'homeResult': sh,
                            'awayResult': sa,
                            'homeFTResult': sh,
                            'awayFTResult': sa,
                        }
                        # Try to get full game data from API if available
                        if hasattr(g, '__dict__'):
                            game_data.update(g.__dict__)
                        elif isinstance(g, dict):
                            game_data.update(g)
                        
                        # Save to upcoming_games table (for future/upcoming games)
                        if self.db_manager:
                            # Check if game already exists in upcoming_games
                            conn = self.db_manager.get_connection()
                            existing = conn.execute("SELECT id FROM upcoming_games WHERE id = ?", (gid,)).fetchone()
                            if not existing:
                                # Save minimal game data to upcoming_games - full details will be loaded later if needed
                                from datetime import datetime
                                conn.execute("""
                                    INSERT OR REPLACE INTO upcoming_games (
                                        id, date, status, status_name,
                                        home_team_name, away_team_name,
                                        home_ft_result, away_ft_result,
                                        country_name, league_name, league_id,
                                        created_at, updated_at
                                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                                """, (
                                    gid,
                                    game_data.get('date') or datetime.now().isoformat(),
                                    status_num,
                                    status_text,
                                    home,
                                    away,
                                    sh if sh else None,
                                    sa if sa else None,
                                    country,
                                    league,
                                    game_data.get('league_id'),
                                ))
                                conn.commit()
                                print(f"[DEBUG] Saved upcoming game {gid} to upcoming_games table")
                    except Exception as e:
                        print(f"[WARNING] Error saving game {gid} to database: {e}")
                
                # Update existing row if it exists (for live score updates), otherwise insert new
                if self.tree.exists(gid_str):
                    # Update only score (index 5) and status (index 6), keep odds unchanged
                    current_values = list(self.tree.item(gid_str, "values"))
                    current_values[5] = score
                    current_values[6] = status_text
                    self.tree.item(gid_str, values=current_values, tags=(tag,))
                else:
                    # Insert new row (profit values already have visual indicators for positive values)
                    self.tree.insert('', 'end', iid=gid_str, 
                                   values=(gid, country, league, home, away, score, status_text,
                                          odd_home, odd_draw, odd_away, odd_over, odd_under,
                                          profit_home, profit_draw, profit_away), 
                                   tags=(tag,))
                    inserted_count += 1
            
            print(f"[DEBUG] Live Tab: {inserted_count} Spiele in Tabelle eingefügt")
            
            # Auto-load odds for new games if not already loaded (only once, not on every refresh)
            if not self.odds_auto_loaded and inserted_count > 0:
                self.odds_auto_loaded = True
                # Load odds in background thread after a short delay
                def auto_load_odds():
                    import time
                    time.sleep(1)  # Wait 1 second for UI to settle
                    self._update_odds_for_all_games_silent()
                import threading
                thread = threading.Thread(target=auto_load_odds, daemon=True)
                thread.start()
                
        except Exception as e:
            # show error in a simple popup
            try:
                from tkinter import messagebox
                messagebox.showerror('Error', f'Fehler beim Laden: {e}')
            except Exception:
                print('Fehler beim Laden:', e)
        finally:
            self.root.after(self.refresh_seconds, self._refresh)
    
    def _get_odds_from_api(self, game_id):
        """Get odds from database first, fallback to API if not found"""
        if not game_id:
            return "", "", "", "", ""
        
        try:
            game_id_int = int(game_id)
            
            # First try to get odds from database (using pivoted view)
            if self.db_manager:
                try:
                    conn = self.db_manager.get_connection()
                    conn.row_factory = sqlite3.Row
                    
                    # Get odds from pivoted view (much simpler!)
                    row = conn.execute(
                        "SELECT odd_home, odd_draw, odd_away, odd_over_25, odd_under_25 FROM game_odds_pivoted WHERE game_id = ?",
                        (game_id_int,)
                    ).fetchone()
                    
                    # If we have odds in DB, use them
                    if row:
                        odd_home = row['odd_home']
                        odd_draw = row['odd_draw']
                        odd_away = row['odd_away']
                        odd_over = row['odd_over_25']
                        odd_under = row['odd_under_25']
                        
                        odd_home_str = f"{odd_home:.2f}" if odd_home is not None else ""
                        odd_draw_str = f"{odd_draw:.2f}" if odd_draw is not None else ""
                        odd_away_str = f"{odd_away:.2f}" if odd_away is not None else ""
                        odd_over_str = f"{odd_over:.2f}" if odd_over is not None else ""
                        odd_under_str = f"{odd_under:.2f}" if odd_under is not None else ""
                        
                        return odd_home_str, odd_draw_str, odd_away_str, odd_over_str, odd_under_str
                except Exception as e:
                    print(f"[WARNING] Error loading odds from DB for game {game_id}: {e}")
            
            # Fallback to API if not in database
            odds_data = self.client.get_game_odds(game_id_int, bookmaker_id=None, opening=False)
            
            # Parse API response: {"status": "OK", "data": [{"bookmakerId": 1, "odds": [...]}]}
            odd_home = None
            odd_draw = None
            odd_away = None
            odd_over = None
            odd_under = None
            
            if odds_data and "data" in odds_data:
                bookmakers = odds_data["data"]
                if isinstance(bookmakers, list) and len(bookmakers) > 0:
                    # Use first bookmaker's odds
                    first_bookmaker = bookmakers[0]
                    markets = first_bookmaker.get("odds", [])
                    
                    for market in markets:
                        market_id = market.get("marketId")
                        market_name = market.get("marketName", "")
                        odds_list = market.get("odds", [])
                        
                        # Match Winner (market_id = 1 or marketName = "Match Winner" / "1X2")
                        if market_id == 1 or "Match Winner" in market_name or "1X2" in market_name:
                            for odd in odds_list:
                                name = odd.get("name", "")
                                value = odd.get("value")
                                if name == "Home":
                                    odd_home = value
                                elif name == "Draw":
                                    odd_draw = value
                                elif name == "Away":
                                    odd_away = value
                        
                        # Goals Over/Under - ONLY marketId 5, ONLY Over 2.5 and Under 2.5
                        elif market_id == 5:
                            # Only process marketId 5 (Goals Over/Under)
                            # Only extract "Over 2.5" and "Under 2.5", ignore all other Over/Under values
                            for odd in odds_list:
                                name = odd.get("name", "")
                                value = odd.get("value")
                                # Strictly match only "Over 2.5" and "Under 2.5"
                                if name == "Over 2.5":
                                    odd_over = value
                                elif name == "Under 2.5":
                                    odd_under = value
                                # Explicitly ignore all other Over/Under values (Over 1.5, Over 3.5, Under 1.5, etc.)
            
            # Format odds
            odd_home_str = f"{odd_home:.2f}" if odd_home is not None else ""
            odd_draw_str = f"{odd_draw:.2f}" if odd_draw is not None else ""
            odd_away_str = f"{odd_away:.2f}" if odd_away is not None else ""
            odd_over_str = f"{odd_over:.2f}" if odd_over is not None else ""
            odd_under_str = f"{odd_under:.2f}" if odd_under is not None else ""
            
            return odd_home_str, odd_draw_str, odd_away_str, odd_over_str, odd_under_str
            
        except Exception as e:
            print(f"[WARNING] Error loading odds from API for game {game_id}: {e}")
            return "", "", "", "", ""
    
    def _get_profit_from_api(self, game_id):
        """Get profit data from database first, fallback to API if not found"""
        if not game_id:
            return "", "", ""
        
        try:
            game_id_int = int(game_id)
            
            # First try to get profits from database
            if self.db_manager:
                try:
                    conn = self.db_manager.get_connection()
                    conn.row_factory = sqlite3.Row
                    
                    # Get profits from database (home team, Match Winner market)
                    profit_home_row = conn.execute(
                        "SELECT profit FROM game_profits WHERE game_id = ? AND team_type = 'home' AND market = 'Match Winner' AND outcome_name = 'Win' LIMIT 1",
                        (game_id_int,)
                    ).fetchone()
                    profit_draw_row = conn.execute(
                        "SELECT profit FROM game_profits WHERE game_id = ? AND team_type = 'home' AND market = 'Match Winner' AND outcome_name = 'Draw' LIMIT 1",
                        (game_id_int,)
                    ).fetchone()
                    profit_away_row = conn.execute(
                        "SELECT profit FROM game_profits WHERE game_id = ? AND team_type = 'home' AND market = 'Match Winner' AND outcome_name = 'Lose' LIMIT 1",
                        (game_id_int,)
                    ).fetchone()
                    
                    # If we have profit data in DB, use it
                    if profit_home_row or profit_draw_row or profit_away_row:
                        profit_home = profit_home_row[0] if profit_home_row else None
                        profit_draw = profit_draw_row[0] if profit_draw_row else None
                        profit_away = profit_away_row[0] if profit_away_row else None
                        
                        # Format profit with visual indicator for positive values
                        profit_home_str = ""
                        profit_draw_str = ""
                        profit_away_str = ""
                        
                        if profit_home is not None:
                            if profit_home > 0:
                                profit_home_str = f"● {profit_home:+.2f}"
                            else:
                                profit_home_str = f"{profit_home:.2f}"
                        
                        if profit_draw is not None:
                            if profit_draw > 0:
                                profit_draw_str = f"● {profit_draw:+.2f}"
                            else:
                                profit_draw_str = f"{profit_draw:.2f}"
                        
                        if profit_away is not None:
                            if profit_away > 0:
                                profit_away_str = f"● {profit_away:+.2f}"
                            else:
                                profit_away_str = f"{profit_away:.2f}"
                        
                        return profit_home_str, profit_draw_str, profit_away_str
                except Exception as e:
                    print(f"[WARNING] Error loading profits from DB for game {game_id}: {e}")
            
            # Fallback to API if not in database
            profit_data = self.client.get_game_profits(game_id_int, bookie_id=1, limit=25)
            
            # Parse API response: {"status": "OK", "data": {"home": [...], "away": [...]}}
            profit_home = None
            profit_draw = None
            profit_away = None
            
            if profit_data and "data" in profit_data:
                data = profit_data["data"]
                # Get home team Match Winner profits
                home_markets = data.get("home", [])
                if isinstance(home_markets, list):
                    for market in home_markets:
                        if market.get("market") == "Match Winner":
                            outcomes = market.get("outcomes", [])
                            for outcome in outcomes:
                                outcome_name = outcome.get("name", "")
                                profit = outcome.get("profit")
                                if outcome_name == "Win":
                                    profit_home = profit
                                elif outcome_name == "Draw":
                                    profit_draw = profit
                                elif outcome_name == "Lose":
                                    profit_away = profit
                            break  # Found Match Winner market, no need to continue
            
            # Format profit with visual indicator for positive values
            # Since Treeview doesn't support individual cell coloring,
            # we'll use a green circle symbol (●) for positive values
            profit_home_str = ""
            profit_draw_str = ""
            profit_away_str = ""
            
            if profit_home is not None:
                if profit_home > 0:
                    profit_home_str = f"● {profit_home:+.2f}"  # Green circle for positive
                else:
                    profit_home_str = f"{profit_home:.2f}"
            
            if profit_draw is not None:
                if profit_draw > 0:
                    profit_draw_str = f"● {profit_draw:+.2f}"  # Green circle for positive
                else:
                    profit_draw_str = f"{profit_draw:.2f}"
            
            if profit_away is not None:
                if profit_away > 0:
                    profit_away_str = f"● {profit_away:+.2f}"  # Green circle for positive
                else:
                    profit_away_str = f"{profit_away:.2f}"
            
            return profit_home_str, profit_draw_str, profit_away_str
            
        except Exception as e:
            print(f"[WARNING] Error loading profit from API for game {game_id}: {e}")
            return "", "", ""
    
    def _color_profit_cells(self, item_id):
        """Color individual profit cells green if positive using Canvas overlay"""
        # Since Tkinter Treeview doesn't support individual cell coloring,
        # we use a workaround: overlay colored rectangles on specific cells
        
        if item_id not in self.profit_cell_colors:
            return
        
        profit_colors = self.profit_cell_colors[item_id]
        
        # Get column positions
        # Column indices: profit_home=11, profit_draw=12, profit_away=13 (0-indexed from values tuple)
        profit_columns = {
            'profit_home': 11,
            'profit_draw': 12,
            'profit_away': 13
        }
        
        # Note: Direct cell coloring in Treeview is not possible without custom widget
        # The visual indicator (●) in the value is the best practical solution
        # For true cell coloring, we would need a Canvas-based custom widget
        
        # Alternative: We could modify the tree's item to use different tags per cell,
        # but Treeview only supports row-level tags
        
        # For now, the visual indicator approach (● symbol) is implemented
        # in _get_profit_from_api() which marks positive values with "● "

    def _show_selected_glicko(self):
        sel = self.tree.selection()
        if not sel:
            try:
                from tkinter import messagebox
                messagebox.showinfo('Info', 'Bitte ein Match auswählen')
            except Exception:
                print('Bitte ein Match auswählen')
            return
        game_id = sel[0]
        try:
            glicko_response = self.glicko_service.fetch_glicko(game_id)
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror('Fehler', f'Glicko Abruf fehlgeschlagen: {e}')
            return
        # Check if data exists
        if not glicko_response or 'glicko' not in glicko_response:
            from tkinter import messagebox
            messagebox.showinfo('Info', 'Keine Glicko-Daten für dieses Spiel verfügbar.')
            return
        glicko_data = glicko_response['glicko']
        print("Glicko data:", glicko_data)  # Debug
        home_rating = glicko_data.get('homeRating')
        away_rating = glicko_data.get('awayRating')
        home_prob = glicko_data.get('homeWinProbability')
        away_prob = glicko_data.get('awayWinProbability')
        home_xg = glicko_data.get('homeXg')
        away_xg = glicko_data.get('awayXg')
        if home_rating is None or away_rating is None:
            from tkinter import messagebox
            messagebox.showinfo('Info', 'Unvollständige Glicko-Daten.')
            return
        # Create graphical popup
        popup = tk.Toplevel(self.root)
        popup.title(f'Glicko - Game {game_id}')
        popup.geometry("800x600")
        # Create figure with subplots
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 6))
        teams = ['Home Team', 'Away Team']
        # Ratings
        ratings = [home_rating, away_rating]
        colors = ['blue', 'red']
        bars1 = ax1.bar(teams, ratings, color=colors, alpha=0.7)
        ax1.set_title('Glicko Ratings')
        ax1.set_ylabel('Rating')
        for i, (bar, prob) in enumerate(zip(bars1, [home_prob, away_prob])):
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2, height + 10, f'Win Prob: {prob:.1%}' if prob else 'N/A', ha='center', va='bottom')
        # xG
        if home_xg is not None and away_xg is not None:
            xg = [home_xg, away_xg]
            bars2 = ax2.bar(teams, xg, color=['lightblue', 'pink'], alpha=0.7)
            ax2.set_title('Expected Goals (xG)')
            ax2.set_ylabel('xG')
        else:
            ax2.text(0.5, 0.5, 'xG data not available', ha='center', va='center', transform=ax2.transAxes)
        plt.tight_layout()
        # Embed in Tkinter
        canvas = FigureCanvasTkAgg(fig, master=popup)
        canvas.draw()
        canvas.get_tk_widget().pack(fill='both', expand=True)

    def _on_tree_double_click(self, event):
        """Handle double-click on treeview to load analytics for selected match"""
        sel = self.tree.selection()
        if not sel:
            return
        game_id = sel[0]
        # Switch to analytics tab
        self.notebook.select(self.analytics_tab)
        # Load analytics for this match
        self.analytics_tab.load_match_by_id(game_id)

    def _show_context_menu(self, event):
        """Show context menu on right-click"""
        sel = self.tree.selection()
        if sel:
            self.context_menu.post(event.x_root, event.y_root)

    def _copy_match_id(self):
        """Copy the selected match ID to clipboard"""
        sel = self.tree.selection()
        if not sel:
            return
        game_id = sel[0]
        self.root.clipboard_clear()
        self.root.clipboard_append(str(game_id))
        # Optional: show a message
        try:
            from tkinter import messagebox
            messagebox.showinfo("Info", f"Match ID {game_id} kopiert")
        except:
            pass

    def _load_analytics_for_selected(self):
        """Load analytics for selected match"""
        sel = self.tree.selection()
        if not sel:
            return
        game_id = sel[0]
        self.notebook.select(self.analytics_tab)
        self.analytics_tab.load_match_by_id(game_id)
    
    def _update_odds_for_all_games_silent(self):
        """Update odds silently (no user notifications) - used for auto-loading"""
        import threading
        
        def update_odds_thread():
            try:
                # Get all game IDs from tree
                game_ids = []
                for item in self.tree.get_children():
                    item_values = self.tree.item(item, "values")
                    if item_values and len(item_values) > 0:
                        try:
                            game_id = int(item_values[0])
                            game_ids.append(game_id)
                        except (ValueError, TypeError):
                            continue
                
                if not game_ids:
                    return
                
                updated_count = 0
                for idx, game_id in enumerate(game_ids):
                    try:
                        # Skip if already in cache
                        if str(game_id) in self.odds_cache:
                            cached = self.odds_cache[str(game_id)]
                            # If cache has values, skip (already loaded)
                            if cached and any(cached):
                                continue
                        
                        # Load odds from API
                        odd_home, odd_draw, odd_away, odd_over, odd_under = self._get_odds_from_api(game_id)
                        
                        # Update cache
                        self.odds_cache[str(game_id)] = (odd_home, odd_draw, odd_away, odd_over, odd_under)
                        
                        # Update tree if game is still displayed
                        if self.tree.exists(str(game_id)):
                            current_values = list(self.tree.item(str(game_id), "values"))
                            if len(current_values) >= 14:
                                # Update odds columns (indices 7-11)
                                current_values[7] = odd_home
                                current_values[8] = odd_draw
                                current_values[9] = odd_away
                                current_values[10] = odd_over
                                current_values[11] = odd_under
                                current_tags = self.tree.item(str(game_id), "tags")
                                self.after(0, lambda vid=str(game_id), v=tuple(current_values), t=current_tags: 
                                          self.tree.item(vid, values=v, tags=t))
                        
                        updated_count += 1
                        
                        # Rate limiting
                        import time
                        time.sleep(0.5)  # 500ms delay between requests
                        
                    except Exception as e:
                        print(f"[WARNING] Error updating odds for game {game_id}: {e}")
                        continue
                
            except Exception as e:
                print(f"[WARNING] Error in auto-load odds: {e}")
        
        # Start update in background thread
        thread = threading.Thread(target=update_odds_thread, daemon=True)
        thread.start()
    
    def _update_odds_for_all_games(self):
        """Update odds for all currently displayed games (with user feedback)"""
        import threading
        
        def update_odds_thread():
            try:
                # Get all game IDs from tree
                game_ids = []
                for item in self.tree.get_children():
                    item_values = self.tree.item(item, "values")
                    if item_values and len(item_values) > 0:
                        try:
                            game_id = int(item_values[0])
                            game_ids.append(game_id)
                        except (ValueError, TypeError):
                            continue
                
                if not game_ids:
                    self.after(0, lambda: messagebox.showinfo("Info", "Keine Spiele zum Aktualisieren gefunden."))
                    return
                
                total = len(game_ids)
                self.after(0, lambda: self.btn_update_odds.config(state=tk.DISABLED, text=f"Quoten aktualisieren... (0/{total})"))
                
                updated_count = 0
                for idx, game_id in enumerate(game_ids):
                    try:
                        # Load odds from API
                        odd_home, odd_draw, odd_away, odd_over, odd_under = self._get_odds_from_api(game_id)
                        
                        # Update cache
                        self.odds_cache[str(game_id)] = (odd_home, odd_draw, odd_away, odd_over, odd_under)
                        
                        # Update tree if game is still displayed
                        if self.tree.exists(str(game_id)):
                            current_values = list(self.tree.item(str(game_id), "values"))
                            if len(current_values) >= 14:
                                # Update odds columns (indices 7-11)
                                current_values[7] = odd_home
                                current_values[8] = odd_draw
                                current_values[9] = odd_away
                                current_values[10] = odd_over
                                current_values[11] = odd_under
                                current_tags = self.tree.item(str(game_id), "tags")
                                self.after(0, lambda vid=str(game_id), v=tuple(current_values), t=current_tags: 
                                          self.tree.item(vid, values=v, tags=t))
                        
                        updated_count += 1
                        
                        # Update button text
                        if (idx + 1) % 10 == 0 or idx == total - 1:
                            self.after(0, lambda c=updated_count, t=total: 
                                      self.btn_update_odds.config(text=f"Quoten aktualisieren... ({c}/{t})"))
                        
                        # Rate limiting
                        import time
                        time.sleep(0.5)  # 500ms delay between requests
                        
                    except Exception as e:
                        print(f"[WARNING] Error updating odds for game {game_id}: {e}")
                        continue
                
                # Re-enable button
                self.after(0, lambda: self.btn_update_odds.config(state=tk.NORMAL, text='📊 Quoten aktualisieren'))
                self.after(0, lambda: messagebox.showinfo("Erfolg", f"Quoten für {updated_count}/{total} Spiele aktualisiert."))
                
            except Exception as e:
                self.after(0, lambda: self.btn_update_odds.config(state=tk.NORMAL, text='📊 Quoten aktualisieren'))
                self.after(0, lambda: messagebox.showerror("Fehler", f"Fehler beim Aktualisieren der Quoten: {e}"))
        
        # Start update in background thread
        thread = threading.Thread(target=update_odds_thread, daemon=True)
        thread.start()


def run_gui(refresh_seconds: int = 60, headless: Optional[bool] = False):
    root = tk.Tk()
    mw = MainWindow(root, refresh_seconds=refresh_seconds)
    mw.start_refresh()
    root.mainloop()
