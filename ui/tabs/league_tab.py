"""League information tab for displaying league details.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import http.client
import json
import os
import sqlite3
from datetime import datetime
from collections import defaultdict
import statistics

# Try to import matplotlib for charts
try:
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

from services.match_status import SQL_FILTER_STILL_PENDING
from ui.league_display_enhancer import (
    HoverTip,
    apply_compact_headings,
    apply_view_mode_widths,
    alarm_heat_index,
    alarm_season_deviation,
    build_streak_special_signal,
    build_trend_cell,
    first_numeric,
    format_alarm_bell,
    format_diff,
    format_streak_cell,
    load_watchlist,
    max_streak_tooltip_text,
    parse_percent_value,
    save_watchlist,
    streak_alert_level,
    STREAK_COL_HINTS,
)


class LeagueTab(tk.Frame):
    def __init__(self, parent, services):
        super().__init__(parent)
        self.services = services
        self.api_base = "api.sstats.net"
        # Load leagues from database instead of hardcoded list
        self.leagues = self._load_leagues_from_database()
        # Unterklassen können years_to_show vor super().__init__ setzen
        self.years_to_show = list(getattr(self, "years_to_show", None) or ["2022", "2023", "2024", "2025", "2026"])
        # Set default year to 2026 (Saison 26/27)
        self.year = "2026"
        # League-specific current seasons (for leagues that started early)
        self.current_seasons = {
            128: 2026  # Argentina Liga Profesional
        }
        self.setup_ui()
        # Load data after a short delay to ensure UI is ready
        print("[DEBUG] LeagueTab initialized")
        print(f"[DEBUG] Loaded {len(self.leagues)} leagues from database")
        if len(self.leagues) > 0:
            first_leagues = [f"{l['country']} - {l['name']}" for l in self.leagues[:3]]
            print(f"[DEBUG] First few leagues: {first_leagues}")
        # Try multiple approaches to ensure data is loaded
        self.after_idle(self.load_league_games_counts)
        self.after(100, self.load_league_games_counts)  # Also try after 100ms
        self.after(500, lambda: self._ensure_data_loaded())  # Fallback check

    def _history_years(self):
        """Jahre für Durchschnitt / Vergleich, ohne die aktuelle Saison (2026)."""
        current = str(getattr(self, "year", "2026") or "2026")
        return [str(y) for y in self.years_to_show if str(y) != current]

    def _avg_heading(self, line: str) -> str:
        hist = self._history_years()
        if len(hist) >= 2:
            return f"Avg {line} ({hist[0]}-{hist[-1]})"
        if hist:
            return f"Avg {line} ({hist[0]})"
        return f"Avg {line}"
    
    def _detect_available_years(self):
        """Detect available years from database games"""
        try:
            from database import DatabaseManager
            db_manager = DatabaseManager("data/flashscore.db")
            conn = db_manager.get_connection()
            
            # Get distinct years from games table, ordered ascending
            years_result = conn.execute("""
                SELECT DISTINCT season_year 
                FROM games 
                WHERE season_year IS NOT NULL 
                AND season_year >= 2022
                ORDER BY season_year ASC
            """).fetchall()
            
            years = [str(row[0]) for row in years_result if row[0] is not None]
            
            # Always include at least 2022-2026, and add any additional years found
            base_years = ["2022", "2023", "2024", "2025", "2026"]
            all_years = sorted(set(base_years + years), key=int)
            
            # Also include current year and next year if not already present
            from datetime import datetime
            current_year = datetime.now().year
            next_year = current_year + 1
            all_years = sorted(set(all_years + [str(current_year), str(next_year)]), key=int)
            
            print(f"[DEBUG] Detected available years: {all_years}")
            return all_years
        except Exception as e:
            print(f"[WARNING] Could not detect years from database: {e}")
            # Fallback to default years
            return ["2022", "2023", "2024", "2025", "2026"]
    
    @staticmethod
    def _ensure_league_streak_columns(conn):
        """Ensure all streak columns exist (DB was missing most year columns → UI showed 0)."""
        columns = [
            ("min_streak_current_season", "INTEGER DEFAULT 0"),
            ("median_streak_current_season", "REAL DEFAULT 0"),
            ("min_streak_all_seasons", "INTEGER DEFAULT 0"),
            ("median_streak_all_seasons", "REAL DEFAULT 0"),
            ("max_streak_current_season_35", "INTEGER DEFAULT 0"),
            ("median_streak_current_season_35", "REAL DEFAULT 0"),
            ("max_streak_all_seasons_35", "INTEGER DEFAULT 0"),
            ("median_streak_all_seasons_35", "REAL DEFAULT 0"),
            ("max_streak_current_season_45", "INTEGER DEFAULT 0"),
            ("median_streak_current_season_45", "REAL DEFAULT 0"),
            ("max_streak_all_seasons_45", "INTEGER DEFAULT 0"),
            ("median_streak_all_seasons_45", "REAL DEFAULT 0"),
        ]
        for year in (2022, 2023, 2024, 2025, 2026):
            for metric in ("25", "35", "45"):
                columns.append((f"max_streak_{year}_{metric}", "INTEGER DEFAULT 0"))
        for col_name, col_type in columns:
            try:
                conn.execute(f"ALTER TABLE leagues ADD COLUMN {col_name} {col_type}")
            except Exception:
                pass
        try:
            conn.commit()
        except Exception:
            pass

    # Backwards-compatible alias
    _ensure_max_streak_2026_columns = _ensure_league_streak_columns

    def _get_liga128_exclusive_league_ids(self):
        """
        IDs in data/liga128_leagues.json are shown only in the Liga 128 tab,
        not in the main Leagues overview.
        """
        path = os.path.join("data", "liga128_leagues.json")
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    return {int(x) for x in data if isinstance(x, int)}
        except Exception as e:
            print(f"[WARNING] Could not read liga128_leagues.json: {e}")
        return {128}

    def _get_exclusive_overview_league_ids(self):
        """Ligen mit eigenem Tab (Liga 128, European Competitions) nicht in der Hauptübersicht."""
        ids = set(self._get_liga128_exclusive_league_ids())
        try:
            from services.european_competition_service import EURO_LEAGUE_IDS
            ids |= {int(x) for x in EURO_LEAGUE_IDS}
        except Exception:
            ids |= {2, 3, 848}
        return ids

    def _load_leagues_from_database(self):
        """Load leagues from database - only show leagues that have games in the database
        Excludes leagues listed in Liga 128 config (their own tab)."""
        try:
            from database import DatabaseManager
            db_manager = DatabaseManager("data/flashscore.db")
            conn = db_manager.get_connection()

            excluded_ids = self._get_exclusive_overview_league_ids()
            if excluded_ids:
                placeholders = ",".join(["?" for _ in sorted(excluded_ids)])
                excluded_sql_fragment = f"AND league_id NOT IN ({placeholders})"
                excluded_params = tuple(sorted(excluded_ids))
            else:
                excluded_sql_fragment = ""
                excluded_params = ()
            
            # Target leagues that should always be shown (even if no games yet)
            # Scottish leagues: 179 = Scottish Premiership, 180 = Scottish Championship
            # French leagues: 61 = Ligue 1, 62 = Ligue 2, 63 = National 1
            # Spanish leagues: 140 = La Liga, 141 = Segunda División
            # Indonesian leagues: 274 = Liga 1, 275 = Liga 2
            # Australian leagues: 188 = A-League, 190 = A-League Women
            # Swiss leagues: 207 = Super League, 208 = Challenge League
            # Austrian leagues: 218 = Bundesliga, 219 = 2. Liga
            target_league_ids = [145, 144, 39, 40, 41, 42, 179, 180, 61, 62, 63, 140, 141, 135, 136, 307, 308, 303, 301, 188, 190, 274, 275, 207, 208, 218, 219]
            
            # Get ALL distinct leagues from database - show everything that has a league_id
            # Exclude Liga-128-exclusive IDs (their own tab)
            leagues_from_games = conn.execute(f"""
                SELECT DISTINCT 
                    league_id,
                    COALESCE(league_name, 'Unknown League') as league_name,
                    COALESCE(country_name, 'Unknown') as country_name,
                    country_code
                FROM games
                WHERE league_id IS NOT NULL
                {excluded_sql_fragment}
            """, excluded_params).fetchall()
            
            # Also get leagues from leagues table (leagues that might not have games yet)
            leagues_from_table = conn.execute(f"""
                SELECT 
                    league_id,
                    COALESCE(league_name, 'Unknown League') as league_name,
                    COALESCE(country_name, 'Unknown') as country_name,
                    COALESCE(country_code, '') as country_code
                FROM leagues
                WHERE league_id IS NOT NULL
                {excluded_sql_fragment}
            """, excluded_params).fetchall()
            
            # Combine both sources, using games table data as primary (more up-to-date)
            leagues_dict = {}
            for row in leagues_from_games:
                league_id = row[0]
                leagues_dict[league_id] = row
            
            # Add leagues from leagues table that don't have games yet
            for row in leagues_from_table:
                league_id = row[0]
                if league_id not in leagues_dict:
                    leagues_dict[league_id] = row
            
            # Convert to list and sort
            leagues_data = sorted(leagues_dict.values(), key=lambda x: (x[2] or '', x[1] or ''))
            
            print(f"[DEBUG] Loaded {len(leagues_data)} leagues from database")
            
            # Map to fix duplicate or unclear league names
            # This ensures unique and clear names for leagues with same name but different IDs
            league_name_fixes = {
                307: "Saudi Pro League",      # Fix: Saudi Arabia Pro League (ID 307)
                308: "Saudi Division 1",      # Fix: Saudi Arabia Division 1 (ID 308)
                303: "UAE Division 1",       # Fix: United Arab Emirates Division 1
                301: "UAE Pro League",        # Fix: United Arab Emirates Pro League
                39: "Premier League",        # Great Britain Premier League
                40: "Championship",          # Great Britain Championship
                41: "League One",            # Great Britain League One
                42: "League Two",            # Great Britain League Two
                179: "Scottish Premiership",   # Scotland Premiership
                180: "Scottish Championship", # Scotland Championship
                61: "Ligue 1",               # France Ligue 1
                62: "Ligue 2",               # France Ligue 2
                63: "National 1",           # France National 1
                140: "La Liga",              # Spain La Liga
                141: "Segunda División",     # Spain Segunda División
                274: "Liga 1",               # Indonesia Liga 1
                275: "Liga 2",               # Indonesia Liga 2
                190: "A-League Women",        # Australia A-League Women
                207: "Swiss Super League",    # Switzerland Super League
                208: "Swiss Challenge League", # Switzerland Challenge League
                218: "Austrian Bundesliga",   # Austria Bundesliga
                219: "Austrian 2. Liga",      # Austria 2. Liga
            }
            
            # Convert to list of dicts with same structure as before
            leagues = []
            found_league_ids = set()
            seen_names = {}  # Track (country, name) pairs to detect duplicates
            
            for row in leagues_data:
                league_id, league_name, country_name, country_code = row
                
                if league_id in excluded_ids:
                    continue
                
                # Skip if already processed (avoid duplicates)
                if league_id in found_league_ids:
                    continue
                
                # Apply name fix if needed
                if league_id in league_name_fixes:
                    league_name = league_name_fixes[league_id]
                
                # Check for duplicates: same country and name but different ID
                key = (country_name or "Unknown", league_name)
                if key in seen_names:
                    # Duplicate detected - append ID to name to make it unique
                    existing_id = seen_names[key]
                    # Update existing entry
                    for league in leagues:
                        if league["id"] == existing_id:
                            league["name"] = f"{league['name']} ({existing_id})"
                            break
                    # Use ID in name for current entry
                    league_name = f"{league_name} ({league_id})"
                else:
                    seen_names[key] = league_id
                
                found_league_ids.add(league_id)
                leagues.append({
                    "id": league_id,
                    "name": league_name or f"League {league_id}",
                    "country": country_name or "Unknown",
                    "games_season": 0,
                    "over25": 0,
                    "over35": 0,
                    "over45": 0,
                    "last10_over25": 0,
                    "last10_over35": 0,
                    "last10_over45": 0,
                    "last20_over25": 0,
                    "last20_over35": 0,
                    "last20_over45": 0,
                    "streak25": 0,
                    "streak35": 0,
                    "streak45": 0
                })
            
            # Load streak data from leagues table (before adding target leagues)
            streak_dict = {}
            try:
                self._ensure_league_streak_columns(conn)
                streak_data = conn.execute("""
                    SELECT league_id, 
                           max_streak_current_season, min_streak_current_season, median_streak_current_season,
                           max_streak_all_seasons, min_streak_all_seasons, median_streak_all_seasons,
                           max_streak_current_season_35, median_streak_current_season_35,
                           max_streak_all_seasons_35, median_streak_all_seasons_35,
                           max_streak_current_season_45, median_streak_current_season_45,
                           max_streak_all_seasons_45, median_streak_all_seasons_45,
                           max_streak_2022_25, max_streak_2023_25, max_streak_2024_25, max_streak_2025_25, max_streak_2026_25,
                           max_streak_2022_35, max_streak_2023_35, max_streak_2024_35, max_streak_2025_35, max_streak_2026_35,
                           max_streak_2022_45, max_streak_2023_45, max_streak_2024_45, max_streak_2025_45, max_streak_2026_45
                    FROM leagues
                """).fetchall()
                
                for row in streak_data:
                    league_id = row[0]
                    streak_dict[league_id] = {
                        'max_streak_2022': row[1] or 0,
                        'min_streak_2022': row[2] or 0,
                        'median_streak_2022': row[3] or 0.0,
                        'max_streak_all': row[4] or 0,
                        'min_streak_all': row[5] or 0,
                        'median_streak_all': row[6] or 0.0,
                        'max_streak_2022_35': row[7] or 0,
                        'median_streak_2022_35': row[8] or 0.0,
                        'max_streak_all_35': row[9] or 0,
                        'median_streak_all_35': row[10] or 0.0,
                        'max_streak_2022_45': row[11] or 0,
                        'median_streak_2022_45': row[12] or 0.0,
                        'max_streak_all_45': row[13] or 0,
                        'median_streak_all_45': row[14] or 0.0,
                        'max_streak_2022_25_season': row[15] or 0,
                        'max_streak_2023_25_season': row[16] or 0,
                        'max_streak_2024_25_season': row[17] or 0,
                        'max_streak_2025_25_season': row[18] or 0,
                        'max_streak_2026_25_season': row[19] or 0,
                        'max_streak_2022_35_season': row[20] or 0,
                        'max_streak_2023_35_season': row[21] or 0,
                        'max_streak_2024_35_season': row[22] or 0,
                        'max_streak_2025_35_season': row[23] or 0,
                        'max_streak_2026_35_season': row[24] or 0,
                        'max_streak_2022_45_season': row[25] or 0,
                        'max_streak_2023_45_season': row[26] or 0,
                        'max_streak_2024_45_season': row[27] or 0,
                        'max_streak_2025_45_season': row[28] or 0,
                        'max_streak_2026_45_season': row[29] or 0
                    }
            except Exception as e:
                print(f"[WARNING] Could not load streak data from leagues table: {e}")
                # Fallback: at least load columns that exist in older DBs
                try:
                    fallback = conn.execute("""
                        SELECT league_id,
                               COALESCE(max_streak_current_season, 0),
                               COALESCE(median_streak_current_season, 0),
                               COALESCE(max_streak_all_seasons, 0),
                               COALESCE(median_streak_all_seasons, 0)
                        FROM leagues
                    """).fetchall()
                    for row in fallback:
                        streak_dict[row[0]] = {
                            'max_streak_2022': row[1] or 0,
                            'median_streak_2022': row[2] or 0.0,
                            'max_streak_all': row[3] or 0,
                            'median_streak_all': row[4] or 0.0,
                        }
                except Exception as e2:
                    print(f"[WARNING] Streak fallback also failed: {e2}")
            
            # Add streak data to existing leagues
            for league in leagues:
                league_id = league['id']
                if league_id in streak_dict:
                    league.update(streak_dict[league_id])
                else:
                    # Default values if not in leagues table
                    league['max_streak_2022'] = 0
                    league['min_streak_2022'] = 0
                    league['median_streak_2022'] = 0.0
                    league['max_streak_all'] = 0
                    league['min_streak_all'] = 0
                    league['median_streak_all'] = 0.0
                    league['max_streak_2022_35'] = 0
                    league['median_streak_2022_35'] = 0.0
                    league['max_streak_all_35'] = 0
                    league['median_streak_all_35'] = 0.0
                    league['max_streak_2022_45'] = 0
                    league['median_streak_2022_45'] = 0.0
                    league['max_streak_all_45'] = 0
                    league['median_streak_all_45'] = 0.0
                    league['max_streak_2022_25_season'] = 0
                    league['max_streak_2023_25_season'] = 0
                    league['max_streak_2024_25_season'] = 0
                    league['max_streak_2025_25_season'] = 0
                    league['max_streak_2026_25_season'] = 0
                    league['max_streak_2022_35_season'] = 0
                    league['max_streak_2023_35_season'] = 0
                    league['max_streak_2024_35_season'] = 0
                    league['max_streak_2025_35_season'] = 0
                    league['max_streak_2026_35_season'] = 0
                    league['max_streak_2022_45_season'] = 0
                    league['max_streak_2023_45_season'] = 0
                    league['max_streak_2024_45_season'] = 0
                    league['max_streak_2025_45_season'] = 0
                    league['max_streak_2026_45_season'] = 0
            
            # Add target leagues that are not in database yet
            # Try to get league names from API or use default names
            # Note: Use specific names to avoid duplicates (e.g., different Division 1 leagues)
            league_names_map = {
                145: "Challenger Pro League",
                144: "Jupiler Pro League",
                39: "Premier League (GB)",
                40: "Championship (GB)",
                41: "League One (GB)",
                42: "League Two (GB)",
                179: "Scottish Premiership",
                180: "Scottish Championship",
                61: "Ligue 1",
                62: "Ligue 2",
                63: "National 1",
                140: "La Liga",
                141: "Segunda División",
                135: "Serie A",
                136: "Serie B",
                307: "Saudi Pro League",  # Saudi Arabia Pro League (ID 307)
                308: "Saudi Division 1",  # Saudi Arabia Division 1 (ID 308)
                303: "UAE Division 1",    # United Arab Emirates Division 1
                301: "UAE Pro League",    # United Arab Emirates Pro League
                188: "A-League",
                190: "A-League Women",    # Australia A-League Women
                274: "Liga 1",            # Indonesia Liga 1
                275: "Liga 2"             # Indonesia Liga 2
            }
            
            country_map = {
                145: "Belgium",
                144: "Belgium",
                39: "Great Britain",
                40: "Great Britain",
                41: "Great Britain",
                42: "Great Britain",
                179: "Scotland",
                180: "Scotland",
                61: "France",
                62: "France",
                63: "France",
                140: "Spain",
                141: "Spain",
                135: "Italy",
                136: "Italy",
                307: "Saudi Arabia",
                308: "Saudi Arabia",
                303: "United Arab Emirates",
                301: "United Arab Emirates",
                188: "Australia",
                190: "Australia",
                274: "Indonesia",
                275: "Indonesia"
            }
            
            for league_id in target_league_ids:
                if league_id in excluded_ids:
                    continue
                if league_id not in found_league_ids:
                    new_league = {
                        "id": league_id,
                        "name": league_names_map.get(league_id, f"League {league_id}"),
                        "country": country_map.get(league_id, "Unknown"),
                        "games_season": 0,
                        "over25": 0,
                        "over35": 0,
                        "over45": 0,
                        "last10_over25": 0,
                        "last10_over35": 0,
                        "last10_over45": 0,
                        "last20_over25": 0,
                        "last20_over35": 0,
                        "last20_over45": 0,
                        "streak25": 0,
                        "streak35": 0,
                        "streak45": 0
                    }
                    # Add streak data if available
                    if league_id in streak_dict:
                        new_league.update(streak_dict[league_id])
                    else:
                        new_league['max_streak_2022'] = 0
                        new_league['min_streak_2022'] = 0
                        new_league['median_streak_2022'] = 0.0
                        new_league['max_streak_all'] = 0
                        new_league['min_streak_all'] = 0
                        new_league['median_streak_all'] = 0.0
                    leagues.append(new_league)
            
            # Sort by country and name
            leagues.sort(key=lambda x: (x["country"], x["name"]))
            
            print(f"[DEBUG] Total leagues after adding target leagues: {len(leagues)}")
            if len(leagues) > 0:
                first_leagues = [f"{l['country']} - {l['name']}" for l in leagues[:5]]
                print(f"[DEBUG] First few leagues: {first_leagues}")
            
            return leagues
        except Exception as e:
            # Fallback to empty list if database error
            import traceback
            print(f"[ERROR] Error loading leagues from database: {e}")
            print(f"[ERROR] Traceback: {traceback.format_exc()}")
            return []

    def setup_ui(self):
        # Main frame
        main_frame = tk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Title and Refresh Button Frame
        title_frame = tk.Frame(main_frame)
        title_frame.pack(fill=tk.X, pady=(0, 4))
        
        title_label = tk.Label(title_frame, text="League Information", font=("Arial", 16, "bold"))
        title_label.pack(side=tk.LEFT)
        
        # Refresh Button
        refresh_btn = ttk.Button(title_frame, text="🔄 Daten aktualisieren", command=self.refresh_data)
        refresh_btn.pack(side=tk.RIGHT, padx=10)

        # Display filters / view modes
        self._init_display_controls(main_frame)

        # Split: tables left, detail right
        self.main_paned = ttk.Panedwindow(main_frame, orient=tk.HORIZONTAL)
        self.main_paned.pack(fill=tk.BOTH, expand=True, pady=6)

        left_pane = tk.Frame(self.main_paned)
        right_pane = tk.Frame(self.main_paned, width=320)
        self.main_paned.add(left_pane, weight=4)
        self.main_paned.add(right_pane, weight=1)

        # Create notebook for tabs
        self.notebook = ttk.Notebook(left_pane)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Tab 2.5
        tab_25_frame = tk.Frame(self.notebook)
        tab_25_frame.pack(fill=tk.BOTH, expand=True)
        self.notebook.add(tab_25_frame, text="2.5 Goals")
        self.setup_tab_25(tab_25_frame)

        # Tab 3.5
        tab_35_frame = tk.Frame(self.notebook)
        tab_35_frame.pack(fill=tk.BOTH, expand=True)
        self.notebook.add(tab_35_frame, text="3.5 Goals")
        self.setup_tab_35(tab_35_frame)

        # Tab 4.5
        tab_45_frame = tk.Frame(self.notebook)
        tab_45_frame.pack(fill=tk.BOTH, expand=True)
        self.notebook.add(tab_45_frame, text="4.5 Goals")
        self.setup_tab_45(tab_45_frame)

        # Tab Alarm overview (cross 2.5/3.5/4.5)
        tab_alarm_frame = tk.Frame(self.notebook)
        tab_alarm_frame.pack(fill=tk.BOTH, expand=True)
        self.notebook.add(tab_alarm_frame, text="Alarm Übersicht")
        self.setup_tab_alarm_overview(tab_alarm_frame)

        # Tab Current Seasons (for leagues that started early)
        tab_current_frame = tk.Frame(self.notebook)
        tab_current_frame.pack(fill=tk.BOTH, expand=True)
        self.notebook.add(tab_current_frame, text="Aktuelle Saisons")
        self.setup_tab_current_seasons(tab_current_frame)

        # Tab Max Streaks
        tab_max_streaks_frame = tk.Frame(self.notebook)
        tab_max_streaks_frame.pack(fill=tk.BOTH, expand=True)
        self.notebook.add(tab_max_streaks_frame, text="Max Streaks")
        self.setup_tab_max_streaks(tab_max_streaks_frame)

        # Watchlist
        tab_watch_frame = tk.Frame(self.notebook)
        self.notebook.add(tab_watch_frame, text="★ Watchlist")
        self.setup_tab_watchlist(tab_watch_frame)

        # Detail panel (right)
        self._setup_detail_panel(right_pane)

        # Hover tip shared
        self._hover_tip = HoverTip(self)
        self._hover_after_id = None
        self.watchlist_ids = set(load_watchlist())

        # Status
        self.status_label = tk.Label(main_frame, text="Ready")
        self.status_label.pack(anchor=tk.W, pady=5)

        # Apply default view mode widths after trees exist
        self.after(50, self._apply_view_mode_to_trees)

    def _init_display_controls(self, parent):
        bar = tk.LabelFrame(parent, text="Anzeige", padx=6, pady=4)
        bar.pack(fill=tk.X, pady=(0, 4))

        self.filter_search_var = tk.StringVar(value="")
        self.filter_alarm_var = tk.BooleanVar(value=False)
        self.filter_today_var = tk.BooleanVar(value=False)
        self.filter_has_data_var = tk.BooleanVar(value=True)  # default: hide empty 2026
        self.filter_min_streak_var = tk.StringVar(value="0")
        self.view_mode_var = tk.StringVar(value="kompakt")

        tk.Label(bar, text="Suche:").pack(side=tk.LEFT)
        search_entry = ttk.Entry(bar, textvariable=self.filter_search_var, width=18)
        search_entry.pack(side=tk.LEFT, padx=(2, 8))
        search_entry.bind("<KeyRelease>", lambda e: self._on_display_filter_changed())

        ttk.Checkbutton(
            bar, text="nur Alarm", variable=self.filter_alarm_var,
            command=self._on_display_filter_changed,
        ).pack(side=tk.LEFT, padx=4)
        ttk.Checkbutton(
            bar, text="nur Heute", variable=self.filter_today_var,
            command=self._on_display_filter_changed,
        ).pack(side=tk.LEFT, padx=4)
        ttk.Checkbutton(
            bar, text="nur mit 2026-Daten", variable=self.filter_has_data_var,
            command=self._on_display_filter_changed,
        ).pack(side=tk.LEFT, padx=4)

        tk.Label(bar, text="Min-Streak:").pack(side=tk.LEFT, padx=(8, 2))
        streak_spin = ttk.Spinbox(
            bar, from_=0, to=30, width=4, textvariable=self.filter_min_streak_var,
            command=self._on_display_filter_changed,
        )
        streak_spin.pack(side=tk.LEFT)
        streak_spin.bind("<KeyRelease>", lambda e: self._on_display_filter_changed())

        tk.Label(bar, text="Ansicht:").pack(side=tk.LEFT, padx=(12, 2))
        for mode, label in (("kompakt", "Kompakt"), ("vergleich", "Vergleich"), ("voll", "Voll")):
            ttk.Radiobutton(
                bar, text=label, value=mode, variable=self.view_mode_var,
                command=self._on_view_mode_changed,
            ).pack(side=tk.LEFT, padx=2)

        ttk.Button(bar, text="Filter anwenden", command=self._on_display_filter_changed).pack(side=tk.RIGHT, padx=4)

    def _setup_detail_panel(self, parent):
        frame = tk.LabelFrame(parent, text="Liga-Detail", padx=6, pady=6)
        frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)

        self.detail_title = tk.Label(frame, text="Liga auswählen", font=("Arial", 11, "bold"), wraplength=280)
        self.detail_title.pack(anchor="w")
        self.detail_subtitle = tk.Label(frame, text="", fg="gray", wraplength=280)
        self.detail_subtitle.pack(anchor="w", pady=(0, 6))

        self.detail_info = tk.Text(frame, height=10, width=36, font=("Consolas", 9), wrap=tk.WORD)
        self.detail_info.pack(fill=tk.X)
        self.detail_info.insert("1.0", "Klick auf eine Liga → Statistik & Streaks hier.\nHover auf Streak-Spalte → Max-Streak-Popup.")
        self.detail_info.config(state=tk.DISABLED)

        self.detail_chart_frame = tk.Frame(frame)
        self.detail_chart_frame.pack(fill=tk.BOTH, expand=True, pady=6)
        self._detail_canvas = None

        btn_row = tk.Frame(frame)
        btn_row.pack(fill=tk.X)
        ttk.Button(btn_row, text="★ Watchlist", command=self._add_selected_to_watchlist).pack(side=tk.LEFT, padx=2)

    def setup_tab_watchlist(self, parent):
        top = tk.Frame(parent)
        top.pack(fill=tk.X, padx=8, pady=6)
        tk.Label(top, text="Markierte Ligen (Rechtsklick → Watchlist)", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
        ttk.Button(top, text="Aktualisieren", command=self._populate_watchlist_tree).pack(side=tk.RIGHT)

        table = tk.Frame(parent)
        table.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        table.grid_rowconfigure(0, weight=1)
        table.grid_columnconfigure(0, weight=1)

        cols = ("Country", "ID", "Name", "Heute", "Games_2026", "Alarm2.5", "Streak2.5", "Over2.5_2026", "Diff2.5")
        self.leagues_tree_watch = ttk.Treeview(table, columns=cols, show="headings", height=12)
        for c in cols:
            self.leagues_tree_watch.heading(c, text=c, command=lambda col=c: self.sort_tree(self.leagues_tree_watch, col))
            self.leagues_tree_watch.column(c, width=100, anchor="center")
        self.leagues_tree_watch.column("Name", width=180, anchor="w")
        self.leagues_tree_watch.column("Country", width=110, anchor="w")
        apply_compact_headings(self.leagues_tree_watch)

        vsb = ttk.Scrollbar(table, orient=tk.VERTICAL, command=self.leagues_tree_watch.yview)
        self.leagues_tree_watch.configure(yscrollcommand=vsb.set)
        self.leagues_tree_watch.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        self.leagues_tree_watch.bind("<Double-1>", self.show_games_list)
        self.leagues_tree_watch.bind("<<TreeviewSelect>>", lambda e: self._on_league_row_selected(self.leagues_tree_watch))
        self.leagues_tree_watch.bind("<Button-3>", self._on_right_click_watchlist)

    def _default_col_widths(self, tree) -> dict:
        widths = {}
        for col in tree["columns"]:
            try:
                widths[col] = int(tree.column(col, "width"))
            except Exception:
                widths[col] = 90
        # Ensure frozen columns stay readable
        widths["Country"] = max(widths.get("Country", 100), 100)
        widths["Name"] = max(widths.get("Name", 160), 160)
        widths["Heute"] = max(widths.get("Heute", 70), 70)
        widths["ID"] = max(widths.get("ID", 50), 50)
        return widths

    def _apply_view_mode_to_trees(self):
        mode = self.view_mode_var.get() if hasattr(self, "view_mode_var") else "kompakt"
        mapping = (
            (getattr(self, "leagues_tree_25", None), "25"),
            (getattr(self, "leagues_tree_35", None), "35"),
            (getattr(self, "leagues_tree_45", None), "45"),
        )
        for tree, key in mapping:
            if tree is None:
                continue
            if not hasattr(tree, "_default_widths"):
                tree._default_widths = self._default_col_widths(tree)
            apply_view_mode_widths(tree, key, mode, tree._default_widths)
            apply_compact_headings(tree)

    def _on_view_mode_changed(self):
        self._apply_view_mode_to_trees()

    def _on_display_filter_changed(self, *_):
        # Re-render from cached league stats (no full DB reload)
        if not getattr(self, "leagues", None):
            return
        if not hasattr(self, "leagues_tree_25"):
            return
        try:
            self._render_filtered_league_tables()
        except Exception as e:
            print(f"[WARNING] Filter refresh failed: {e}")

    def _league_passes_display_filter(self, league, metric_prefix="over25", streak_key="streak25_2026") -> bool:
        if not hasattr(self, "filter_has_data_var"):
            return True
        year = str(getattr(self, "year", "2026"))
        games = league.get(f"games_{year}", 0) or 0
        try:
            games = int(games) if games != "Error" else 0
        except (TypeError, ValueError):
            games = 0

        if self.filter_has_data_var.get() and games <= 0:
            return False

        q = (self.filter_search_var.get() or "").strip().lower()
        if q:
            hay = f"{league.get('country','')} {league.get('name','')} {league.get('id','')}".lower()
            if q not in hay:
                return False

        lid = int(league.get("id", 0) or 0)
        today = getattr(self, "_today_upcoming_counts", {}).get(lid, 0)
        if self.filter_today_var.get() and today <= 0:
            return False

        if self.filter_alarm_var.get():
            alarm = self._get_alarm_metric_value(league, metric_prefix) or ""
            if not alarm:
                return False

        try:
            min_streak = int(float(self.filter_min_streak_var.get() or 0))
        except ValueError:
            min_streak = 0
        if min_streak > 0:
            streak = league.get(streak_key, 0) or 0
            try:
                streak = int(streak)
            except (TypeError, ValueError):
                streak = 0
            if streak < min_streak:
                return False
        return True

    def _bind_enhanced_tree(self, tree, metric_focus: str):
        """Hover-Tooltips (Streak→Max-Streaks), Selektion→Detail, kompakte Header."""
        apply_compact_headings(tree)
        tree._metric_focus = metric_focus
        tree.bind("<Motion>", lambda e, t=tree: self._on_tree_motion(e, t), add="+")
        tree.bind("<Leave>", lambda e: self._hover_tip.hide(), add="+")
        tree.bind("<<TreeviewSelect>>", lambda e, t=tree: self._on_league_row_selected(t), add="+")
        tree.bind("<Button-1>", lambda e, t=tree: self._schedule_detail_from_click(e, t), add="+")

    def _schedule_detail_from_click(self, event, tree):
        row = tree.identify_row(event.y)
        if row:
            tree.selection_set(row)
            self.after(10, lambda: self._on_league_row_selected(tree))

    def _on_tree_motion(self, event, tree):
        col = tree.identify_column(event.x)
        row = tree.identify_row(event.y)
        if self._hover_after_id:
            try:
                self.after_cancel(self._hover_after_id)
            except Exception:
                pass
            self._hover_after_id = None

        if not row or not col:
            self._hover_tip.hide()
            return

        try:
            col_index = int(col.replace("#", "")) - 1
            columns = tree["columns"]
            if col_index < 0 or col_index >= len(columns):
                self._hover_tip.hide()
                return
            col_name = columns[col_index]
        except Exception:
            self._hover_tip.hide()
            return

        values = tree.item(row, "values")
        if not values or len(values) < 2:
            return
        league = self._find_league_for_row(values)
        tip_text = None

        # Streak-Spalte → volle Max-Streak-Tabelle
        focus = STREAK_COL_HINTS.get(col_name) or getattr(tree, "_metric_focus", "25")
        if col_name in STREAK_COL_HINTS or "Streak" in col_name and "Median" not in col_name and "Max" not in col_name:
            if league:
                tip_text = max_streak_tooltip_text(league, focus=focus)
        else:
            # Spalten-Erklärung
            tips = getattr(tree, "_col_tooltips", {})
            tip_text = tips.get(col_name)

        if tip_text:
            self._hover_after_id = self.after(
                280,
                lambda t=tip_text, x=event.x_root, y=event.y_root: self._hover_tip.show(t, x, y),
            )
        else:
            self._hover_tip.hide()

    def _find_league_by_id(self, league_id):
        try:
            lid = int(league_id)
        except (TypeError, ValueError):
            return None
        for league in getattr(self, "leagues", []) or []:
            if int(league.get("id", -1)) == lid:
                return league
        return None

    def _find_league_for_row(self, values):
        """Liga zur Tabellenzeile (Unterklassen können ID-Spalte umschreiben)."""
        if not values or len(values) < 2:
            return None
        return self._find_league_by_id(values[1])

    def _on_league_row_selected(self, tree):
        sel = tree.selection()
        if not sel:
            return
        values = tree.item(sel[0], "values")
        if not values or len(values) < 2:
            return
        league = self._find_league_for_row(values)
        if league:
            self._update_detail_panel(league, getattr(tree, "_metric_focus", "25"))

    def _update_detail_panel(self, league, focus="25"):
        if not hasattr(self, "detail_title"):
            return
        self.detail_title.config(text=f"{league.get('name', '')}")
        self.detail_subtitle.config(
            text=f"{league.get('country', '')} · ID {league.get('id')} · Saison {self.current_seasons.get(league.get('id'), 2026)}"
        )
        text = max_streak_tooltip_text(league, focus=focus)
        # Extra season stats
        year = "2026"
        prefix = {"25": "over25", "35": "over35", "45": "over45", "55": "over55"}[focus]
        extra = [
            "",
            f"Over {focus[0]}.{focus[1]} {year}: {league.get(f'{prefix}_{year}', '–')}",
            f"Last10: {league.get(f'last10_{prefix}_{year}', '–')}",
            f"Last20: {league.get(f'last20_{prefix}_{year}', '–')}",
            f"Spiele: {league.get(f'games_{year}', 0)}",
        ]
        self.detail_info.config(state=tk.NORMAL)
        self.detail_info.delete("1.0", tk.END)
        self.detail_info.insert("1.0", text + "\n" + "\n".join(extra))
        self.detail_info.config(state=tk.DISABLED)
        self._draw_detail_chart(league, focus)
        self._selected_league_for_watch = league

    def _draw_detail_chart(self, league, focus="25"):
        for child in self.detail_chart_frame.winfo_children():
            child.destroy()
        self._detail_canvas = None
        if not HAS_MATPLOTLIB:
            tk.Label(self.detail_chart_frame, text="matplotlib fehlt", fg="gray").pack()
            return

        tip = tk.Label(
            self.detail_chart_frame,
            text="Punkt anklicken → Monat / Runde / Spiele",
            fg="#555",
            font=("Arial", 8),
        )
        tip.pack(anchor="w")

        prefix = {"25": "over25", "35": "over35", "45": "over45", "55": "over55"}[focus]
        years = list(self.years_to_show)
        vals = [parse_percent_value(league.get(f"{prefix}_{y}", None)) for y in years]
        fig = Figure(figsize=(3.2, 2.0), dpi=100)
        ax = fig.add_subplot(111)
        plot_y = [v if v is not None else float("nan") for v in vals]
        line, = ax.plot(years, plot_y, marker="o", color="#1f77b4", linewidth=1.8, picker=8)
        ax.set_ylim(0, 100)
        ax.set_ylabel("%")
        ax.set_title(f"Over {focus[0]}.{focus[1]} je Saison")
        ax.grid(True, linestyle="--", alpha=0.4)
        fig.tight_layout()

        self._detail_chart_league = league
        self._detail_chart_focus = focus
        self._detail_chart_years = years

        def on_pick(event):
            if event.artist is not line:
                return
            if not len(getattr(event, "ind", [])):
                return
            idx = int(event.ind[0])
            if idx < 0 or idx >= len(years):
                return
            year = years[idx]
            self._schedule_season_breakdown(league, year, focus)

        def on_click(event):
            if event.inaxes != ax or event.xdata is None or event.ydata is None:
                return
            try:
                nearest = min(range(len(years)), key=lambda i: abs(i - float(event.xdata)))
                yv = plot_y[nearest]
                if yv != yv:  # NaN
                    return
                if abs(event.ydata - yv) > 15:
                    return
                self._schedule_season_breakdown(league, years[nearest], focus)
            except Exception:
                pass

        canvas = FigureCanvasTkAgg(fig, master=self.detail_chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        fig.canvas.mpl_connect("pick_event", on_pick)
        fig.canvas.mpl_connect("button_press_event", on_click)
        self._detail_canvas = canvas

        btn_row = tk.Frame(self.detail_chart_frame)
        btn_row.pack(fill=tk.X, pady=4)
        for y in reversed(years[-3:]):
            ttk.Button(
                btn_row,
                text=str(y),
                width=5,
                command=lambda yy=y: self._open_season_goal_breakdown(league, yy, focus),
            ).pack(side=tk.LEFT, padx=2)

    def _schedule_season_breakdown(self, league, year, focus):
        """Debounce double fire from pick+click."""
        key = (league.get("id"), str(year), str(focus))
        now = datetime.now().timestamp()
        last = getattr(self, "_last_breakdown_open", (None, 0))
        if last[0] == key and (now - last[1]) < 0.8:
            return
        self._last_breakdown_open = (key, now)
        self.after(0, lambda: self._open_season_goal_breakdown(league, year, focus))

    def _fetch_league_games_for_year(self, league_id, year):
        """Finished games for one league/year with goals + round."""
        from database import DatabaseManager
        import sqlite3
        db_manager = DatabaseManager("data/flashscore.db")
        conn = db_manager.get_connection()
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, date, home_team_name, away_team_name,
                   home_ft_result, away_ft_result, total_goals, round_name,
                   season_year
            FROM games
            WHERE league_id = ?
              AND season_year = ?
              AND status IN (7, 8, 9, 10)
            ORDER BY date ASC
            """,
            (int(league_id), int(year)),
        ).fetchall()
        games = []
        for r in rows:
            tg = r["total_goals"]
            if tg is None:
                h = r["home_ft_result"]
                a = r["away_ft_result"]
                if h is not None and a is not None:
                    try:
                        tg = int(h) + int(a)
                    except Exception:
                        tg = 0
                else:
                    tg = 0
            games.append(
                {
                    "id": r["id"],
                    "date": r["date"],
                    "home_team_name": r["home_team_name"],
                    "away_team_name": r["away_team_name"],
                    "home_ft_result": r["home_ft_result"],
                    "away_ft_result": r["away_ft_result"],
                    "total_goals": tg,
                    "round_name": r["round_name"],
                    "season_year": r["season_year"],
                }
            )
        return games, conn

    def _open_season_goal_breakdown(self, league, year, focus="25"):
        """Popup: Tore pro Monat / pro Runde / pro Spiel for clicked season point."""
        league_id = league.get("id")
        league_name = league.get("name", f"League {league_id}")
        try:
            year_int = int(year)
        except (TypeError, ValueError):
            messagebox.showwarning("Saison", f"Ungültiges Jahr: {year}")
            return

        try:
            games, conn = self._fetch_league_games_for_year(league_id, year_int)
        except Exception as e:
            messagebox.showerror("Fehler", f"Spiele konnten nicht geladen werden:\n{e}")
            return

        win = tk.Toplevel(self)
        win.title(f"{league_name} — Saison {year_int} (Tore)")
        win.geometry("1100x720")
        win.transient(self.winfo_toplevel())

        header = tk.Frame(win)
        header.pack(fill=tk.X, padx=10, pady=6)
        tk.Label(
            header,
            text=f"{league.get('country', '')} · {league_name} · {year_int}",
            font=("Arial", 12, "bold"),
        ).pack(side=tk.LEFT)
        tk.Label(
            header,
            text=f"{len(games)} Spiele · Klick kam aus Over-{focus[0]}.{focus[1]}-Historie",
            fg="gray",
        ).pack(side=tk.LEFT, padx=12)

        nb = ttk.Notebook(win)
        nb.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        tab_month = tk.Frame(nb)
        tab_round = tk.Frame(nb)
        tab_games = tk.Frame(nb)
        nb.add(tab_month, text="Tore pro Monat")
        nb.add(tab_round, text="Tore pro Runde")
        nb.add(tab_games, text="Tore pro Spiel")

        if not games:
            for tab in (tab_month, tab_round, tab_games):
                tk.Label(tab, text=f"Keine Spiele für {year_int}", fg="gray").pack(expand=True)
            return

        # Monat: reuse existing chart helper (expects list of dict-like games)
        try:
            self._create_goals_chart(tab_month, games, f"{league_name} ({year_int})")
            # Force season combo to this year if present
            for child in tab_month.winfo_children():
                if isinstance(child, tk.Frame):
                    for sub in child.winfo_children():
                        if isinstance(sub, ttk.Combobox):
                            try:
                                sub.set(str(year_int))
                                sub.event_generate("<<ComboboxSelected>>")
                            except Exception:
                                pass
        except Exception as e:
            tk.Label(tab_month, text=f"Monats-Chart Fehler: {e}", fg="red").pack()

        try:
            self._create_per_round_stats_tab(tab_round, league_id, conn, league_name, year_int)
        except Exception as e:
            tk.Label(tab_round, text=f"Runden-Chart Fehler: {e}", fg="red").pack()

        try:
            self._create_per_game_goals_chart(tab_games, games, league_name, year_int)
        except Exception as e:
            tk.Label(tab_games, text=f"Spiel-Chart Fehler: {e}", fg="red").pack()

    def _create_per_game_goals_chart(self, parent, games, league_name, year_int):
        """Bar chart: total goals of each match in chronological order."""
        if not HAS_MATPLOTLIB:
            tk.Label(parent, text="matplotlib fehlt", fg="red").pack(expand=True)
            return
        if not games:
            tk.Label(parent, text="Keine Spiele", fg="gray").pack(expand=True)
            return

        goals = []
        labels = []
        for i, g in enumerate(games, start=1):
            tg = g.get("total_goals")
            if tg is None:
                try:
                    tg = int(g.get("home_ft_result") or 0) + int(g.get("away_ft_result") or 0)
                except Exception:
                    tg = 0
            goals.append(int(tg or 0))
            rnd = (g.get("round_name") or "")[:10]
            labels.append(str(i) if not rnd else f"{i}")

        fig = Figure(figsize=(10, 5), dpi=100)
        ax = fig.add_subplot(111)
        colors = []
        for g in goals:
            if g >= 5:
                colors.append("#90EE90")
            elif g == 4:
                colors.append("#FFFF99")
            elif g == 3:
                colors.append("#FFA500")
            else:
                colors.append("#FFB6C1")
        x = list(range(len(goals)))
        ax.bar(x, goals, color=colors, edgecolor="white", linewidth=0.4)
        if goals:
            avg = sum(goals) / len(goals)
            ax.axhline(avg, color="#2c3e50", linestyle="--", linewidth=1.5, label=f"Ø {avg:.2f}")
        ax.set_ylabel("Tore")
        ax.set_xlabel("Spiel (chronologisch)")
        ax.set_title(f"Tore pro Spiel — {league_name} {year_int} ({len(goals)} Spiele)")
        ax.set_ylim(0, max(goals + [1]) + 1)
        step = max(1, len(labels) // 20)
        ax.set_xticks(x[::step])
        ax.set_xticklabels(labels[::step], fontsize=7)
        ax.legend(loc="upper right")
        ax.grid(axis="y", linestyle="--", alpha=0.35)
        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        # Mini legend
        tk.Label(
            parent,
            text="Farbe: rot ≤2 · orange 3 · gelb 4 · grün ≥5 Tore",
            fg="gray",
            font=("Arial", 8),
        ).pack(anchor="w", padx=8)

    def _add_selected_to_watchlist(self):
        league = getattr(self, "_selected_league_for_watch", None)
        if not league:
            messagebox.showinfo("Watchlist", "Bitte zuerst eine Liga auswählen.")
            return
        self.watchlist_ids.add(int(league["id"]))
        save_watchlist(self.watchlist_ids)
        self._populate_watchlist_tree()
        messagebox.showinfo("Watchlist", f"{league.get('name')} hinzugefügt.")

    def _on_right_click_watchlist(self, event):
        widget = event.widget
        row_id = widget.identify_row(event.y)
        if not row_id:
            return
        widget.selection_set(row_id)
        values = widget.item(row_id)["values"]
        if not values or len(values) < 3:
            return
        league_id = int(values[1])
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(
            label="★ Von Watchlist entfernen",
            command=lambda: self._remove_from_watchlist(league_id),
        )
        menu.add_command(label="Abbrechen", command=menu.destroy)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _remove_from_watchlist(self, league_id):
        self.watchlist_ids.discard(int(league_id))
        save_watchlist(self.watchlist_ids)
        self._populate_watchlist_tree()

    def _populate_watchlist_tree(self):
        if not hasattr(self, "leagues_tree_watch"):
            return
        for item in self.leagues_tree_watch.get_children():
            self.leagues_tree_watch.delete(item)
        today = getattr(self, "_today_upcoming_counts", {})
        for league in self.leagues or []:
            if int(league.get("id", -1)) not in self.watchlist_ids:
                continue
            lid = int(league["id"])
            alarm = self._get_alarm_metric_value(league, "over25") or ""
            diff = parse_percent_value(league.get("over25_2026"))
            avg_vals = []
            for y in ("2022", "2023", "2024", "2025"):
                p = parse_percent_value(league.get(f"over25_{y}"))
                if p is not None:
                    avg_vals.append(p)
            avg = sum(avg_vals) / len(avg_vals) if avg_vals else None
            diff_s = format_diff(None if diff is None or avg is None else diff - avg)
            self.leagues_tree_watch.insert(
                "",
                tk.END,
                values=(
                    league.get("country"),
                    lid,
                    league.get("name"),
                    self._today_games_cell_label(today.get(lid, 0)),
                    league.get("games_2026", 0),
                    alarm,
                    league.get("streak25_2026", 0),
                    league.get("over25_2026", 0),
                    diff_s,
                ),
            )

    def _render_filtered_league_tables(self):
        """Nur Tabellen neu befüllen (Daten schon in self.leagues)."""
        self._skip_db_reload_once = True
        self.load_league_games_counts()

    def setup_tab_alarm_overview(self, parent):
        """Setup compact alarm overview across 2.5 / 3.5 / 4.5."""
        table_frame = tk.LabelFrame(parent, text="Ligen mit Alarm-Signalen")
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        columns = (
            "Country", "ID", "Name", "CurrentSeason",
            "Alarm2.5", "Streak2.5",
            "Spezial2.5",
            "Alarm3.5", "Streak3.5",
            "Spezial3.5",
            "Alarm4.5", "Streak4.5",
            "Spezial4.5",
            "Heute"
        )
        self.leagues_tree_alarm = ttk.Treeview(table_frame, columns=columns, show="headings", height=10)
        self.leagues_tree_alarm.sort_column = None
        self.leagues_tree_alarm.sort_reverse = False

        for col in columns:
            self.leagues_tree_alarm.heading(col, text=col, command=lambda c=col: self.sort_tree(self.leagues_tree_alarm, c))
        self.leagues_tree_alarm.heading("Heute", text="Heute Spi.")

        self.leagues_tree_alarm.column("Country", width=130)
        self.leagues_tree_alarm.column("ID", width=80, anchor="center")
        self.leagues_tree_alarm.column("Name", width=280)
        self.leagues_tree_alarm.column("CurrentSeason", width=110, anchor="center")
        self.leagues_tree_alarm.column("Alarm2.5", width=110, anchor="center")
        self.leagues_tree_alarm.column("Streak2.5", width=90, anchor="center")
        self.leagues_tree_alarm.column("Spezial2.5", width=90, anchor="center")
        self.leagues_tree_alarm.column("Alarm3.5", width=110, anchor="center")
        self.leagues_tree_alarm.column("Streak3.5", width=90, anchor="center")
        self.leagues_tree_alarm.column("Spezial3.5", width=90, anchor="center")
        self.leagues_tree_alarm.column("Alarm4.5", width=110, anchor="center")
        self.leagues_tree_alarm.column("Streak4.5", width=90, anchor="center")
        self.leagues_tree_alarm.column("Spezial4.5", width=90, anchor="center")
        self.leagues_tree_alarm.column("Heute", width=100, anchor="center")

        self.leagues_tree_alarm.tag_configure("alarm_strong", background="#ffe5b4")
        self.leagues_tree_alarm.tag_configure("alarm_warning", background="#fff3cd")
        self._configure_alert_tree_tags(self.leagues_tree_alarm)

        v_scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.leagues_tree_alarm.yview)
        h_scrollbar = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.leagues_tree_alarm.xview)
        self.leagues_tree_alarm.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        self.leagues_tree_alarm.grid(row=0, column=0, sticky="nsew")
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar.grid(row=1, column=0, sticky="ew")

        self.leagues_tree_alarm.bind("<Double-1>", self.show_games_list)
        self._bind_enhanced_tree(self.leagues_tree_alarm, "25")


    def _get_alarm_metric_value(self, league, metric_prefix):
        """Calculate alarm value for one metric, adapted to League or Liga128 context."""
        current_year = str(getattr(self, "year", "2026"))
        has_data = (league.get(f"games_{current_year}", 0) or 0) > 0
        if not has_data:
            return ""

        if hasattr(self, "_calculate_alarm_2026") and current_year == "2026":
            return self._calculate_alarm_2026(league, metric_prefix)

        streak_map = {
            "over25": "streak25_2026",
            "over35": "streak35_2026",
            "over45": "streak45_2026",
        }
        return self._calculate_alarm(league, metric_prefix, streak_map[metric_prefix])

    def _get_first_numeric(self, league, keys):
        return first_numeric(league, keys)

    def _build_streak_special_signal(self, current_streak, median_streak, max_streak):
        return build_streak_special_signal(current_streak, median_streak, max_streak)

    def _streak_refs_for_metric(self, league, focus: str):
        """Median/Max-Referenzwerte je Over-Linie."""
        if focus == "35":
            return (
                first_numeric(league, ["median_streak_all_35", "median_streak_2022_35"]),
                first_numeric(league, ["max_streak_all_35", "max_of_max_35", "max_streak_2022_35"]),
            )
        if focus == "45":
            return (
                first_numeric(league, ["median_streak_all_45", "median_streak_2022_45"]),
                first_numeric(league, ["max_streak_all_45", "max_of_max_45", "max_streak_2022_45"]),
            )
        return (
            first_numeric(league, ["median_streak_all", "median_streak_2022"]),
            first_numeric(league, ["max_streak_all", "max_of_max_25", "max_streak_2022"]),
        )

    def _format_alarm_display(self, league, metric_prefix: str) -> str:
        streak_map = {"over25": "streak25_2026", "over35": "streak35_2026", "over45": "streak45_2026"}
        base = self._calculate_alarm(league, metric_prefix, streak_map.get(metric_prefix, "streak25_2026"))
        if not base:
            return ""
        deviation = alarm_season_deviation(league, metric_prefix, self._history_years())
        return format_alarm_bell(base, deviation)

    def _row_alert_tags(self, league, metric_prefix: str, focus: str, alarm_text: str, today_count: int, has_data: bool):
        """Zeilen-Tags: Streak rot/gelb hat Vorrang, dann Alarm-Farbverlauf."""
        tags = []
        streak_key = {"25": "streak25_2026", "35": "streak35_2026", "45": "streak45_2026"}.get(focus, "streak25_2026")
        median_ref, max_ref = self._streak_refs_for_metric(league, focus)
        streak_level = streak_alert_level(league.get(streak_key, 0), median_ref, max_ref)
        if streak_level == "red":
            tags.append("streak_red")
        elif streak_level == "yellow":
            tags.append("streak_yellow")
        elif alarm_text:
            heat = alarm_heat_index(alarm_season_deviation(league, metric_prefix, self._history_years()))
            if heat:
                tags.append(f"alarm_heat_{heat}")
            else:
                tags.append("alarm_row")
        if not has_data:
            tags.append("no_data")
        if today_count > 0:
            tags.append("games_today")
        return tuple(dict.fromkeys(tags))

    def _configure_alert_tree_tags(self, tree):
        tree.tag_configure("streak_yellow", background="#fef08a")
        tree.tag_configure("streak_red", background="#fecaca")
        for i, color in enumerate(
            ("#fef9c3", "#fef08a", "#fde047", "#fdba74", "#f87171", "#fca5a5"),
            start=1,
        ):
            tree.tag_configure(f"alarm_heat_{i}", background=color)

    def _update_alarm_overview_tab(self):
        """Fill alarm overview tab with leagues that currently have alarm markers."""
        if not hasattr(self, "leagues_tree_alarm"):
            return

        for item in self.leagues_tree_alarm.get_children():
            self.leagues_tree_alarm.delete(item)

        today_counts = getattr(self, "_today_upcoming_counts", {})
        current_year = str(getattr(self, "year", "2026"))

        for league in self.leagues:
            alarm_25 = self._get_alarm_metric_value(league, "over25")
            alarm_35 = self._get_alarm_metric_value(league, "over35")
            alarm_45 = self._get_alarm_metric_value(league, "over45")
            if not (alarm_25 or alarm_35 or alarm_45):
                continue

            league_id = int(league.get("id"))
            today_cnt = today_counts.get(league_id, 0)
            current_season = self.current_seasons.get(league_id, int(current_year))
            league_name = league.get("name", "")

            streak_25 = league.get(f"streak25_{current_year}", 0) or 0
            streak_35 = league.get(f"streak35_{current_year}", 0) or 0
            streak_45 = league.get(f"streak45_{current_year}", 0) or 0

            median_25 = self._get_first_numeric(
                league, ["median_streak_all", "median_streak_all_25", "median_streak_2022"]
            )
            max_25 = self._get_first_numeric(
                league, ["max_streak_all", "max_streak_all_25", "max_of_max_25", "max_streak_2022"]
            )
            median_35 = self._get_first_numeric(
                league, ["median_streak_all_35", "median_streak_2022_35"]
            )
            max_35 = self._get_first_numeric(
                league, ["max_streak_all_35", "max_of_max_35", "max_streak_2022_35"]
            )
            median_45 = self._get_first_numeric(
                league, ["median_streak_all_45", "median_streak_2022_45"]
            )
            max_45 = self._get_first_numeric(
                league, ["max_streak_all_45", "max_of_max_45", "max_streak_2022_45"]
            )

            special_25 = self._build_streak_special_signal(float(streak_25), median_25, max_25)
            special_35 = self._build_streak_special_signal(float(streak_35), median_35, max_35)
            special_45 = self._build_streak_special_signal(float(streak_45), median_45, max_45)

            alarm_25_disp = self._format_alarm_display(league, "over25") if alarm_25 else ""
            alarm_35_disp = self._format_alarm_display(league, "over35") if alarm_35 else ""
            alarm_45_disp = self._format_alarm_display(league, "over45") if alarm_45 else ""

            values = (
                league.get("country", ""),
                league_id,
                league_name,
                current_season,
                alarm_25_disp,
                format_streak_cell(streak_25, median_25, max_25),
                special_25,
                alarm_35_disp,
                format_streak_cell(streak_35, median_35, max_35),
                special_35,
                alarm_45_disp,
                format_streak_cell(streak_45, median_45, max_45),
                special_45,
                self._today_games_cell_label(today_cnt),
            )

            tags = []
            if streak_alert_level(streak_25, median_25, max_25) == "red" or streak_alert_level(streak_35, median_35, max_35) == "red" or streak_alert_level(streak_45, median_45, max_45) == "red":
                tags.append("streak_red")
            elif streak_alert_level(streak_25, median_25, max_25) == "yellow" or streak_alert_level(streak_35, median_35, max_35) == "yellow" or streak_alert_level(streak_45, median_45, max_45) == "yellow":
                tags.append("streak_yellow")
            elif "🔔" in f"{alarm_25}{alarm_35}{alarm_45}":
                tags.append("alarm_strong")
            else:
                tags.append("alarm_warning")

            self.leagues_tree_alarm.insert("", tk.END, values=values, tags=tuple(tags))

    def setup_tab_25(self, parent):
        """Setup tab for 2.5 goals statistics"""
        table_frame = tk.LabelFrame(parent, text="Available Leagues - 2.5 Goals")
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # Build columns: Country, ID, Name, Current Season, Games (2026), Alarm, Streak (2026), Over 2.5 for each year (2025, 2024, 2023, 2022), Last 10/20 (2026), Average (2022-2025), Diff columns
        base_columns = ["Country", "ID", "Name", "Heute", "CurrentSeason", "Games_2026", "Alarm", "Streak2.5_2026"]
        # Years in reverse order: 2026, 2025, 2024, 2023, 2022
        years_reversed = list(reversed(self.years_to_show))
        year_columns = []
        for year in years_reversed:
            year_columns.append(f"Over2.5_{year}")
        year_columns.extend(["Last10_2.5_2026", "Last20_2.5_2026", "Avg2.5_2022_2025", "Diff2.5_2026_Avg", "Diff2.5_Last10_Avg", "Diff2.5_Last20_Avg", "Trend2.5", "MedianStreak2.5", 
                            "MaxStreak2022", "MedianStreak2022", "MaxStreakAll", "MedianStreakAll", "MaxOfMax2.5"])
        all_columns = tuple(base_columns + year_columns)
        
        self.leagues_tree_25 = ttk.Treeview(table_frame, columns=all_columns, show="headings", height=10)
        self.leagues_tree_25.sort_column = None
        self.leagues_tree_25.sort_reverse = False
        self.leagues_tree_25.heading("Country", text="Country")
        self.leagues_tree_25.heading("ID", text="League ID")
        self.leagues_tree_25.heading("Name", text="League Name")
        self.leagues_tree_25.heading("Heute", text="Heute Spi.")
        self.leagues_tree_25.heading("CurrentSeason", text="Current Season")
        self.leagues_tree_25.heading("Games_2026", text="Total Games (2026)")
        self.leagues_tree_25.heading("Alarm", text="Alarm")
        self.leagues_tree_25.heading("Streak2.5_2026", text="Streak 2.5 (2026)")
        
        # Add Over 2.5 for each year in reverse order: 2025, 2024, 2023, 2022
        for year in years_reversed:
            self.leagues_tree_25.heading(f"Over2.5_{year}", text=f"Over 2.5 ({year})")
        self.leagues_tree_25.heading("Last10_2.5_2026", text="Last 10 (2026)")
        self.leagues_tree_25.heading("Last20_2.5_2026", text="Last 20 (2026)")
        self.leagues_tree_25.heading("Avg2.5_2022_2025", text=self._avg_heading("2.5"))
        self.leagues_tree_25.heading("Diff2.5_2026_Avg", text="Diff (2026-Avg)")
        self.leagues_tree_25.heading("Diff2.5_Last10_Avg", text="Diff (Last10-Avg)")
        self.leagues_tree_25.heading("Diff2.5_Last20_Avg", text="Diff (Last20-Avg)")
        self.leagues_tree_25.heading("Trend2.5", text="Trend")
        self.leagues_tree_25.heading("MedianStreak2.5", text=self._avg_heading("Streak").replace("Avg ", "Median "))
        self.leagues_tree_25.heading("MaxStreak2022", text="Max Streak (2022)")
        self.leagues_tree_25.heading("MedianStreak2022", text="Median Streak (2022)")
        self.leagues_tree_25.heading("MaxStreakAll", text="Max Streak (All)")
        self.leagues_tree_25.heading("MedianStreakAll", text="Median Streak (All)")
        self.leagues_tree_25.heading("MaxOfMax2.5", text="Max of Max 2.5")
        
        # Bind heading clicks for sorting
        for col in all_columns:
            self.leagues_tree_25.heading(col, command=lambda c=col: self.sort_tree(self.leagues_tree_25, c))
        
        self.leagues_tree_25.column("Country", width=100)
        self.leagues_tree_25.column("ID", width=80, anchor='center')
        self.leagues_tree_25.column("Name", width=200)
        self.leagues_tree_25.column("Heute", width=88, anchor="center")
        self.leagues_tree_25.column("CurrentSeason", width=100, anchor='center')
        self.leagues_tree_25.column("Games_2026", width=110, anchor='center')
        self.leagues_tree_25.column("Alarm", width=80, anchor='center')
        self.leagues_tree_25.column("Streak2.5_2026", width=100, anchor='center')
        for year in years_reversed:
            self.leagues_tree_25.column(f"Over2.5_{year}", width=100, anchor='center')
        self.leagues_tree_25.column("Last10_2.5_2026", width=90, anchor='center')
        self.leagues_tree_25.column("Last20_2.5_2026", width=90, anchor='center')
        self.leagues_tree_25.column("Avg2.5_2022_2025", width=110, anchor='center')
        self.leagues_tree_25.column("Diff2.5_2026_Avg", width=100, anchor='center')
        self.leagues_tree_25.column("Diff2.5_Last10_Avg", width=110, anchor='center')
        self.leagues_tree_25.column("Diff2.5_Last20_Avg", width=110, anchor='center')
        self.leagues_tree_25.column("Trend2.5", width=110, anchor='center')
        self.leagues_tree_25.column("MedianStreak2.5", width=130, anchor='center')
        self.leagues_tree_25.column("MaxStreak2022", width=100, anchor='center')
        self.leagues_tree_25.column("MedianStreak2022", width=110, anchor='center')
        self.leagues_tree_25.column("MaxStreakAll", width=100, anchor='center')
        self.leagues_tree_25.column("MedianStreakAll", width=110, anchor='center')
        self.leagues_tree_25.column("MaxOfMax2.5", width=120, anchor='center')
        
        # Configure tags for coloring
        self.leagues_tree_25.tag_configure("diff_positive", background="#d4edda")  # Light green
        self.leagues_tree_25.tag_configure("diff_negative", background="#f8d7da")  # Light red
        self.leagues_tree_25.tag_configure("diff_very_negative", background="#f5c6cb")  # Darker red
        self.leagues_tree_25.tag_configure("no_data", background="#e9ecef")  # Light gray for leagues without data
        self.leagues_tree_25.tag_configure("games_today", background="#cce7ff")
        self.leagues_tree_25.tag_configure("alarm_row", background="#ffe8cc")
        self._configure_alert_tree_tags(self.leagues_tree_25)

        # Add scrollbars
        v_scrollbar_25 = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.leagues_tree_25.yview)
        h_scrollbar_25 = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.leagues_tree_25.xview)
        self.leagues_tree_25.configure(yscrollcommand=v_scrollbar_25.set, xscrollcommand=h_scrollbar_25.set)
        
        # Pack scrollbars and treeview
        self.leagues_tree_25.grid(row=0, column=0, sticky="nsew")
        v_scrollbar_25.grid(row=0, column=1, sticky="ns")
        h_scrollbar_25.grid(row=1, column=0, sticky="ew")
        
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)
        
        self.leagues_tree_25.bind("<Double-1>", self.show_games_list)
        self.leagues_tree_25.bind("<Button-3>", self._on_right_click_league)
        self._bind_enhanced_tree(self.leagues_tree_25, "25")

    def setup_tab_35(self, parent):
        """Setup tab for 3.5 goals statistics"""
        table_frame = tk.LabelFrame(parent, text="Available Leagues - 3.5 Goals")
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Build columns: Country, ID, Name, Current Season, Games (2026), Alarm, Streak (2026), Over 3.5 for each year (2025, 2024, 2023, 2022), Last 10/20 (2026), Average (2022-2025), Diff columns
        base_columns = ["Country", "ID", "Name", "Heute", "CurrentSeason", "Games_2026", "Alarm", "Streak3.5_2026"]
        # Years in reverse order: 2026, 2025, 2024, 2023, 2022
        years_reversed = list(reversed(self.years_to_show))
        year_columns = []
        for year in years_reversed:
            year_columns.append(f"Over3.5_{year}")
        year_columns.extend(["Last10_3.5_2026", "Last20_3.5_2026", "Avg3.5_2022_2025", "Diff3.5_2026_Avg", "Diff3.5_Last10_Avg", "Diff3.5_Last20_Avg", "Trend3.5", "MedianStreak3.5",
                            "MaxStreak2022_35", "MedianStreak2022_35", "MaxStreakAll_35", "MedianStreakAll_35",
                            "MaxStreak2022_35_Season", "MaxStreak2023_35_Season", "MaxStreak2024_35_Season", "MaxStreak2025_35_Season", "MaxStreak2026_35_Season", "MaxOfMax3.5"])
        all_columns = tuple(base_columns + year_columns)
        
        self.leagues_tree_35 = ttk.Treeview(table_frame, columns=all_columns, show="headings", height=10)
        self.leagues_tree_35.sort_column = None
        self.leagues_tree_35.sort_reverse = False
        self.leagues_tree_35.heading("Country", text="Country")
        self.leagues_tree_35.heading("ID", text="League ID")
        self.leagues_tree_35.heading("Name", text="League Name")
        self.leagues_tree_35.heading("Heute", text="Heute Spi.")
        self.leagues_tree_35.heading("CurrentSeason", text="Current Season")
        self.leagues_tree_35.heading("Games_2026", text="Total Games (2026)")
        self.leagues_tree_35.heading("Alarm", text="Alarm")
        self.leagues_tree_35.heading("Streak3.5_2026", text="Streak 3.5 (2026)")
        
        # Add Over 3.5 for each year in reverse order: 2025, 2024, 2023, 2022
        for year in years_reversed:
            self.leagues_tree_35.heading(f"Over3.5_{year}", text=f"Over 3.5 ({year})")
        self.leagues_tree_35.heading("Last10_3.5_2026", text="Last 10 (2026)")
        self.leagues_tree_35.heading("Last20_3.5_2026", text="Last 20 (2026)")
        self.leagues_tree_35.heading("Avg3.5_2022_2025", text=self._avg_heading("3.5"))
        self.leagues_tree_35.heading("Diff3.5_2026_Avg", text="Diff (2026-Avg)")
        self.leagues_tree_35.heading("Diff3.5_Last10_Avg", text="Diff (Last10-Avg)")
        self.leagues_tree_35.heading("Diff3.5_Last20_Avg", text="Diff (Last20-Avg)")
        self.leagues_tree_35.heading("Trend3.5", text="Trend")
        self.leagues_tree_35.heading("MedianStreak3.5", text=self._avg_heading("Streak").replace("Avg ", "Median "))
        self.leagues_tree_35.heading("MaxStreak2022_35", text="Max Streak (2022)")
        self.leagues_tree_35.heading("MedianStreak2022_35", text="Median Streak (2022)")
        self.leagues_tree_35.heading("MaxStreakAll_35", text="Max Streak (All)")
        self.leagues_tree_35.heading("MedianStreakAll_35", text="Median Streak (All)")
        self.leagues_tree_35.heading("MaxStreak2022_35_Season", text="Max 2022")
        self.leagues_tree_35.heading("MaxStreak2023_35_Season", text="Max 2023")
        self.leagues_tree_35.heading("MaxStreak2024_35_Season", text="Max 2024")
        self.leagues_tree_35.heading("MaxStreak2025_35_Season", text="Max 2025")
        self.leagues_tree_35.heading("MaxStreak2026_35_Season", text="Max 2026")
        self.leagues_tree_35.heading("MaxOfMax3.5", text="Max of Max 3.5")
        
        # Bind heading clicks for sorting
        for col in all_columns:
            self.leagues_tree_35.heading(col, command=lambda c=col: self.sort_tree(self.leagues_tree_35, c))
        
        self.leagues_tree_35.column("Country", width=100)
        self.leagues_tree_35.column("ID", width=80, anchor='center')
        self.leagues_tree_35.column("Name", width=200)
        self.leagues_tree_35.column("Heute", width=88, anchor="center")
        self.leagues_tree_35.column("CurrentSeason", width=100, anchor='center')
        self.leagues_tree_35.column("Games_2026", width=110, anchor='center')
        self.leagues_tree_35.column("Alarm", width=80, anchor='center')
        self.leagues_tree_35.column("Streak3.5_2026", width=100, anchor='center')
        for year in years_reversed:
            self.leagues_tree_35.column(f"Over3.5_{year}", width=100, anchor='center')
        self.leagues_tree_35.column("Last10_3.5_2026", width=90, anchor='center')
        self.leagues_tree_35.column("Last20_3.5_2026", width=90, anchor='center')
        self.leagues_tree_35.column("Avg3.5_2022_2025", width=110, anchor='center')
        self.leagues_tree_35.column("Diff3.5_2026_Avg", width=100, anchor='center')
        self.leagues_tree_35.column("Diff3.5_Last10_Avg", width=110, anchor='center')
        self.leagues_tree_35.column("Diff3.5_Last20_Avg", width=110, anchor='center')
        self.leagues_tree_35.column("Trend3.5", width=110, anchor='center')
        self.leagues_tree_35.column("MedianStreak3.5", width=130, anchor='center')
        self.leagues_tree_35.column("MaxStreak2022_35", width=100, anchor='center')
        self.leagues_tree_35.column("MedianStreak2022_35", width=110, anchor='center')
        self.leagues_tree_35.column("MaxStreakAll_35", width=100, anchor='center')
        self.leagues_tree_35.column("MedianStreakAll_35", width=110, anchor='center')
        self.leagues_tree_35.column("MaxStreak2022_35_Season", width=80, anchor='center')
        self.leagues_tree_35.column("MaxStreak2023_35_Season", width=80, anchor='center')
        self.leagues_tree_35.column("MaxStreak2024_35_Season", width=80, anchor='center')
        self.leagues_tree_35.column("MaxStreak2025_35_Season", width=80, anchor='center')
        self.leagues_tree_35.column("MaxStreak2026_35_Season", width=80, anchor='center')
        
        # Configure tags for coloring
        self.leagues_tree_35.tag_configure("diff_positive", background="#d4edda")  # Light green
        self.leagues_tree_35.tag_configure("diff_negative", background="#f8d7da")  # Light red
        self.leagues_tree_35.tag_configure("diff_very_negative", background="#f5c6cb")  # Darker red
        self.leagues_tree_35.tag_configure("no_data", background="#e9ecef")  # Light gray for leagues without data
        self.leagues_tree_35.tag_configure("games_today", background="#cce7ff")
        self.leagues_tree_35.tag_configure("alarm_row", background="#ffe8cc")
        self._configure_alert_tree_tags(self.leagues_tree_35)

        # Add scrollbars for 3.5 tab
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)
        
        v_scrollbar_35 = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.leagues_tree_35.yview)
        h_scrollbar_35 = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.leagues_tree_35.xview)
        self.leagues_tree_35.configure(yscrollcommand=v_scrollbar_35.set, xscrollcommand=h_scrollbar_35.set)
        
        self.leagues_tree_35.grid(row=0, column=0, sticky="nsew")
        v_scrollbar_35.grid(row=0, column=1, sticky="ns")
        h_scrollbar_35.grid(row=1, column=0, sticky="ew")
        
        self.leagues_tree_35.bind("<Double-1>", self.show_games_list)
        self.leagues_tree_35.bind("<Button-3>", self._on_right_click_league)
        self._bind_enhanced_tree(self.leagues_tree_35, "35")

    def setup_tab_45(self, parent):
        """Setup tab for 4.5 goals statistics"""
        table_frame = tk.LabelFrame(parent, text="Available Leagues - 4.5 Goals")
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Build columns: Country, ID, Name, Current Season, Games (2026), Alarm, Streak (2026), Over 4.5 for each year (2025, 2024, 2023, 2022), Last 10/20 (2026), Average (2022-2025), Diff columns
        base_columns = ["Country", "ID", "Name", "Heute", "CurrentSeason", "Games_2026", "Alarm", "Streak4.5_2026"]
        # Years in reverse order: 2026, 2025, 2024, 2023, 2022
        years_reversed = list(reversed(self.years_to_show))
        year_columns = []
        for year in years_reversed:
            year_columns.append(f"Over4.5_{year}")
        year_columns.extend(["Last10_4.5_2026", "Last20_4.5_2026", "Avg4.5_2022_2025", "Diff4.5_2026_Avg", "Diff4.5_Last10_Avg", "Diff4.5_Last20_Avg", "Trend4.5", "MedianStreak4.5",
                            "MaxStreak2022_45", "MedianStreak2022_45", "MaxStreakAll_45", "MedianStreakAll_45",
                            "MaxStreak2022_45_Season", "MaxStreak2023_45_Season", "MaxStreak2024_45_Season", "MaxStreak2025_45_Season", "MaxStreak2026_45_Season", "MaxOfMax4.5"])
        all_columns = tuple(base_columns + year_columns)
        
        self.leagues_tree_45 = ttk.Treeview(table_frame, columns=all_columns, show="headings", height=10)
        self.leagues_tree_45.sort_column = None
        self.leagues_tree_45.sort_reverse = False
        self.leagues_tree_45.heading("Country", text="Country")
        self.leagues_tree_45.heading("ID", text="League ID")
        self.leagues_tree_45.heading("Name", text="League Name")
        self.leagues_tree_45.heading("Heute", text="Heute Spi.")
        self.leagues_tree_45.heading("CurrentSeason", text="Current Season")
        self.leagues_tree_45.heading("Games_2026", text="Total Games (2026)")
        self.leagues_tree_45.heading("Alarm", text="Alarm")
        self.leagues_tree_45.heading("Streak4.5_2026", text="Streak 4.5 (2026)")
        
        # Add Over 4.5 for each year in reverse order: 2025, 2024, 2023, 2022
        for year in years_reversed:
            self.leagues_tree_45.heading(f"Over4.5_{year}", text=f"Over 4.5 ({year})")
        self.leagues_tree_45.heading("Last10_4.5_2026", text="Last 10 (2026)")
        self.leagues_tree_45.heading("Last20_4.5_2026", text="Last 20 (2026)")
        self.leagues_tree_45.heading("Avg4.5_2022_2025", text=self._avg_heading("4.5"))
        self.leagues_tree_45.heading("Diff4.5_2026_Avg", text="Diff (2026-Avg)")
        self.leagues_tree_45.heading("Diff4.5_Last10_Avg", text="Diff (Last10-Avg)")
        self.leagues_tree_45.heading("Diff4.5_Last20_Avg", text="Diff (Last20-Avg)")
        self.leagues_tree_45.heading("Trend4.5", text="Trend")
        self.leagues_tree_45.heading("MedianStreak4.5", text=self._avg_heading("Streak").replace("Avg ", "Median "))
        self.leagues_tree_45.heading("MaxStreak2022_45", text="Max Streak (2022)")
        self.leagues_tree_45.heading("MedianStreak2022_45", text="Median Streak (2022)")
        self.leagues_tree_45.heading("MaxStreakAll_45", text="Max Streak (All)")
        self.leagues_tree_45.heading("MedianStreakAll_45", text="Median Streak (All)")
        self.leagues_tree_45.heading("MaxStreak2022_45_Season", text="Max 2022")
        self.leagues_tree_45.heading("MaxStreak2023_45_Season", text="Max 2023")
        self.leagues_tree_45.heading("MaxStreak2024_45_Season", text="Max 2024")
        self.leagues_tree_45.heading("MaxStreak2025_45_Season", text="Max 2025")
        self.leagues_tree_45.heading("MaxStreak2026_45_Season", text="Max 2026")
        self.leagues_tree_45.heading("MaxOfMax4.5", text="Max of Max 4.5")
        
        # Bind heading clicks for sorting
        for col in all_columns:
            self.leagues_tree_45.heading(col, command=lambda c=col: self.sort_tree(self.leagues_tree_45, c))
        
        self.leagues_tree_45.column("Country", width=100)
        self.leagues_tree_45.column("ID", width=80, anchor='center')
        self.leagues_tree_45.column("Name", width=200)
        self.leagues_tree_45.column("Heute", width=88, anchor="center")
        self.leagues_tree_45.column("CurrentSeason", width=100, anchor='center')
        self.leagues_tree_45.column("Games_2026", width=110, anchor='center')
        self.leagues_tree_45.column("Alarm", width=80, anchor='center')
        self.leagues_tree_45.column("Streak4.5_2026", width=100, anchor='center')
        for year in years_reversed:
            self.leagues_tree_45.column(f"Over4.5_{year}", width=100, anchor='center')
        self.leagues_tree_45.column("Last10_4.5_2026", width=90, anchor='center')
        self.leagues_tree_45.column("Last20_4.5_2026", width=90, anchor='center')
        self.leagues_tree_45.column("Avg4.5_2022_2025", width=110, anchor='center')
        self.leagues_tree_45.column("Diff4.5_2026_Avg", width=100, anchor='center')
        self.leagues_tree_45.column("Diff4.5_Last10_Avg", width=110, anchor='center')
        self.leagues_tree_45.column("Diff4.5_Last20_Avg", width=110, anchor='center')
        self.leagues_tree_45.column("Trend4.5", width=110, anchor='center')
        self.leagues_tree_45.column("MedianStreak4.5", width=130, anchor='center')
        self.leagues_tree_45.column("MaxOfMax4.5", width=120, anchor='center')
        
        # Configure tags for coloring
        self.leagues_tree_45.tag_configure("diff_positive", background="#d4edda")  # Light green
        self.leagues_tree_45.tag_configure("diff_negative", background="#f8d7da")  # Light red
        self.leagues_tree_45.tag_configure("diff_very_negative", background="#f5c6cb")  # Darker red
        self.leagues_tree_45.tag_configure("no_data", background="#e9ecef")  # Light gray for leagues without data
        self.leagues_tree_45.tag_configure("games_today", background="#cce7ff")
        self.leagues_tree_45.tag_configure("alarm_row", background="#ffe8cc")
        self._configure_alert_tree_tags(self.leagues_tree_45)

        self.leagues_tree_45.pack(fill=tk.BOTH, expand=True)
        self.leagues_tree_45.bind("<Double-1>", self.show_games_list)
        self.leagues_tree_45.bind("<Button-3>", self._on_right_click_league)
        self._bind_enhanced_tree(self.leagues_tree_45, "45")
    
    def setup_tab_current_seasons(self, parent):
        """Setup tab for leagues with current seasons (2026+)"""
        table_frame = tk.LabelFrame(parent, text="Ligen mit aktuellen Saisons (2026+)")
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # Build columns: Country, ID, Name, Current Season, Games (Current Season), Over 2.5/3.5/4.5 (Current Season)
        base_columns = ["Country", "ID", "Name", "Heute", "CurrentSeason", "Games_Current", "Over2.5_Current", "Over3.5_Current", "Over4.5_Current"]
        all_columns = tuple(base_columns)
        
        self.leagues_tree_current = ttk.Treeview(table_frame, columns=all_columns, show="headings", height=10)
        self.leagues_tree_current.sort_column = None
        self.leagues_tree_current.sort_reverse = False
        
        self.leagues_tree_current.heading("Country", text="Country")
        self.leagues_tree_current.heading("ID", text="League ID")
        self.leagues_tree_current.heading("Name", text="League Name")
        self.leagues_tree_current.heading("Heute", text="Heute Spi.")
        self.leagues_tree_current.heading("CurrentSeason", text="Current Season")
        self.leagues_tree_current.heading("Games_Current", text="Games")
        self.leagues_tree_current.heading("Over2.5_Current", text="Over 2.5")
        self.leagues_tree_current.heading("Over3.5_Current", text="Over 3.5")
        self.leagues_tree_current.heading("Over4.5_Current", text="Over 4.5")
        
        # Bind heading clicks for sorting
        for col in all_columns:
            self.leagues_tree_current.heading(col, command=lambda c=col: self.sort_tree(self.leagues_tree_current, c))
        
        self.leagues_tree_current.column("Country", width=100)
        self.leagues_tree_current.column("ID", width=80, anchor='center')
        self.leagues_tree_current.column("Name", width=200)
        self.leagues_tree_current.column("Heute", width=88, anchor="center")
        self.leagues_tree_current.column("CurrentSeason", width=100, anchor='center')
        self.leagues_tree_current.column("Games_Current", width=80, anchor='center')
        self.leagues_tree_current.column("Over2.5_Current", width=80, anchor='center')
        self.leagues_tree_current.column("Over3.5_Current", width=80, anchor='center')
        self.leagues_tree_current.column("Over4.5_Current", width=80, anchor='center')
        
        # Add scrollbars
        v_scrollbar_current = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.leagues_tree_current.yview)
        h_scrollbar_current = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.leagues_tree_current.xview)
        self.leagues_tree_current.configure(yscrollcommand=v_scrollbar_current.set, xscrollcommand=h_scrollbar_current.set)
        self.leagues_tree_current.tag_configure("games_today", background="#cce7ff")

        # Pack scrollbars and treeview
        self.leagues_tree_current.grid(row=0, column=0, sticky="nsew")
        v_scrollbar_current.grid(row=0, column=1, sticky="ns")
        h_scrollbar_current.grid(row=1, column=0, sticky="ew")
        
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)
        
        self.leagues_tree_current.bind("<Double-1>", self.show_games_list)
        self.leagues_tree_current.bind("<Button-3>", self._on_right_click_league)
    
    def _calculate_streak_stats(self, games, threshold='25', count_under=True):
        """
        Calculate streak statistics for Under X.5 goals from a list of games.
        Games should be ordered by date (oldest first).
        
        Args:
            games: List of game dictionaries with over_25, over_35, over_45 values
            threshold: '25', '35', or '45' for 2.5, 3.5, or 4.5
            count_under: If True, count Under streaks (default). If False, count Over streaks.
        
        Returns: (max_streak, min_streak, median_streak, all_streaks)
        """
        if not games:
            return 0, 0, 0.0, []
        
        all_streaks = []
        current_streak = 0
        
        for game in games:
            if threshold == '25':
                over_value = game.get('over_25', 0) if isinstance(game, dict) else (game[0] if len(game) > 0 else 0)
            elif threshold == '35':
                over_value = game.get('over_35', 0) if isinstance(game, dict) else (game[1] if len(game) > 1 else 0)
            elif threshold == '45':
                over_value = game.get('over_45', 0) if isinstance(game, dict) else (game[2] if len(game) > 2 else 0)
            else:
                over_value = 0
            
            # Handle None values
            if over_value is None:
                over_value = 0
            
            if count_under:
                # Count Under streaks: if over_value == 0 (Under), continue streak
                if over_value == 0:  # Under X.5 - continue streak
                    current_streak += 1
                else:  # Over X.5 - streak ends
                    if current_streak > 0:
                        all_streaks.append(current_streak)
                    current_streak = 0
            else:
                # Count Over streaks: if over_value == 1 (Over), continue streak
                if over_value == 1:  # Over X.5 - continue streak
                    current_streak += 1
                else:  # Under X.5 - streak ends
                    if current_streak > 0:
                        all_streaks.append(current_streak)
                    current_streak = 0
        
        # Don't forget the last streak if it ends with the counted type
        if current_streak > 0:
            all_streaks.append(current_streak)
        
        if not all_streaks:
            return 0, 0, 0.0, []
        
        max_streak = max(all_streaks)
        min_streak = min(all_streaks)
        median_streak = statistics.median(all_streaks) if all_streaks else 0.0
        
        return max_streak, min_streak, median_streak, all_streaks
    
    def setup_tab_max_streaks(self, parent):
        """Setup tab for displaying max streaks for selected season"""
        # Season selection frame
        selection_frame = tk.Frame(parent)
        selection_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(selection_frame, text="Season auswählen:", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=5)
        
        self.max_streaks_season_var = tk.StringVar(value=self.years_to_show[0] if self.years_to_show else "2026")
        season_combo = ttk.Combobox(selection_frame, textvariable=self.max_streaks_season_var, 
                                    values=list(self.years_to_show), 
                                    state="readonly", width=10)
        season_combo.pack(side=tk.LEFT, padx=5)
        season_combo.bind("<<ComboboxSelected>>", lambda e: self.load_max_streaks())
        
        table_frame = tk.LabelFrame(parent, text="Max Streaks (2.5, 3.5, 4.5 Goals)")
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # Build columns: Country, ID, Name, Max 2.5, Max 3.5, Max 4.5, Median 2.5, Median 3.5, Median 4.5, Max of Max 2.5, Max of Max 3.5, Max of Max 4.5
        columns = ("Country", "ID", "Name", "Max2.5", "Max3.5", "Max4.5", "Median2.5", "Median3.5", "Median4.5", "MaxOfMax2.5", "MaxOfMax3.5", "MaxOfMax4.5")
        
        self.leagues_tree_max_streaks = ttk.Treeview(table_frame, columns=columns, show="headings", height=15)
        self.leagues_tree_max_streaks.sort_column = None
        self.leagues_tree_max_streaks.sort_reverse = False
        
        # Configure headings - MUST be done before inserting data
        self.leagues_tree_max_streaks.heading("Country", text="Land")
        self.leagues_tree_max_streaks.heading("ID", text="League ID")
        self.leagues_tree_max_streaks.heading("Name", text="Liga Name")
        self.leagues_tree_max_streaks.heading("Max2.5", text="Max 2.5")
        self.leagues_tree_max_streaks.heading("Max3.5", text="Max 3.5")
        self.leagues_tree_max_streaks.heading("Max4.5", text="Max 4.5")
        self.leagues_tree_max_streaks.heading("Median2.5", text="Median 2.5")
        self.leagues_tree_max_streaks.heading("Median3.5", text="Median 3.5")
        self.leagues_tree_max_streaks.heading("Median4.5", text="Median 4.5")
        self.leagues_tree_max_streaks.heading("MaxOfMax2.5", text="Max of Max 2.5")
        self.leagues_tree_max_streaks.heading("MaxOfMax3.5", text="Max of Max 3.5")
        self.leagues_tree_max_streaks.heading("MaxOfMax4.5", text="Max of Max 4.5")
        
        # Configure column widths and anchors - MUST be done before inserting data
        self.leagues_tree_max_streaks.column("Country", width=120, anchor='w')
        self.leagues_tree_max_streaks.column("ID", width=80, anchor='center')
        self.leagues_tree_max_streaks.column("Name", width=300, anchor='w')
        self.leagues_tree_max_streaks.column("Max2.5", width=100, anchor='center')
        self.leagues_tree_max_streaks.column("Max3.5", width=100, anchor='center')
        self.leagues_tree_max_streaks.column("Max4.5", width=100, anchor='center')
        self.leagues_tree_max_streaks.column("Median2.5", width=100, anchor='center')
        self.leagues_tree_max_streaks.column("Median3.5", width=100, anchor='center')
        self.leagues_tree_max_streaks.column("Median4.5", width=100, anchor='center')
        self.leagues_tree_max_streaks.column("MaxOfMax2.5", width=120, anchor='center')
        self.leagues_tree_max_streaks.column("MaxOfMax3.5", width=120, anchor='center')
        self.leagues_tree_max_streaks.column("MaxOfMax4.5", width=120, anchor='center')
        
        # Bind heading clicks for sorting
        for col in columns:
            self.leagues_tree_max_streaks.heading(col, command=lambda c=col: self.sort_tree(self.leagues_tree_max_streaks, c))
        
        # Configure tags for highlighting highest streaks
        self.leagues_tree_max_streaks.tag_configure("highest_25", background="#fff3cd")  # Light yellow
        self.leagues_tree_max_streaks.tag_configure("highest_35", background="#d1ecf1")  # Light blue
        self.leagues_tree_max_streaks.tag_configure("highest_45", background="#d4edda")  # Light green
        
        # Add scrollbars
        v_scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.leagues_tree_max_streaks.yview)
        h_scrollbar = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.leagues_tree_max_streaks.xview)
        self.leagues_tree_max_streaks.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Pack scrollbars and treeview
        self.leagues_tree_max_streaks.grid(row=0, column=0, sticky="nsew")
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar.grid(row=1, column=0, sticky="ew")
        
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)
        
        # Bind double-click to show games for selected season
        self.leagues_tree_max_streaks.bind("<Double-1>", self.show_games_list_max_streaks)
        self.leagues_tree_max_streaks.bind("<Button-3>", self._on_right_click_league)
        
        # Load data after a short delay to ensure UI is ready
        self.after(100, self.load_max_streaks)
    
    def load_max_streaks(self):
        """Load and display max streaks for selected season"""
        try:
            # Check if UI is ready
            if not hasattr(self, 'leagues_tree_max_streaks'):
                print("[DEBUG] leagues_tree_max_streaks not ready, retrying...")
                self.after(100, self.load_max_streaks)
                return
            
            from database import DatabaseManager
            db_manager = DatabaseManager("data/flashscore.db")
            conn = db_manager.get_connection()
            
            # Clear existing items
            for item in self.leagues_tree_max_streaks.get_children():
                self.leagues_tree_max_streaks.delete(item)
            
            # Get selected season
            try:
                selected_season = self.max_streaks_season_var.get()
                season_year = int(selected_season)
            except (ValueError, AttributeError):
                season_year = 2022  # Default to 2022
                print(f"[DEBUG] Using default season 2022")
            
            print(f"[DEBUG] Loading max streaks for season {season_year}")
            
            # Get all distinct leagues with games in selected season
            leagues = conn.execute("""
                SELECT DISTINCT 
                    league_id,
                    COALESCE(league_name, 'Unknown League') as league_name,
                    COALESCE(country_name, 'Unknown') as country_name
                FROM games
                WHERE league_id IS NOT NULL
                  AND season_year = ?
                ORDER BY country_name, league_name
            """, (season_year,)).fetchall()
            
            if not leagues:
                return
            
            results = []
            max_25_value = 0
            max_35_value = 0
            max_45_value = 0
            
            # Calculate streaks for each league
            for league in leagues:
                league_id, league_name, country_name = league
                
                # First, calculate max streaks for all years (2022-2025) to find max_of_max
                max_of_max_25 = 0
                max_of_max_35 = 0
                max_of_max_45 = 0
                
                # Calculate max streaks for each year (2022-2025)
                for year in [int(y) for y in self.years_to_show]:
                    year_games_data = conn.execute("""
                        SELECT total_goals
                        FROM games
                        WHERE league_id = ?
                          AND season_year = ?
                          AND status IN (7, 8, 9, 10)  -- Finished games only
                        ORDER BY date DESC
                    """, (league_id, year)).fetchall()
                    
                    if not year_games_data:
                        continue
                    
                    # Calculate max streak for this year
                    year_max_25 = 0
                    year_max_35 = 0
                    year_max_45 = 0
                    
                    current_streak_25 = 0
                    current_streak_35 = 0
                    current_streak_45 = 0
                    
                    for row in year_games_data:
                        total_goals = row[0] if row[0] is not None else 0
                        
                        if total_goals <= 2:
                            current_streak_25 += 1
                            if current_streak_25 > year_max_25:
                                year_max_25 = current_streak_25
                        else:
                            current_streak_25 = 0
                        
                        if total_goals <= 3:
                            current_streak_35 += 1
                            if current_streak_35 > year_max_35:
                                year_max_35 = current_streak_35
                        else:
                            current_streak_35 = 0
                        
                        if total_goals <= 4:
                            current_streak_45 += 1
                            if current_streak_45 > year_max_45:
                                year_max_45 = current_streak_45
                        else:
                            current_streak_45 = 0
                    
                    # Update max_of_max values
                    if year_max_25 > max_of_max_25:
                        max_of_max_25 = year_max_25
                    if year_max_35 > max_of_max_35:
                        max_of_max_35 = year_max_35
                    if year_max_45 > max_of_max_45:
                        max_of_max_45 = year_max_45
                
                # Get all games for this league in selected season, ordered by date DESC (neueste zuerst)
                # Same logic as in Finished Games window - count streaks in reverse (from newest to oldest)
                games_data = conn.execute("""
                    SELECT total_goals, over_25, over_35, over_45
                    FROM games
                    WHERE league_id = ?
                      AND season_year = ?
                      AND status IN (7, 8, 9, 10)  -- Finished games only
                    ORDER BY date DESC
                """, (league_id, season_year)).fetchall()
                
                if not games_data:
                    continue
                
                # Calculate max streaks: find the longest consecutive sequence of Under X.5 games
                # Count how many games in a row ended with <= X.5 goals (from newest to oldest - "in Folge")
                # Under 2.5 = total_goals <= 2 (0, 1, or 2 goals)
                # Under 3.5 = total_goals <= 3 (0, 1, 2, or 3 goals)
                # Under 4.5 = total_goals <= 4 (0, 1, 2, 3, or 4 goals)
                max_25 = 0
                max_35 = 0
                max_45 = 0
                
                current_streak_25 = 0
                current_streak_35 = 0
                current_streak_45 = 0
                
                # For median calculation: track all streak sequence maxima
                streak_maxima_25 = []
                streak_maxima_35 = []
                streak_maxima_45 = []
                
                current_max_25 = 0
                current_max_35 = 0
                current_max_45 = 0
                
                # Count streaks from newest to oldest (in Folge)
                for row in games_data:
                    total_goals = row[0] if row[0] is not None else 0
                    
                    # Under 2.5 streak: count consecutive games that ended with <= 2 goals (0, 1, or 2 goals)
                    if total_goals <= 2:
                        current_streak_25 += 1
                        if current_streak_25 > max_25:
                            max_25 = current_streak_25
                        if current_streak_25 > current_max_25:
                            current_max_25 = current_streak_25
                    else:
                        # Streak ends when a game has 3+ goals
                        # Save the maximum of the previous streak sequence
                        if current_max_25 > 0:
                            streak_maxima_25.append(current_max_25)
                        current_streak_25 = 0
                        current_max_25 = 0
                    
                    # Under 3.5 streak: count consecutive games that ended with <= 3 goals (0, 1, 2, or 3 goals)
                    if total_goals <= 3:
                        current_streak_35 += 1
                        if current_streak_35 > max_35:
                            max_35 = current_streak_35
                        if current_streak_35 > current_max_35:
                            current_max_35 = current_streak_35
                    else:
                        # Streak ends when a game has 4+ goals
                        if current_max_35 > 0:
                            streak_maxima_35.append(current_max_35)
                        current_streak_35 = 0
                        current_max_35 = 0
                    
                    # Under 4.5 streak: count consecutive games that ended with <= 4 goals (0, 1, 2, 3, or 4 goals)
                    if total_goals <= 4:
                        current_streak_45 += 1
                        if current_streak_45 > max_45:
                            max_45 = current_streak_45
                        if current_streak_45 > current_max_45:
                            current_max_45 = current_streak_45
                    else:
                        # Streak ends when a game has 5+ goals
                        if current_max_45 > 0:
                            streak_maxima_45.append(current_max_45)
                        current_streak_45 = 0
                        current_max_45 = 0
                
                # Don't forget the last streak sequence if it ends with the list
                if current_max_25 > 0:
                    streak_maxima_25.append(current_max_25)
                if current_max_35 > 0:
                    streak_maxima_35.append(current_max_35)
                if current_max_45 > 0:
                    streak_maxima_45.append(current_max_45)
                
                # Calculate median of all streak maxima
                import statistics
                median_25 = statistics.median(streak_maxima_25) if streak_maxima_25 else 0
                median_35 = statistics.median(streak_maxima_35) if streak_maxima_35 else 0
                median_45 = statistics.median(streak_maxima_45) if streak_maxima_45 else 0
                
                # Ensure logical consistency: 
                # If a game is Under 3.5 (<=3 goals), it might be Over 2.5 (3 goals) or Under 2.5 (<=2 goals)
                # If a game is Under 4.5 (<=4 goals), it might be Over 3.5 (4 goals) or Under 3.5 (<=3 goals)
                # So the streaks are independent - a game can be Under 4.5 but Over 2.5
                # However, if max_25 is very high, it means many consecutive games were Under 2.5
                # Those same games would also be Under 3.5 and Under 4.5, so max_35 and max_45 should be >= max_25
                # But this is not always true because a game can be Under 3.5 but Over 2.5 (exactly 3 goals)
                # So we don't enforce strict ordering, but we ensure they make sense
                
                results.append((league_id, league_name, country_name, max_25, max_35, max_45, median_25, median_35, median_45, max_of_max_25, max_of_max_35, max_of_max_45))
                
                # Track maximum values for highlighting
                if max_25 > max_25_value:
                    max_25_value = max_25
                if max_35 > max_35_value:
                    max_35_value = max_35
                if max_45 > max_45_value:
                    max_45_value = max_45
            
            # Insert results into treeview
            for result in results:
                league_id, league_name, country_name, max_25, max_35, max_45, median_25, median_35, median_45, max_of_max_25, max_of_max_35, max_of_max_45 = result
                
                # Determine tags for highlighting
                tags = []
                if max_25 == max_25_value and max_25 > 0:
                    tags.append("highest_25")
                if max_35 == max_35_value and max_35 > 0:
                    tags.append("highest_35")
                if max_45 == max_45_value and max_45 > 0:
                    tags.append("highest_45")
                
                # Insert with all values - ensure they are strings
                # Display max streaks as positive numbers (same as Finished Games window)
                # Display median with 1 decimal place if needed
                # Display max_of_max values (constant across all seasons)
                values_tuple = (
                    str(country_name),
                    str(league_id),
                    str(league_name),
                    str(max_25) if max_25 > 0 else "",
                    str(max_35) if max_35 > 0 else "",
                    str(max_45) if max_45 > 0 else "",
                    f"{median_25:.1f}" if median_25 > 0 else "",
                    f"{median_35:.1f}" if median_35 > 0 else "",
                    f"{median_45:.1f}" if median_45 > 0 else "",
                    str(max_of_max_25) if max_of_max_25 > 0 else "",
                    str(max_of_max_35) if max_of_max_35 > 0 else "",
                    str(max_of_max_45) if max_of_max_45 > 0 else ""
                )
                
                # Apply tags for highlighting (highest streaks get colored)
                self.leagues_tree_max_streaks.insert("", tk.END, values=values_tuple, tags=tags if tags else ())
            
            print(f"[INFO] Loaded {len(results)} leagues with max streaks for season {season_year}")
            if results:
                print(f"[DEBUG] Sample result: League {results[0][0]} - Max 2.5: {results[0][3]}, Max 3.5: {results[0][4]}, Max 4.5: {results[0][5]}")
                print(f"[DEBUG] Sample result values: {results[0]}")
            
            # Verify treeview has items
            tree_items = self.leagues_tree_max_streaks.get_children()
            print(f"[DEBUG] Treeview has {len(tree_items)} items after insertion")
            if tree_items:
                first_item = self.leagues_tree_max_streaks.item(tree_items[0])
                print(f"[DEBUG] First item values: {first_item.get('values', [])}")
            
        except Exception as e:
            print(f"[ERROR] Failed to load max streaks: {e}")
            import traceback
            traceback.print_exc()
            # Show error in UI if possible
            if hasattr(self, 'status_label'):
                self.status_label.config(text=f"Fehler beim Laden der Max Streaks: {e}")

    def update_years(self):
        """Update the years to display"""
        years_str = self.year_var.get().strip()
        if years_str:
            try:
                new_years = [y.strip() for y in years_str.split(",") if y.strip()]
                if new_years:
                    self.years_to_show = new_years
                    # Rebuild UI with new years
                    self.setup_ui()
                    self.load_league_games_counts()
            except Exception as e:
                messagebox.showerror("Error", f"Invalid year format: {e}")
    
    def refresh_data(self):
        """Refresh all data: reload leagues from database and recalculate statistics"""
        def refresh_in_thread():
            try:
                # Update status
                if hasattr(self, 'status_label'):
                    self.after(0, lambda: self.status_label.config(text="Daten werden aktualisiert..."))
                    self.after(0, self.update_idletasks)
                
                # Reload leagues from database
                print("[INFO] Reloading leagues from database...")
                new_leagues = self._load_leagues_from_database()
                print(f"[INFO] Loaded {len(new_leagues)} leagues from database")
                
                # Update leagues list
                self.leagues = new_leagues
                
                # Reload and recalculate all statistics (runs in main thread via self.after)
                print("[INFO] Recalculating statistics...")
                self.after(0, self.load_league_games_counts)
                # Also refresh max streaks tab
                if hasattr(self, 'leagues_tree_max_streaks'):
                    self.after(0, self.load_max_streaks)
                
                # Show success message after a short delay to let UI update
                def show_success():
                    if hasattr(self, 'status_label'):
                        self.status_label.config(text=f"Daten aktualisiert - {len(new_leagues)} Ligen geladen")
                    messagebox.showinfo("Erfolg", f"Daten erfolgreich aktualisiert!\n{len(new_leagues)} Ligen geladen und Statistiken neu berechnet.")
                
                self.after(1000, show_success)  # Wait 1 second for data to load
                
            except Exception as e:
                error_msg = f"Fehler beim Aktualisieren der Daten: {e}"
                print(f"[ERROR] {error_msg}")
                import traceback
                traceback.print_exc()
                self.after(0, lambda: self.status_label.config(text=f"Fehler: {e}") if hasattr(self, 'status_label') else None)
                self.after(0, lambda: messagebox.showerror("Fehler", error_msg))
        
        # Run in background thread to avoid freezing UI
        thread = threading.Thread(target=refresh_in_thread, daemon=True)
        thread.start()

    def reload_league_list_from_database(self):
        """Neu laden der Liga-Liste aus der DB (z. B. nach Excel-Import), ohne API-Refresh."""
        try:
            self.leagues = self._load_leagues_from_database()
            if getattr(self, "leagues_tree_25", None):
                self.load_league_games_counts()
            if hasattr(self, "leagues_tree_max_streaks"):
                self.load_max_streaks()
        except Exception as e:
            print(f"[ERROR] reload_league_list_from_database: {e}")
    
    def _ensure_data_loaded(self):
        """Fallback method to ensure data is loaded"""
        if not hasattr(self, 'leagues_tree_25') or not self.leagues_tree_25.get_children():
            print("[DEBUG] Fallback: Treeviews are empty, trying to load data again")
            if hasattr(self, 'status_label') and self.leagues:
                self.load_league_games_counts()
    
    def _calculate_alarm(self, league, metric_prefix, streak_key):
        """
        Calculate alarm based on multiple factors to detect 'Tiefpunkt' (low point).
        
        A "Tiefpunkt" means many games ended under X.5 goals, which indicates:
        - Low "Over X.5" percentage = many games under X.5
        - This could be a good time to bet on "Over X.5" (regression to mean)
        
        Factors considered:
        1. Deviation from historical average (2026 vs avg(2022-2025))
        2. Recent trend (last10 vs last20 vs 2026)
        3. Absolute low values (very low percentages)
        4. Combined signals (multiple factors together)
        
        Returns: Alarm text (🔔 for strong signal, ⚠ for moderate signal, or empty)
        """
        def parse_percent(val):
            """Parse percentage value from string or number"""
            if isinstance(val, str) and val != "Error" and val.endswith("%"):
                try:
                    return float(val.rstrip("%"))
                except ValueError:
                    return None
            elif isinstance(val, (int, float)) and val != "Error":
                return float(val)
            return None
        
        # Get current year (2026 / Saison 26/27)
        current_year = "2026"
        
        # Parse values
        val_last10 = parse_percent(league.get(f"last10_{metric_prefix}_{current_year}", 0))
        val_last20 = parse_percent(league.get(f"last20_{metric_prefix}_{current_year}", 0))
        val_current = parse_percent(league.get(f"{metric_prefix}_{current_year}", 0))
        
        # Calculate avg(2022-2025)
        avg_years = self._history_years()
        avg_values = []
        for year in avg_years:
            val = league.get(f"{metric_prefix}_{year}", 0)
            parsed = parse_percent(val)
            if parsed is not None:
                avg_values.append(parsed)
        
        avg_hist = sum(avg_values) / len(avg_values) if avg_values else None
        
        # If we don't have enough data, no alarm
        if val_last10 is None or val_current is None or avg_hist is None:
            return ""
        
        # Calculate score based on multiple factors
        score = 0
        
        # Factor 1: Current value is significantly below historical average
        # This indicates a "Tiefpunkt" - many games under X.5
        deviation = avg_hist - val_current
        if deviation > 20:  # More than 20% below average (very significant)
            score += 4
        elif deviation > 15:  # More than 15% below average
            score += 3
        elif deviation > 10:  # More than 10% below average
            score += 2
        elif deviation > 5:  # More than 5% below average
            score += 1
        
        # Factor 2: Recent trend is declining (last10 < last20 < 2026)
        # This shows a clear downward trend
        if val_last20 is not None:
            if val_last10 < val_last20 and val_last20 < val_current:
                score += 3  # Strong declining trend
            elif val_last10 < val_current:
                score += 2  # Recent decline
            elif val_last10 < val_last20:
                score += 1  # Slight decline
        
        # Factor 3: Last 10 games are very low (strong recent signal)
        # Very low percentage in recent games indicates current "Tiefpunkt"
        if val_last10 < 25:  # Less than 25% over X.5 in last 10 games (very low)
            score += 3
        elif val_last10 < 35:  # Less than 35%
            score += 2
        elif val_last10 < 45:  # Less than 45%
            score += 1
        
        # Factor 4: Current season is significantly below average AND last 10 is even lower
        # This is a strong "Tiefpunkt" signal - season is low AND getting lower
        if val_current < avg_hist and val_last10 < val_current:
            score += 3  # Strong signal: below average and declining
        
        # Factor 5: Very low overall percentage (below 40%)
        # Absolute low value indicates many games under X.5
        if val_current < 35:  # Very low overall
            score += 2
        elif val_current < 45:  # Low overall
            score += 1
        
        # Factor 6: Combined strong signals
        # If multiple factors align, increase score
        if deviation > 15 and val_last10 < 35:
            score += 1  # Bonus for multiple strong signals
        
        # Determine alarm level based on score
        # Higher score = stronger "Tiefpunkt" signal = better time to bet on "Over X.5"
        if score >= 8:  # Very strong signal
            return "🔔"  # Strong alarm - good betting opportunity
        elif score >= 5:  # Moderate to strong signal
            return "⚠"  # Warning - potential opportunity
        else:
            return ""  # No alarm

    def _get_today_upcoming_counts(self):
        """Noch ausstehende Spiele mit heutigem Datum je Liga (ohne bereits beendete)."""
        counts = {}
        try:
            from database import DatabaseManager
            import sqlite3
            from datetime import datetime

            today_str = datetime.now().strftime("%Y-%m-%d")
            db_manager = DatabaseManager("data/flashscore.db")
            conn = db_manager.get_connection()
            conn.row_factory = sqlite3.Row
            pending = SQL_FILTER_STILL_PENDING

            rows = conn.execute(
                f"""
                SELECT league_id, COUNT(*) AS cnt FROM (
                    SELECT league_id, id FROM upcoming_games
                    WHERE league_id IS NOT NULL
                      AND substr(date, 1, 10) = ?
                      {pending}
                    UNION
                    SELECT league_id, id FROM games
                    WHERE league_id IS NOT NULL
                      AND substr(date, 1, 10) = ?
                      {pending}
                ) AS today_rows
                GROUP BY league_id
                """,
                (today_str, today_str),
            ).fetchall()

            for row in rows:
                counts[int(row["league_id"])] = int(row["cnt"] or 0)
        except Exception as e:
            print(f"[WARNING] Could not load today's game counts per league: {e}")
        return counts

    def _format_alarm_with_today(self, alarm_text, today_count):
        """Nur noch Alarm; Heute-Zähler steht in eigener Spalte „heute“."""
        return alarm_text or ""

    def _today_games_cell_label(self, today_count):
        """Klartext Ja + Anzahl offener Spiele heute, sonst Gedankenstrich."""
        try:
            n = int(today_count)
        except (TypeError, ValueError):
            return ""
        if n <= 0:
            return "—"
        if n == 1:
            return "Ja · 1"
        return f"Ja · {n}"

    def _load_today_upcoming_games(self, conn, league_id):
        """Heutige Partien der Liga, die noch nicht beendet sind."""
        from datetime import datetime

        today_str = datetime.now().strftime("%Y-%m-%d")
        pending = SQL_FILTER_STILL_PENDING
        rows = conn.execute(
            f"""
            SELECT id, date, home_team_name, away_team_name, status_name, round_name,
                   status, home_ft_result, away_ft_result, updated_at
            FROM (
                SELECT id, date, home_team_name, away_team_name, status_name, round_name,
                       status, home_ft_result, away_ft_result, updated_at
                FROM upcoming_games
                WHERE league_id = ?
                  AND substr(date, 1, 10) = ?
                  {pending}
                UNION
                SELECT id, date, home_team_name, away_team_name, status_name, round_name,
                       status, home_ft_result, away_ft_result, updated_at
                FROM games
                WHERE league_id = ?
                  AND substr(date, 1, 10) = ?
                  {pending}
            ) AS merged_today
            ORDER BY date ASC
            """,
            (league_id, today_str, league_id, today_str),
        ).fetchall()
        return list(rows)

    def _create_today_games_tab(self, tab, today_games, league_name):
        """Create table with today's upcoming games for selected league."""
        frame = tk.Frame(tab)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        if not today_games:
            info = tk.Label(
                frame,
                text=(
                    f"Für {league_name} sind heute keine offenen Partien mehr in der Datenbank "
                    f"(alle beendet oder kein Termin heute)."
                ),
                fg="gray",
                font=("Arial", 11),
                wraplength=640,
                justify="left",
            )
            info.pack(pady=20)
            return

        cols = ("ID", "Date", "Home", "Away", "Round", "Status")
        tree = ttk.Treeview(frame, columns=cols, show="headings")
        for col in cols:
            tree.heading(col, text=col)
        tree.column("ID", width=90, anchor="center")
        tree.column("Date", width=150, anchor="center")
        tree.column("Home", width=220)
        tree.column("Away", width=220)
        tree.column("Round", width=140, anchor="center")
        tree.column("Status", width=120, anchor="center")

        scroll_y = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll_y.set)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        for row in today_games:
            date_val = row["date"] or ""
            if date_val and "T" in str(date_val):
                try:
                    dt = datetime.fromisoformat(str(date_val).replace("Z", "+00:00"))
                    date_val = dt.strftime("%Y-%m-%d %H:%M")
                except Exception:
                    pass
            tree.insert(
                "",
                tk.END,
                values=(
                    row["id"],
                    date_val,
                    row["home_team_name"] or "",
                    row["away_team_name"] or "",
                    row["round_name"] or "",
                    row["status_name"] or "",
                ),
            )
    
    def load_league_games_counts(self):
        """Load the number of games for each league for all specified years"""
        print("[DEBUG] load_league_games_counts called")
        try:
            if not hasattr(self, 'status_label'):
                # UI not ready yet, try again later
                print("[DEBUG] status_label not ready, retrying in 100ms")
                self.after(100, self.load_league_games_counts)
                return
            
            if not self.leagues:
                self.status_label.config(text="Keine Ligen gefunden - Datenbank prüfen")
                print("[WARNING] Keine Ligen geladen - möglicherweise ist die Datenbank leer oder nicht erreichbar")
                print("[DEBUG] self.leagues is empty, returning early")
                return
            
            print(f"[DEBUG] About to load data for {len(self.leagues)} leagues")
            
            self.status_label.config(text=f"Loading games counts for years {', '.join(self.years_to_show)}...")
            self.update_idletasks()  # Update UI to show status
            
            print(f"[DEBUG] Loading data for {len(self.leagues)} leagues")
            
            if len(self.leagues) == 0:
                print("[WARNING] Keine Ligen zum Laden vorhanden!")
                self.status_label.config(text="Keine Ligen gefunden")
                return
            
            skip_fetch = bool(getattr(self, "_skip_db_reload_once", False))
            self._skip_db_reload_once = False

            # Load data for all years (skip when only re-applying display filters)
            if not skip_fetch:
              for league in self.leagues:
                # Initialize year-specific data
                for year in self.years_to_show:
                    league[f"games_{year}"] = 0
                    league[f"over25_{year}"] = 0
                    league[f"over35_{year}"] = 0
                    league[f"over45_{year}"] = 0
                    league[f"last10_over25_{year}"] = 0
                    league[f"last10_over35_{year}"] = 0
                    league[f"last10_over45_{year}"] = 0
                    league[f"last20_over25_{year}"] = 0
                    league[f"last20_over35_{year}"] = 0
                    league[f"last20_over45_{year}"] = 0
                    league[f"streak25_{year}"] = 0
                    league[f"streak35_{year}"] = 0
                    league[f"streak45_{year}"] = 0
                
                # Calculate max streaks live from games (DB year-columns were often empty/missing)
                try:
                    from database import DatabaseManager
                    import sqlite3
                    db_manager = DatabaseManager("data/flashscore.db")
                    conn = db_manager.get_connection()
                    
                    max_of_max_25 = 0
                    max_of_max_35 = 0
                    max_of_max_45 = 0
                    
                    for year in [int(y) for y in self.years_to_show]:
                        year_games_data = conn.execute("""
                            SELECT total_goals
                            FROM games
                            WHERE league_id = ?
                              AND season_year = ?
                              AND status IN (7, 8, 9, 10)
                            ORDER BY date ASC
                        """, (league["id"], year)).fetchall()
                        
                        year_max_25 = 0
                        year_max_35 = 0
                        year_max_45 = 0
                        current_streak_25 = 0
                        current_streak_35 = 0
                        current_streak_45 = 0

                        if year_games_data:
                            for row in year_games_data:
                                total_goals = row[0] if row[0] is not None else 0
                                
                                if total_goals <= 2:
                                    current_streak_25 += 1
                                    year_max_25 = max(year_max_25, current_streak_25)
                                else:
                                    current_streak_25 = 0
                                
                                if total_goals <= 3:
                                    current_streak_35 += 1
                                    year_max_35 = max(year_max_35, current_streak_35)
                                else:
                                    current_streak_35 = 0
                                
                                if total_goals <= 4:
                                    current_streak_45 += 1
                                    year_max_45 = max(year_max_45, current_streak_45)
                                else:
                                    current_streak_45 = 0
                        
                        # Always store season max (0 if no games) so UI is never stuck on empty DB cols
                        league[f"max_streak_{year}_25_season"] = year_max_25
                        league[f"max_streak_{year}_35_season"] = year_max_35
                        league[f"max_streak_{year}_45_season"] = year_max_45

                        max_of_max_25 = max(max_of_max_25, year_max_25)
                        max_of_max_35 = max(max_of_max_35, year_max_35)
                        max_of_max_45 = max(max_of_max_45, year_max_45)
                    
                    league["max_of_max_25"] = max_of_max_25
                    league["max_of_max_35"] = max_of_max_35
                    league["max_of_max_45"] = max_of_max_45
                    # Summary fields for table / tooltip (live from games)
                    league["max_streak_2022"] = league.get("max_streak_2022_25_season", 0) or 0
                    league["max_streak_all"] = max_of_max_25
                    league["max_streak_2022_35"] = league.get("max_streak_2022_35_season", 0) or 0
                    league["max_streak_all_35"] = max_of_max_35
                    league["max_streak_2022_45"] = league.get("max_streak_2022_45_season", 0) or 0
                    league["max_streak_all_45"] = max_of_max_45
                except Exception as e:
                    print(f"[WARNING] Could not calculate max_of_max for league {league['id']}: {e}")
                    league["max_of_max_25"] = 0
                    league["max_of_max_35"] = 0
                    league["max_of_max_45"] = 0
                
                # Load data for each year
                for year in self.years_to_show:
                    try:
                        result = self.get_games_count_for_league(league["id"], year)
                        total_games = result["total"]
                        league[f"games_{year}"] = total_games
                        # Debug output for specific leagues
                        target_leagues = [145, 144, 39, 40, 41, 42, 135, 136, 307, 308, 303, 301]
                        if league["id"] in target_leagues and year == "2026":
                            print(f"[DEBUG] League {league['id']} ({league['name']}) - Year {year}: total={total_games}")
                        league[f"over25_{year}"] = result["over25"]
                        league[f"over35_{year}"] = result["over35"]
                        league[f"over45_{year}"] = result["over45"]
                        league[f"last10_over25_{year}"] = result["last10_over25"]
                        league[f"last10_over35_{year}"] = result["last10_over35"]
                        league[f"last10_over45_{year}"] = result["last10_over45"]
                        league[f"last20_over25_{year}"] = result["last20_over25"]
                        league[f"last20_over35_{year}"] = result["last20_over35"]
                        league[f"last20_over45_{year}"] = result["last20_over45"]
                        league[f"streak25_{year}"] = result["streak25"]
                        league[f"streak35_{year}"] = result["streak35"]
                        league[f"streak45_{year}"] = result["streak45"]
                    except Exception as e:
                        print(f"Error loading games for league {league['id']} year {year}: {e}")
                        import traceback
                        traceback.print_exc()
                        league[f"games_{year}"] = "Error"
                        league[f"over25_{year}"] = "Error"
                        league[f"over35_{year}"] = "Error"
                        league[f"over45_{year}"] = "Error"
                        league[f"last10_over25_{year}"] = "Error"
                        league[f"last10_over35_{year}"] = "Error"
                        league[f"last10_over45_{year}"] = "Error"
                        league[f"last20_over25_{year}"] = "Error"
                        league[f"last20_over35_{year}"] = "Error"
                        league[f"last20_over45_{year}"] = "Error"
                        league[f"streak25_{year}"] = "Error"
                        league[f"streak35_{year}"] = "Error"
                        league[f"streak45_{year}"] = "Error"
            
            # Check if treeviews exist
            if not hasattr(self, 'leagues_tree_25') or not hasattr(self, 'leagues_tree_35') or not hasattr(self, 'leagues_tree_45') or not hasattr(self, 'leagues_tree_current'):
                print("[ERROR] Treeviews not initialized! Retrying in 200ms")
                self.after(200, self.load_league_games_counts)
                return
            
            # Load today's upcoming matches per league for overview markers.
            self._today_upcoming_counts = self._get_today_upcoming_counts()

            # Update tab 2.5
            years_reversed = list(reversed(self.years_to_show))  # 2025, 2024, 2023, 2022
            print(f"[DEBUG] Updating tab 2.5 with {len(self.leagues)} leagues")
            for item in self.leagues_tree_25.get_children():
                self.leagues_tree_25.delete(item)
            inserted_count_25 = 0
            for league in self.leagues:
                if not self._league_passes_display_filter(league, "over25", "streak25_2026"):
                    continue
                # Build values list - make sure we have the right number of values
                # Get current season for this league
                league_id = league.get("id")
                current_season = self.current_seasons.get(league_id, 2026)
                
                # Check if league has no data
                games_2025 = league.get("games_2026", 0)
                has_data = games_2025 > 0
                
                # Mark league name if no data
                league_name_display = league["name"]
                if not has_data:
                    league_name_display = f"{league['name']} ⚠"  # Mark with warning symbol
                
                # Calculate improved Alarm using multiple factors
                alarm_text = self._calculate_alarm(league, "over25", "streak25_2026")
                today_count = self._today_upcoming_counts.get(int(league_id), 0)
                alarm_display = self._format_alarm_display(league, "over25")
                median_ref, max_ref = self._streak_refs_for_metric(league, "25")
                streak_display = format_streak_cell(league.get("streak25_2026", 0), median_ref, max_ref)
                
                values = [
                    league["country"], 
                    league["id"], 
                    league_name_display,  # Use marked name if no data
                    self._today_games_cell_label(today_count),
                    current_season,  # Current Season column
                    games_2025,  # Total Games from 2026
                    alarm_display,  # Alarm column
                    streak_display  # Streak right after Alarm
                ]
                
                # Add Over 2.5 for each year in reverse order (2025, 2024, 2023, 2022)
                for year in years_reversed:
                    values.append(league.get(f"over25_{year}", 0))
                # Add Last 10, Last 20 for 2026
                values.extend([
                    league.get("last10_over25_2026", 0),
                    league.get("last20_over25_2026", 0)
                ])
                # Calculate average for 2022-2025 (excluding 2026)
                avg_years = self._history_years()
                avg_values = []
                for year in avg_years:
                    val = league.get(f"over25_{year}", 0)
                    if isinstance(val, str) and val != "Error" and val.endswith("%"):
                        try:
                            avg_values.append(float(val.rstrip("%")))
                        except ValueError:
                            pass
                    elif isinstance(val, (int, float)) and val != "Error":
                        avg_values.append(float(val))
                if avg_values:
                    avg = sum(avg_values) / len(avg_values)
                    values.append(f"{avg:.1f}%")
                    avg_num = avg
                else:
                    values.append("N/A")
                    avg_num = None
                
                # Calculate differences
                def parse_percent(val):
                    if isinstance(val, str) and val != "Error" and val.endswith("%"):
                        try:
                            return float(val.rstrip("%"))
                        except ValueError:
                            return None
                    elif isinstance(val, (int, float)) and val != "Error":
                        return float(val)
                    return None
                
                # Diff (2026 - Avg)
                val_current = parse_percent_value(league.get("over25_2026", 0))
                if val_current is not None and avg_num is not None:
                    diff_2026 = val_current - avg_num
                    values.append(format_diff(diff_2026))
                else:
                    values.append("N/A")
                
                # Diff (Last10 - Avg)
                val_last10 = parse_percent_value(league.get("last10_over25_2026", 0))
                if val_last10 is not None and avg_num is not None:
                    diff_last10 = val_last10 - avg_num
                    values.append(format_diff(diff_last10))
                else:
                    values.append("N/A")
                
                # Diff (Last20 - Avg)
                val_last20 = parse_percent_value(league.get("last20_over25_2026", 0))
                if val_last20 is not None and avg_num is not None:
                    diff_last20 = val_last20 - avg_num
                    values.append(format_diff(diff_last20))
                else:
                    values.append("N/A")

                # Trend sparkline: Last10 → Season → Avg
                values.append(build_trend_cell(
                    league.get("last10_over25_2026", 0),
                    league.get("over25_2026", 0),
                    f"{avg_num:.1f}%" if avg_num is not None else None,
                ))
                
                # Calculate median streak for 2022-2024
                streak_years = ["2022", "2023", "2024"]
                streak_values = []
                for year in streak_years:
                    streak_val = league.get(f"streak25_{year}", 0)
                    if isinstance(streak_val, (int, float)) and streak_val != "Error" and streak_val != 0:
                        # Nur negative Werte berücksichtigen (größte negative Zahl = kleinste Zahl)
                        if streak_val < 0:
                            streak_values.append(abs(float(streak_val)))  # Absoluter Wert für Berechnung
                
                if len(streak_values) > 0:
                    # Berechne Durchschnitt: Summe der Streak-Werte / Anzahl der Streaks
                    avg_streak = sum(streak_values) / len(streak_values)
                    values.append(f"{avg_streak:.1f}")
                else:
                    values.append("N/A")
                
                # Add streak statistics from leagues table
                values.append(league.get("max_streak_2022", 0) or 0)
                median_2022 = league.get("median_streak_2022", 0.0) or 0.0
                values.append(f"{median_2022:.1f}" if median_2022 > 0 else "0.0")
                values.append(league.get("max_streak_all", 0) or 0)
                median_all = league.get("median_streak_all", 0.0) or 0.0
                values.append(f"{median_all:.1f}" if median_all > 0 else "0.0")
                
                # Add max_of_max_25 value
                max_of_max_25 = league.get("max_of_max_25", 0) or 0
                values.append(str(max_of_max_25) if max_of_max_25 > 0 else "")
                
                # Add 3.5 streak values
                values.append(league.get("max_streak_2022_35", 0) or 0)
                median_2022_35 = league.get("median_streak_2022_35", 0.0) or 0.0
                values.append(f"{median_2022_35:.1f}" if median_2022_35 > 0 else "0.0")
                values.append(league.get("max_streak_all_35", 0) or 0)
                median_all_35 = league.get("median_streak_all_35", 0.0) or 0.0
                values.append(f"{median_all_35:.1f}" if median_all_35 > 0 else "0.0")
                
                # Add 4.5 streak values
                values.append(league.get("max_streak_2022_45", 0) or 0)
                median_2022_45 = league.get("median_streak_2022_45", 0.0) or 0.0
                values.append(f"{median_2022_45:.1f}" if median_2022_45 > 0 else "0.0")
                values.append(league.get("max_streak_all_45", 0) or 0)
                median_all_45 = league.get("median_streak_all_45", 0.0) or 0.0
                values.append(f"{median_all_45:.1f}" if median_all_45 > 0 else "0.0")
                
                # Determine tags: Streak / Alarm-Farbverlauf / Heute / keine Daten
                tags = list(self._row_alert_tags(league, "over25", "25", alarm_text, today_count, has_data))

                try:
                    item_id = self.leagues_tree_25.insert("", tk.END, values=tuple(values), tags=tuple(dict.fromkeys(tags)) if tags else ())
                    inserted_count_25 += 1
                except Exception as e:
                    print(f"[ERROR] Failed to insert league {league['id']} ({league['name']}) into tree 2.5: {e}")
                    print(f"[DEBUG] Values length: {len(values)}, Expected columns: {len(self.leagues_tree_25['columns'])}")
                    import traceback
                    traceback.print_exc()
                    continue
            
            print(f"[DEBUG] Inserted {inserted_count_25} leagues into tab 2.5")
            
            # Update tab 3.5
            years_reversed = list(reversed(self.years_to_show))  # 2025, 2024, 2023, 2022
            print(f"[DEBUG] Updating tab 3.5 with {len(self.leagues)} leagues")
            for item in self.leagues_tree_35.get_children():
                self.leagues_tree_35.delete(item)
            inserted_count_35 = 0
            for league in self.leagues:
                if not self._league_passes_display_filter(league, "over35", "streak35_2026"):
                    continue
                # Get current season for this league
                league_id = league.get("id")
                current_season = self.current_seasons.get(league_id, 2026)
                
                # Check if league has no data
                games_2025 = league.get("games_2026", 0)
                has_data = games_2025 > 0
                
                # Mark league name if no data
                league_name_display = league["name"]
                if not has_data:
                    league_name_display = f"{league['name']} ⚠"  # Mark with warning symbol
                
                # Calculate improved Alarm using multiple factors for 3.5
                alarm_text = self._calculate_alarm(league, "over35", "streak35_2026") if has_data else ""
                today_count = self._today_upcoming_counts.get(int(league_id), 0)
                alarm_display = self._format_alarm_display(league, "over35") if has_data else ""
                median_ref, max_ref = self._streak_refs_for_metric(league, "35")
                streak_display = format_streak_cell(league.get("streak35_2026", 0), median_ref, max_ref)
                
                values = [
                    league["country"], 
                    league["id"], 
                    league_name_display,  # Use marked name if no data
                    self._today_games_cell_label(today_count),
                    current_season,  # Current Season column
                    games_2025,  # Total Games from 2026
                    alarm_display,  # Alarm column
                    streak_display  # Streak right after Alarm
                ]
                # Add Over 3.5 for each year in reverse order (2025, 2024, 2023, 2022)
                for year in years_reversed:
                    values.append(league.get(f"over35_{year}", 0))
                # Add Last 10, Last 20 for 2026
                values.extend([
                    league.get("last10_over35_2026", 0),
                    league.get("last20_over35_2026", 0)
                ])
                # Calculate average for 2022-2025 (excluding 2026)
                avg_years = self._history_years()
                avg_values = []
                for year in avg_years:
                    val = league.get(f"over35_{year}", 0)
                    if isinstance(val, str) and val != "Error" and val.endswith("%"):
                        try:
                            avg_values.append(float(val.rstrip("%")))
                        except ValueError:
                            pass
                    elif isinstance(val, (int, float)) and val != "Error":
                        avg_values.append(float(val))
                if avg_values:
                    avg = sum(avg_values) / len(avg_values)
                    values.append(f"{avg:.1f}%")
                    avg_num = avg
                else:
                    values.append("N/A")
                    avg_num = None
                
                # Calculate differences
                def parse_percent(val):
                    if isinstance(val, str) and val != "Error" and val.endswith("%"):
                        try:
                            return float(val.rstrip("%"))
                        except ValueError:
                            return None
                    elif isinstance(val, (int, float)) and val != "Error":
                        return float(val)
                    return None
                
                # Diff (2026 - Avg)
                val_current = parse_percent_value(league.get("over35_2026", 0))
                if val_current is not None and avg_num is not None:
                    diff_2026 = val_current - avg_num
                    values.append(format_diff(diff_2026))
                else:
                    values.append("N/A")
                
                # Diff (Last10 - Avg)
                val_last10 = parse_percent_value(league.get("last10_over35_2026", 0))
                if val_last10 is not None and avg_num is not None:
                    diff_last10 = val_last10 - avg_num
                    values.append(format_diff(diff_last10))
                else:
                    values.append("N/A")
                
                # Diff (Last20 - Avg)
                val_last20 = parse_percent_value(league.get("last20_over35_2026", 0))
                if val_last20 is not None and avg_num is not None:
                    diff_last20 = val_last20 - avg_num
                    values.append(format_diff(diff_last20))
                else:
                    values.append("N/A")

                values.append(build_trend_cell(
                    league.get("last10_over35_2026", 0),
                    league.get("over35_2026", 0),
                    f"{avg_num:.1f}%" if avg_num is not None else None,
                ))
                
                # Calculate median streak for 2022-2024
                # Neue Berechnung: Zuerst die Anzahl von Streaks zählen (ein Streak ist 1, 2, 3 oder mehr - die größte Zahl von jedem Lauf)
                # Dann durch die Anzahl von Streaks teilen (Durchschnitt)
                # Wenn 0 ist, muss es nicht berücksichtigt werden
                streak_years = ["2022", "2023", "2024"]
                streak_values = []
                for year in streak_years:
                    streak_val = league.get(f"streak35_{year}", 0)
                    if isinstance(streak_val, (int, float)) and streak_val != "Error" and streak_val != 0:
                        # Nur negative Werte berücksichtigen (größte negative Zahl = kleinste Zahl)
                        if streak_val < 0:
                            streak_values.append(abs(float(streak_val)))  # Absoluter Wert für Berechnung
                
                if len(streak_values) > 0:
                    # Berechne Durchschnitt: Summe der Streak-Werte / Anzahl der Streaks
                    avg_streak = sum(streak_values) / len(streak_values)
                    values.append(f"{avg_streak:.1f}")
                else:
                    values.append("N/A")
                
                # Add streak statistics from leagues table for 3.5
                values.append(league.get("max_streak_2022_35", 0) or 0)
                median_2022_35 = league.get("median_streak_2022_35", 0.0) or 0.0
                values.append(f"{median_2022_35:.1f}" if median_2022_35 > 0 else "0.0")
                values.append(league.get("max_streak_all_35", 0) or 0)
                median_all_35 = league.get("median_streak_all_35", 0.0) or 0.0
                values.append(f"{median_all_35:.1f}" if median_all_35 > 0 else "0.0")
                
                # Add max streak per season for 3.5
                values.append(league.get("max_streak_2022_35_season", 0) or 0)
                values.append(league.get("max_streak_2023_35_season", 0) or 0)
                values.append(league.get("max_streak_2024_35_season", 0) or 0)
                values.append(league.get("max_streak_2025_35_season", 0) or 0)
                values.append(league.get("max_streak_2026_35_season", 0) or 0)
                
                # Add max_of_max_35 value
                max_of_max_35 = league.get("max_of_max_35", 0) or 0
                values.append(str(max_of_max_35) if max_of_max_35 > 0 else "")
                
                # Determine tags for coloring
                tags = list(self._row_alert_tags(league, "over35", "35", alarm_text, today_count, has_data))

                try:
                    item_id = self.leagues_tree_35.insert("", tk.END, values=tuple(values), tags=tuple(dict.fromkeys(tags)) if tags else ())
                    inserted_count_35 += 1
                except Exception as e:
                    print(f"[ERROR] Failed to insert league {league['id']} ({league['name']}) into tree 3.5: {e}")
                    continue
            
            print(f"[DEBUG] Inserted {inserted_count_35} leagues into tab 3.5")
            
            # Update tab 4.5
            years_reversed = list(reversed(self.years_to_show))  # 2025, 2024, 2023, 2022
            print(f"[DEBUG] Updating tab 4.5 with {len(self.leagues)} leagues")
            for item in self.leagues_tree_45.get_children():
                self.leagues_tree_45.delete(item)
            inserted_count_45 = 0
            for league in self.leagues:
                if not self._league_passes_display_filter(league, "over45", "streak45_2026"):
                    continue
                # Get current season for this league
                league_id = league.get("id")
                current_season = self.current_seasons.get(league_id, 2026)
                
                # Check if league has no data
                games_2025 = league.get("games_2026", 0)
                has_data = games_2025 > 0
                
                # Mark league name if no data
                league_name_display = league["name"]
                if not has_data:
                    league_name_display = f"{league['name']} ⚠"  # Mark with warning symbol
                
                # Calculate improved Alarm using multiple factors for 4.5
                alarm_text = self._calculate_alarm(league, "over45", "streak45_2026") if has_data else ""
                today_count = self._today_upcoming_counts.get(int(league_id), 0)
                alarm_display = self._format_alarm_display(league, "over45") if has_data else ""
                median_ref, max_ref = self._streak_refs_for_metric(league, "45")
                streak_display = format_streak_cell(league.get("streak45_2026", 0), median_ref, max_ref)
                
                values = [
                    league["country"], 
                    league["id"], 
                    league_name_display,  # Use marked name if no data
                    self._today_games_cell_label(today_count),
                    current_season,  # Current Season column
                    games_2025,  # Total Games from 2026
                    alarm_display,  # Alarm column
                    streak_display  # Streak right after Alarm
                ]
                # Add Over 4.5 for each year in reverse order (2025, 2024, 2023, 2022)
                for year in years_reversed:
                    values.append(league.get(f"over45_{year}", 0))
                # Add Last 10, Last 20 for 2026
                values.extend([
                    league.get("last10_over45_2026", 0),
                    league.get("last20_over45_2026", 0)
                ])
                # Calculate average for 2022-2025 (excluding 2026)
                avg_years = self._history_years()
                avg_values = []
                for year in avg_years:
                    val = league.get(f"over45_{year}", 0)
                    if isinstance(val, str) and val != "Error" and val.endswith("%"):
                        try:
                            avg_values.append(float(val.rstrip("%")))
                        except ValueError:
                            pass
                    elif isinstance(val, (int, float)) and val != "Error":
                        avg_values.append(float(val))
                if avg_values:
                    avg = sum(avg_values) / len(avg_values)
                    values.append(f"{avg:.1f}%")
                    avg_num = avg
                else:
                    values.append("N/A")
                    avg_num = None
                
                # Calculate differences
                def parse_percent(val):
                    if isinstance(val, str) and val != "Error" and val.endswith("%"):
                        try:
                            return float(val.rstrip("%"))
                        except ValueError:
                            return None
                    elif isinstance(val, (int, float)) and val != "Error":
                        return float(val)
                    return None
                
                # Diff (2026 - Avg)
                val_current = parse_percent_value(league.get("over45_2026", 0))
                if val_current is not None and avg_num is not None:
                    diff_2026 = val_current - avg_num
                    values.append(format_diff(diff_2026))
                else:
                    values.append("N/A")
                
                # Diff (Last10 - Avg)
                val_last10 = parse_percent_value(league.get("last10_over45_2026", 0))
                if val_last10 is not None and avg_num is not None:
                    diff_last10 = val_last10 - avg_num
                    values.append(format_diff(diff_last10))
                else:
                    values.append("N/A")
                
                # Diff (Last20 - Avg)
                val_last20 = parse_percent_value(league.get("last20_over45_2026", 0))
                if val_last20 is not None and avg_num is not None:
                    diff_last20 = val_last20 - avg_num
                    values.append(format_diff(diff_last20))
                else:
                    values.append("N/A")

                values.append(build_trend_cell(
                    league.get("last10_over45_2026", 0),
                    league.get("over45_2026", 0),
                    f"{avg_num:.1f}%" if avg_num is not None else None,
                ))
                
                # Calculate median streak for 2022-2024
                # Neue Berechnung: Zuerst die Anzahl von Streaks zählen (ein Streak ist 1, 2, 3 oder mehr - die größte Zahl von jedem Lauf)
                # Dann durch die Anzahl von Streaks teilen (Durchschnitt)
                # Wenn 0 ist, muss es nicht berücksichtigt werden
                streak_years = ["2022", "2023", "2024"]
                streak_values = []
                for year in streak_years:
                    streak_val = league.get(f"streak45_{year}", 0)
                    if isinstance(streak_val, (int, float)) and streak_val != "Error" and streak_val != 0:
                        # Nur negative Werte berücksichtigen (größte negative Zahl = kleinste Zahl)
                        if streak_val < 0:
                            streak_values.append(abs(float(streak_val)))  # Absoluter Wert für Berechnung
                
                if len(streak_values) > 0:
                    # Berechne Durchschnitt: Summe der Streak-Werte / Anzahl der Streaks
                    avg_streak = sum(streak_values) / len(streak_values)
                    values.append(f"{avg_streak:.1f}")
                else:
                    values.append("N/A")
                
                # Add streak statistics from leagues table for 4.5
                values.append(league.get("max_streak_2022_45", 0) or 0)
                median_2022_45 = league.get("median_streak_2022_45", 0.0) or 0.0
                values.append(f"{median_2022_45:.1f}" if median_2022_45 > 0 else "0.0")
                values.append(league.get("max_streak_all_45", 0) or 0)
                median_all_45 = league.get("median_streak_all_45", 0.0) or 0.0
                values.append(f"{median_all_45:.1f}" if median_all_45 > 0 else "0.0")
                
                # Add max streak per season for 4.5
                values.append(league.get("max_streak_2022_45_season", 0) or 0)
                values.append(league.get("max_streak_2023_45_season", 0) or 0)
                values.append(league.get("max_streak_2024_45_season", 0) or 0)
                values.append(league.get("max_streak_2025_45_season", 0) or 0)
                values.append(league.get("max_streak_2026_45_season", 0) or 0)
                
                # Add max_of_max_45 value
                max_of_max_45 = league.get("max_of_max_45", 0) or 0
                values.append(str(max_of_max_45) if max_of_max_45 > 0 else "")
                
                # Determine tags for coloring
                tags = list(self._row_alert_tags(league, "over45", "45", alarm_text, today_count, has_data))

                try:
                    item_id = self.leagues_tree_45.insert("", tk.END, values=tuple(values), tags=tuple(dict.fromkeys(tags)) if tags else ())
                    inserted_count_45 += 1
                except Exception as e:
                    print(f"[ERROR] Failed to insert league {league['id']} ({league['name']}) into tree 4.5: {e}")
                    continue
            
            print(f"[DEBUG] Inserted {inserted_count_45} leagues into tab 4.5")
            self._populate_watchlist_tree()
            self._apply_view_mode_to_trees()
            print(f"[DEBUG] Total: {inserted_count_25} in 2.5, {inserted_count_35} in 3.5, {inserted_count_45} in 4.5")
            
            # Update tab Current Seasons (only leagues with current_season > 2026)
            print(f"[DEBUG] Updating tab Current Seasons")
            if hasattr(self, 'leagues_tree_current'):
                for item in self.leagues_tree_current.get_children():
                    self.leagues_tree_current.delete(item)
                inserted_count_current = 0
                for league in self.leagues:
                    league_id = league.get("id")
                    current_season = self.current_seasons.get(league_id, 2026)
                    
                    # Only show leagues with current season > 2026
                    if current_season <= 2026:
                        continue
                    
                    # Get games count for current season
                    try:
                        result = self.get_games_count_for_league(league_id, str(current_season))
                        games_current = result["total"]
                        over25_current = result["over25"]
                        over35_current = result["over35"]
                        over45_current = result["over45"]
                    except Exception as e:
                        print(f"Error loading games for league {league_id} year {current_season}: {e}")
                        games_current = 0
                        over25_current = "Error"
                        over35_current = "Error"
                        over45_current = "Error"
                    
                    today_cnt_cs = getattr(self, "_today_upcoming_counts", {}).get(int(league_id), 0)
                    values = [
                        league["country"],
                        league["id"],
                        league["name"],
                        self._today_games_cell_label(today_cnt_cs),
                        current_season,
                        games_current,
                        over25_current,
                        over35_current,
                        over45_current
                    ]

                    row_tags = ("games_today",) if today_cnt_cs > 0 else ()
                    try:
                        item_id = self.leagues_tree_current.insert("", tk.END, values=tuple(values), tags=row_tags)
                        inserted_count_current += 1
                    except Exception as e:
                        print(f"[ERROR] Failed to insert league {league['id']} ({league['name']}) into current seasons tab: {e}")
                        continue
                
                print(f"[DEBUG] Inserted {inserted_count_current} leagues into tab Current Seasons")

            # Update compact alarm overview tab.
            self._update_alarm_overview_tab()
            
            self.status_label.config(text="Loaded")
        except Exception as e:
            import traceback
            error_msg = f"Fehler beim Laden der Liga-Daten: {e}\n{traceback.format_exc()}"
            print(f"[ERROR] {error_msg}")
            if hasattr(self, 'status_label'):
                self.status_label.config(text=f"Fehler: {str(e)}")
            # Show error message to user
            try:
                messagebox.showerror("Fehler", f"Fehler beim Laden der Liga-Informationen:\n{str(e)}")
            except:
                pass

    def sort_tree(self, tree, column):
        """Sort tree by column when heading is clicked"""
        # Get column index
        columns = tree["columns"]
        if column not in columns:
            return
        
        col_index = columns.index(column)
        
        # Toggle sort direction if same column
        if tree.sort_column == column:
            tree.sort_reverse = not tree.sort_reverse
        else:
            tree.sort_column = column
            tree.sort_reverse = False
        
        # Get all items
        items = [(tree.set(item, column), item) for item in tree.get_children("")]
        
        # Sort items
        def try_convert(value):
            """Try to convert value to number for proper sorting"""
            if value == "N/A" or value == "Error":
                return float('-inf') if not tree.sort_reverse else float('inf')
            # Try to parse percentage / diff with arrows
            if isinstance(value, str):
                parsed = parse_percent_value(value)
                if parsed is not None:
                    return parsed
            # Try to parse as float
            try:
                return float(value)
            except (ValueError, TypeError):
                # String comparison
                return str(value).lower()
        
        items.sort(key=lambda x: try_convert(x[0]), reverse=tree.sort_reverse)
        
        # Rearrange items in tree
        for index, (val, item) in enumerate(items):
            tree.move(item, "", index)
        
        # Update heading to show sort direction
        for col in columns:
            heading_text = tree.heading(col)["text"]
            if col == column:
                arrow = " ▼" if tree.sort_reverse else " ▲"
                if arrow not in heading_text:
                    tree.heading(col, text=heading_text.split(" ▼")[0].split(" ▲")[0] + arrow)
            else:
                # Remove arrows from other columns
                heading_text = heading_text.split(" ▼")[0].split(" ▲")[0]
                tree.heading(col, text=heading_text)

    def show_games_list_max_streaks(self, event):
        """Show list of games for the selected league from Max Streaks tab"""
        widget = event.widget
        if widget != self.leagues_tree_max_streaks:
            return
        
        sel = widget.selection()
        if not sel:
            return
        item = widget.item(sel[0])
        values = item["values"]
        
        # Get league_id and league_name from values
        # Values structure: Country (0), ID (1), Name (2), Max2.5 (3), Max3.5 (4), Max4.5 (5), Median2.5 (6), Median3.5 (7), Median4.5 (8), MaxOfMax2.5 (9), MaxOfMax3.5 (10), MaxOfMax4.5 (11)
        if len(values) < 3:
            messagebox.showerror("Error", f"Invalid league data: {values}")
            return
        
        league_id = values[1]
        league_name = values[2]
        
        # Get selected season from dropdown
        try:
            selected_season = self.max_streaks_season_var.get()
            season_year = int(selected_season)
        except (ValueError, AttributeError):
            season_year = 2022  # Default to 2022
        
        # Ensure league_id is an integer
        try:
            league_id = int(league_id)
        except (ValueError, TypeError):
            print(f"[ERROR] Invalid league_id: {league_id}")
            messagebox.showerror("Error", f"Invalid league ID: {league_id}")
            return
        
        # Remove warning symbol if present
        if "⚠" in league_name:
            league_name = league_name.replace("⚠", "").strip()
        
        print(f"[DEBUG] Loading games for league_id={league_id}, season={season_year}, league_name={league_name}")
        
        # Create popup window
        popup = tk.Toplevel(self)
        popup.title(f"Games for {league_name} - Season {season_year} (Loading...)")
        popup.geometry("1600x800")
        
        # Create notebook for table and chart
        notebook = ttk.Notebook(popup)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Tab 1: Games Table
        table_tab = tk.Frame(notebook)
        notebook.add(table_tab, text="Spiele")
        
        # Create a frame with scrollbars for the games table
        table_frame = tk.Frame(table_tab)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Tab 2: Per Game statistics
        per_game_tab_ms = tk.Frame(notebook)
        notebook.add(per_game_tab_ms, text="Pro Spiel")
        
        # Tab 3: Per Round statistics
        per_round_tab_ms = tk.Frame(notebook)
        notebook.add(per_round_tab_ms, text="Pro Runde")
        
        # Tab 4: Goals Chart by Month
        chart_tab = tk.Frame(notebook)
        notebook.add(chart_tab, text="Tore pro Monat")
        
        # Tab 5: Goals per Game Chart
        goals_per_game_tab = tk.Frame(notebook)
        notebook.add(goals_per_game_tab, text="Tore pro Spiel (Chart)")
        
        # Vertical scrollbar
        scrollbar_y = ttk.Scrollbar(table_frame, orient='vertical')
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Horizontal scrollbar
        scrollbar_x = ttk.Scrollbar(table_frame, orient='horizontal')
        scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Games table
        tree = ttk.Treeview(table_frame, columns=("ID", "Home", "Away", "Home Score", "Away Score", "xG Home", "xG Away", "Over2.5", "Over3.5", "Over4.5", "Streak2.5", "Streak3.5", "Streak4.5", "Date", "Status"), 
                          show="headings", yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)
        scrollbar_y.config(command=tree.yview)
        scrollbar_x.config(command=tree.xview)
        
        tree.heading("ID", text="Game ID")
        tree.heading("Home", text="Home Team")
        tree.heading("Away", text="Away Team")
        tree.heading("Home Score", text="Home Score")
        tree.heading("Away Score", text="Away Score")
        tree.heading("xG Home", text="xG Home")
        tree.heading("xG Away", text="xG Away")
        tree.heading("Over2.5", text="Over 2.5")
        tree.heading("Over3.5", text="Over 3.5")
        tree.heading("Over4.5", text="Over 4.5")
        tree.heading("Streak2.5", text="Streak 2.5")
        tree.heading("Streak3.5", text="Streak 3.5")
        tree.heading("Streak4.5", text="Streak 4.5")
        tree.heading("Date", text="Date")
        tree.heading("Status", text="Status")
        tree.column("ID", width=70, anchor='center')
        tree.column("Home", width=100)
        tree.column("Away", width=100)
        tree.column("Home Score", width=70, anchor='center')
        tree.column("Away Score", width=70, anchor='center')
        tree.column("xG Home", width=70, anchor='center')
        tree.column("xG Away", width=70, anchor='center')
        tree.column("Over2.5", width=70, anchor='center')
        tree.column("Over3.5", width=70, anchor='center')
        tree.column("Over4.5", width=70, anchor='center')
        tree.column("Streak2.5", width=70, anchor='center')
        tree.column("Streak3.5", width=70, anchor='center')
        tree.column("Streak4.5", width=70, anchor='center')
        tree.column("Date", width=100)
        tree.column("Status", width=80)
        
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Store tree reference for cell coloring
        self.games_tree = tree
        self.games_popup = popup
        
        # Button frame (button will be created after games are loaded)
        button_frame = tk.Frame(popup)
        button_frame.pack(pady=5)
        
        # Progress label (initially hidden)
        progress_label = tk.Label(popup, text="", fg="blue")
        progress_label.pack(pady=2)
        
        # Load games from database for the selected season
        def load_games_thread():
            try:
                from database import DatabaseManager
                import sqlite3
                db_manager = DatabaseManager("data/flashscore.db")
                conn = db_manager.get_connection()
                conn.row_factory = sqlite3.Row
                
                # Load games for the selected season, ordered by date DESC (neueste zuerst)
                # Same as Finished Games window - count streaks in reverse (from newest to oldest)
                rows = conn.execute("""
                    SELECT id, date, home_team_name, away_team_name,
                           home_ft_result, away_ft_result, status, status_name,
                           country_name, league_name, league_id, season_year,
                           calculated_xg_home, calculated_xg_away, total_goals,
                           over_25, over_35, over_45
                    FROM games 
                    WHERE league_id = ?
                      AND season_year = ?
                      AND status IN (7, 8, 9, 10)
                    ORDER BY date DESC
                """, (league_id, season_year)).fetchall()
                
                # Update UI in main thread
                def update_ui():
                    popup.title(f"Games for {league_name} - Season {season_year}")
                    progress_label.config(text=f"Loaded {len(rows)} games")
                    
                    # Calculate streaks as we insert games (from newest to oldest - "in Folge")
                    # Count Under streaks: how many games in a row ended with <= X.5 goals
                    streak_25 = 0
                    streak_35 = 0
                    streak_45 = 0
                    
                    # Store color info for individual cells
                    if not hasattr(self, '_game_colors'):
                        self._game_colors = {}
                    
                    for row in rows:
                        home_score = row['home_ft_result'] or 0
                        away_score = row['away_ft_result'] or 0
                        total = home_score + away_score
                        
                        # Calculate over/under values
                        over_25 = 1 if total > 2.5 else 0
                        over_35 = 1 if total > 3.5 else 0
                        over_45 = 1 if total > 4.5 else 0
                        
                        # Calculate Under streaks (count games with <= X.5 goals)
                        # Under 2.5 = total <= 2
                        if total <= 2:
                            streak_25 += 1
                        else:
                            streak_25 = 0
                        
                        # Under 3.5 = total <= 3
                        if total <= 3:
                            streak_35 += 1
                        else:
                            streak_35 = 0
                        
                        # Under 4.5 = total <= 4
                        if total <= 4:
                            streak_45 += 1
                        else:
                            streak_45 = 0
                        
                        item_id = str(row['id'])
                        tree.insert("", tk.END, iid=item_id, values=(
                            row['id'],
                            row['home_team_name'] or "",
                            row['away_team_name'] or "",
                            home_score,
                            away_score,
                            f"{row['calculated_xg_home']:.2f}" if row['calculated_xg_home'] is not None else "N/A",
                            f"{row['calculated_xg_away']:.2f}" if row['calculated_xg_away'] is not None else "N/A",
                            "✓" if over_25 == 1 else "✗",
                            "✓" if over_35 == 1 else "✗",
                            "✓" if over_45 == 1 else "✗",
                            streak_25 if streak_25 > 0 else "",  # Under 2.5 streak (in Folge)
                            streak_35 if streak_35 > 0 else "",  # Under 3.5 streak (in Folge)
                            streak_45 if streak_45 > 0 else "",  # Under 4.5 streak (in Folge)
                            row['date'] or "",
                            row['status_name'] or ""
                        ))
                        
                        # Store color info for row coloring
                        # Color logic: 
                        # - Grün: > 4.5 (5+ Goals)
                        # - Gelb: == 4 Goals
                        # - Orange: == 3 Goals
                        # - Rot: < 2.5 (0, 1, 2 Goals)
                        if total > 4.5:
                            color_category = 'green'  # 5+ Goals
                        elif total == 4:
                            color_category = 'yellow'  # Exactly 4 Goals
                        elif total == 3:
                            color_category = 'orange'  # Exactly 3 Goals
                        else:  # total < 2.5 (0, 1, or 2 Goals)
                            color_category = 'red'
                        
                        self._game_colors[item_id] = {
                            'over25': over_25 == 1,
                            'over35': over_35 == 1,
                            'over45': over_45 == 1,
                            'color_category': color_category,
                            'total_goals': total
                        }
                    
                    # Apply row coloring
                    self._apply_cell_colors_workaround(tree)
                    
                    # Force UI update
                    popup.update_idletasks()
                    tree.update_idletasks()
                    popup.update()
                    table_frame.update()
                    table_tab.update()
                    
                    print(f"[DEBUG] Successfully inserted {len(rows)} games into treeview")
                    print(f"[DEBUG] Treeview has {len(tree.get_children())} items after insertion")
                    
                    # Create charts (similar to show_games_list)
                    # Convert rows to list of dicts for chart methods
                    games_list = []
                    for row in rows:
                        games_list.append({
                            'date': row['date'],
                            'total_goals': row['total_goals'] or 0,
                            'home_ft_result': row['home_ft_result'] or 0,
                            'away_ft_result': row['away_ft_result'] or 0
                        })
                    
                    self._create_goals_chart(chart_tab, games_list, league_name)
                    # For goals per game chart, we need conn and league_id
                    self._create_goals_per_game_chart(goals_per_game_tab, games_list, league_name, league_id, conn)
                    
                    # Populate Pro Spiel and Pro Runde tabs
                    self._create_per_game_stats_tab(per_game_tab_ms, games_list, league_name, season_year, league_id, conn)
                    self._create_per_round_stats_tab(per_round_tab_ms, league_id, conn, league_name, int(season_year))
                
                self.after(0, update_ui)
                
            except Exception as e:
                error_msg = f"Error loading games: {e}"
                print(f"[ERROR] {error_msg}")
                import traceback
                traceback.print_exc()
                self.after(0, lambda: messagebox.showerror("Error", error_msg))
        
        # Start loading in background thread
        import threading
        thread = threading.Thread(target=load_games_thread, daemon=True)
        thread.start()
        progress_label.config(text="Loading games...")

    def _add_league_id_to_watchlist(self, league_id, league_name=None):
        try:
            self.watchlist_ids.add(int(league_id))
            save_watchlist(self.watchlist_ids)
            self._populate_watchlist_tree()
            if league_name:
                messagebox.showinfo("Watchlist", f"{league_name} hinzugefügt.")
        except Exception as e:
            messagebox.showerror("Watchlist", str(e))

    def _on_right_click_league(self, event):
        """Show context menu on right-click for league deletion"""
        widget = event.widget
        # Select the row under cursor
        row_id = widget.identify_row(event.y)
        if not row_id:
            return
        widget.selection_set(row_id)
        
        item = widget.item(row_id)
        values = item["values"]
        if not values or len(values) < 3:
            return
        
        league_id = values[1]
        league_name = values[2]
        country = values[0]
        
        # Create context menu
        context_menu = tk.Menu(self, tearoff=0)
        context_menu.add_command(
            label=f"★ Zur Watchlist: {country} - {league_name}",
            command=lambda: self._add_league_id_to_watchlist(league_id, league_name)
        )
        context_menu.add_separator()
        context_menu.add_command(
            label=f"➡ In Liga 128 übertragen: {country} - {league_name} (ID: {league_id})",
            command=lambda: self._transfer_to_liga128(league_id, league_name, country)
        )
        context_menu.add_separator()
        context_menu.add_command(
            label=f"🗑 League löschen: {country} - {league_name} (ID: {league_id})",
            command=lambda: self._delete_league(league_id, league_name, country)
        )
        context_menu.add_separator()
        context_menu.add_command(label="Abbrechen", command=context_menu.destroy)
        
        # Show context menu at cursor position
        try:
            context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            context_menu.grab_release()
    
    def _transfer_to_liga128(self, league_id, league_name, country):
        """Transfer a league to the Liga 128 tab by adding it to the config"""
        import json
        import os
        
        config_path = os.path.join("data", "liga128_leagues.json")
        
        # Load current config
        current_ids = []
        try:
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    current_ids = json.load(f)
        except Exception as e:
            print(f"[ERROR] Could not load liga128 config: {e}")
            current_ids = [128]
        
        # Check if already in list
        if league_id in current_ids:
            messagebox.showinfo(
                "Bereits vorhanden",
                f"Liga {country} - {league_name} (ID: {league_id})\n"
                f"ist bereits im Liga 128 Tab enthalten."
            )
            return
        
        # Confirmation
        result = messagebox.askyesno(
            "In Liga 128 übertragen",
            f"Liga in den Liga 128 Tab übertragen?\n\n"
            f"Liga: {country} - {league_name}\n"
            f"ID: {league_id}\n\n"
            f"Nach dem Übertrag: Unter „Leagues“ kannst du mit „Daten aktualisieren“ die Liste neu laden,\n"
            f"dann erscheint die Liga dort nicht mehr.\n\n"
            f"Sie bleibt im Tab „Liga 128“ und im Datenbank-Tab zum Laden wählbar."
        )
        
        if not result:
            return
        
        # Add to config
        current_ids.append(int(league_id))
        try:
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, "w") as f:
                json.dump(sorted(set(current_ids)), f)
            
            print(f"[INFO] League {league_id} ({league_name}) added to Liga 128 tab")
            
            messagebox.showinfo(
                "Übertragen",
                f"Liga {country} - {league_name} (ID: {league_id})\n"
                f"wurde zum Liga 128 Tab hinzugefügt.\n\n"
                f"Tipps: „Daten aktualisieren“ im Tab „Leagues“ lädt die Liste neu.\n\n"
                f"Aktuelle IDs im Liga 128 Tab: {sorted(set(current_ids))}"
            )
        except Exception as e:
            print(f"[ERROR] Failed to save liga128 config: {e}")
            messagebox.showerror("Fehler", f"Fehler beim Speichern:\n{e}")

    def _delete_league(self, league_id, league_name, country):
        """Delete a league and all its games from the database"""
        # Confirmation dialog
        result = messagebox.askyesno(
            "League löschen",
            f"Möchtest du die Liga wirklich löschen?\n\n"
            f"Liga: {country} - {league_name}\n"
            f"ID: {league_id}\n\n"
            f"⚠ Alle Spiele dieser Liga werden ebenfalls gelöscht!\n"
            f"Diese Aktion kann nicht rückgängig gemacht werden.",
            icon="warning"
        )
        
        if not result:
            return
        
        try:
            from database import DatabaseManager
            db_manager = DatabaseManager("data/flashscore.db")
            conn = db_manager.get_connection()
            
            # Count games before deletion
            game_count = conn.execute(
                "SELECT COUNT(*) FROM games WHERE league_id = ?", (league_id,)
            ).fetchone()[0]
            
            # Delete games
            conn.execute("DELETE FROM games WHERE league_id = ?", (league_id,))
            
            # Delete from leagues table
            conn.execute("DELETE FROM leagues WHERE league_id = ?", (league_id,))
            
            conn.commit()
            
            print(f"[INFO] League {league_id} ({league_name}) deleted: {game_count} games removed")
            
            # Remove from self.leagues list
            self.leagues = [l for l in self.leagues if l.get("id") != league_id]
            
            # Refresh all treeviews
            self.after(0, self.load_league_games_counts)
            
            messagebox.showinfo(
                "League gelöscht",
                f"Liga {country} - {league_name} (ID: {league_id}) wurde gelöscht.\n"
                f"{game_count} Spiele wurden entfernt."
            )
        except Exception as e:
            print(f"[ERROR] Failed to delete league {league_id}: {e}")
            messagebox.showerror("Fehler", f"Fehler beim Löschen der Liga:\n{e}")

    def show_games_list(self, event):
        """Show list of games for the selected league"""
        # Determine which tree was clicked
        widget = event.widget
        if widget == self.leagues_tree_25:
            tree = self.leagues_tree_25
        elif widget == self.leagues_tree_35:
            tree = self.leagues_tree_35
        elif widget == self.leagues_tree_45:
            tree = self.leagues_tree_45
        elif hasattr(self, "leagues_tree_alarm") and widget == self.leagues_tree_alarm:
            tree = self.leagues_tree_alarm
        else:
            return
        
        sel = tree.selection()
        if not sel:
            return
        item = tree.item(sel[0])
        values = item["values"]
        
        # Debug: Print values to see structure
        print(f"[DEBUG] show_games_list - values: {values}")
        
        # Get league_id and league_name from values
        # Values structure: Country (0), ID (1), Name (2), Games_2026 (3), Alarm (4), Streak (5), ...
        if len(values) < 3:
            messagebox.showerror("Error", f"Invalid league data: {values}")
            return
        
        league_id = values[1]
        league_name = values[2]
        
        # Ensure league_id is an integer
        try:
            league_id = int(league_id)
        except (ValueError, TypeError):
            print(f"[ERROR] Invalid league_id: {league_id}")
            messagebox.showerror("Error", f"Invalid league ID: {league_id}")
            return
        
        # Remove warning symbol if present
        if "⚠" in league_name:
            league_name = league_name.replace("⚠", "").strip()
        
        print(f"[DEBUG] Loading games for league_id={league_id} (type: {type(league_id)}), league_name={league_name}")
        print(f"[DEBUG] Values structure: {values}")
        
        # Create popup window
        popup = tk.Toplevel(self)
        popup.title(f"Games for {league_name} (Loading...)")
        popup.geometry("1600x800")
        
        # Create notebook for table and chart
        notebook = ttk.Notebook(popup)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Tab 1: Games Table
        table_tab = tk.Frame(notebook)
        notebook.add(table_tab, text="Spiele")
        
        # Create a frame with scrollbars for the games table
        table_frame = tk.Frame(table_tab)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Tab 2: Today's upcoming games for this league
        today_games_tab = tk.Frame(notebook)
        notebook.add(today_games_tab, text="Heute Spiele")

        # Tab 3: Per Game statistics (Goals per game table)
        per_game_tab = tk.Frame(notebook)
        notebook.add(per_game_tab, text="Pro Spiel")
        
        # Tab 4: Per Round statistics (Goals per round)
        per_round_tab = tk.Frame(notebook)
        notebook.add(per_round_tab, text="Pro Runde")
        
        # Tab 5: Goals Chart by Month
        chart_tab = tk.Frame(notebook)
        notebook.add(chart_tab, text="Tore pro Monat")
        
        # Tab 6: Goals per Game Chart
        goals_per_game_tab = tk.Frame(notebook)
        notebook.add(goals_per_game_tab, text="Tore pro Spiel (Chart)")
        
        # Vertical scrollbar
        scrollbar_y = ttk.Scrollbar(table_frame, orient='vertical')
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Horizontal scrollbar
        scrollbar_x = ttk.Scrollbar(table_frame, orient='horizontal')
        scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Games table
        tree = ttk.Treeview(table_frame, columns=("ID", "Home", "Away", "Home Score", "Away Score", "xG Home", "xG Away", "Over2.5", "Over3.5", "Over4.5", "Streak2.5", "Streak3.5", "Streak4.5", "Date", "Status"), 
                          show="headings", yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)
        scrollbar_y.config(command=tree.yview)
        scrollbar_x.config(command=tree.xview)
        
        tree.heading("ID", text="Game ID")
        tree.heading("Home", text="Home Team")
        tree.heading("Away", text="Away Team")
        tree.heading("Home Score", text="Home Score")
        tree.heading("Away Score", text="Away Score")
        tree.heading("xG Home", text="xG Home")
        tree.heading("xG Away", text="xG Away")
        tree.heading("Over2.5", text="Over 2.5")
        tree.heading("Over3.5", text="Over 3.5")
        tree.heading("Over4.5", text="Over 4.5")
        tree.heading("Streak2.5", text="Streak 2.5")
        tree.heading("Streak3.5", text="Streak 3.5")
        tree.heading("Streak4.5", text="Streak 4.5")
        tree.heading("Date", text="Date")
        tree.heading("Status", text="Status")
        tree.column("ID", width=70, anchor='center')
        tree.column("Home", width=100)
        tree.column("Away", width=100)
        tree.column("Home Score", width=70, anchor='center')
        tree.column("Away Score", width=70, anchor='center')
        tree.column("xG Home", width=70, anchor='center')
        tree.column("xG Away", width=70, anchor='center')
        tree.column("Over2.5", width=70, anchor='center')
        tree.column("Over3.5", width=70, anchor='center')
        tree.column("Over4.5", width=70, anchor='center')
        tree.column("Streak2.5", width=70, anchor='center')
        tree.column("Streak3.5", width=70, anchor='center')
        tree.column("Streak4.5", width=70, anchor='center')
        tree.column("Date", width=100)
        tree.column("Status", width=80)
        
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Store tree reference for cell coloring
        self.games_tree = tree
        self.games_popup = popup
        
        # Button frame (button will be created after games are loaded)
        button_frame = tk.Frame(popup)
        button_frame.pack(pady=5)
        
        # Progress label (initially hidden)
        progress_label = tk.Label(popup, text="", fg="blue")
        progress_label.pack(pady=2)
        
        # Load games - only from database
        conn = None
        selected_year = "2026"
        year_int = 2026
        year_check = []
        all_games = []
        
        try:
            # Try to find the most recent year with games for this league
            from database import DatabaseManager
            import sqlite3
            db_manager = DatabaseManager("data/flashscore.db")
            conn = db_manager.get_connection()
            conn.row_factory = sqlite3.Row
            
            # Set timeout for this connection to handle locks
            conn.execute("PRAGMA busy_timeout = 30000")  # 30 seconds timeout
            
            # First, check what years are available for this league
            year_check = conn.execute("""
                SELECT DISTINCT season_year, COUNT(*) as cnt
                FROM games 
                WHERE league_id = ?
                  AND home_ft_result IS NOT NULL 
                  AND away_ft_result IS NOT NULL
                GROUP BY season_year
                ORDER BY season_year DESC
            """, (league_id,)).fetchall()
            
            # Determine which year to use
            # Check if self.year is set (e.g., by League128Tab to force 2026)
            preferred_year = getattr(self, 'year', "2026")
            preferred_year_int = int(preferred_year) if preferred_year.isdigit() else 2026
            
            selected_year = preferred_year
            year_int = preferred_year_int
            
            if year_check:
                # Try preferred year first (e.g., 2026 for League 128)
                found_preferred = False
                for year_row in year_check:
                    if year_row['season_year'] == preferred_year_int:
                        selected_year = preferred_year
                        year_int = preferred_year_int
                        found_preferred = True
                        break
                
                # If preferred year not found, try 2025
                if not found_preferred:
                    for year_row in year_check:
                        if year_row['season_year'] == 2026:
                            selected_year = "2026"
                            year_int = 2026
                            found_preferred = True
                            break
                
                # If neither preferred nor 2025 found, use the most recent year
                if not found_preferred:
                    most_recent_year = year_check[0]['season_year']
                    selected_year = str(most_recent_year)
                    year_int = int(most_recent_year)
                    print(f"[INFO] No games for {preferred_year} or 2025, using most recent year: {year_int} ({year_check[0]['cnt']} games)")
            else:
                # Default to preferred year if no games found at all
                selected_year = preferred_year
                year_int = preferred_year_int
                print(f"[WARNING] No games found in database for league {league_id}")

            
            # Initialize client early (needed for xG loading button even if loading from DB)
            client = self.services["client"]
            
            # Load games from database - Load games for the selected year (2025)
            try:
                # Ensure league_id is an integer
                league_id_int = int(league_id)
                print(f"[DEBUG] Loading games for league_id={league_id_int}, year={year_int}")
                
                # Load finished games for this league and year (2025)
                # First try with season_year
                rows = conn.execute("""
                    SELECT id, date, home_team_name, away_team_name,
                           home_ft_result, away_ft_result, status, status_name,
                           country_name, league_name, league_id, season_year,
                           calculated_xg_home, calculated_xg_away, round_name
                    FROM games 
                    WHERE league_id = ?
                      AND season_year = ?
                      AND home_ft_result IS NOT NULL 
                      AND away_ft_result IS NOT NULL
                    ORDER BY date DESC
                """, (league_id_int, year_int)).fetchall()
                
                print(f"[DEBUG] Found {len(rows)} games with season_year={year_int}")
                
                # If no games with season_year, try filtering by date
                if not rows:
                    print(f"[DEBUG] No games with season_year={year_int}, trying date filter...")
                    rows = conn.execute("""
                        SELECT id, date, home_team_name, away_team_name,
                               home_ft_result, away_ft_result, status, status_name,
                               country_name, league_name, league_id, season_year,
                               calculated_xg_home, calculated_xg_away, round_name
                        FROM games 
                        WHERE league_id = ?
                          AND date LIKE ?
                          AND home_ft_result IS NOT NULL 
                          AND away_ft_result IS NOT NULL
                        ORDER BY date DESC
                    """, (league_id_int, f"{year_int}%")).fetchall()
                    print(f"[DEBUG] Found {len(rows)} games with date starting with {year_int}")
                
                # Debug: Show first row if available
                if rows:
                    first_row = rows[0]
                    season_year_val = first_row['season_year'] if 'season_year' in first_row.keys() else None
                    print(f"[DEBUG] First game: id={first_row['id']}, home={first_row['home_team_name']}, away={first_row['away_team_name']}, date={first_row['date']}, season_year={season_year_val}")
                else:
                    # If no rows, check if league_id exists at all
                    check_league = conn.execute("SELECT COUNT(*) as cnt FROM games WHERE league_id = ?", (league_id_int,)).fetchone()
                    print(f"[DEBUG] Total games for league_id {league_id_int} (any status): {check_league['cnt'] if check_league else 0}")
                    # Also check for year 2025 specifically
                    check_2025 = conn.execute("SELECT COUNT(*) as cnt FROM games WHERE league_id = ? AND season_year = 2025", (league_id_int,)).fetchone()
                    print(f"[DEBUG] Games for league_id {league_id_int} with season_year=2025: {check_2025['cnt'] if check_2025 else 0}")
                
                if year_check:
                    print(f"[DEBUG] Available years for league {league_id}: {[f'{r[0]}: {r[1]} games' for r in year_check]}")
                
                # Convert database rows to game dicts (compatible with API format)
                # Show ALL games - no year filtering
                for row in rows:
                    # Get season_year if available (sqlite3.Row uses [] not .get())
                    season_year = row['season_year'] if 'season_year' in row.keys() else None
                    
                    # Get round_name safely
                    round_name = row['round_name'] if 'round_name' in row.keys() else None
                    
                    game_dict = {
                        'id': row['id'],
                        'Id': row['id'],
                        'date': row['date'],
                        'home_team': row['home_team_name'],
                        'away_team': row['away_team_name'],
                        'homeTeam': {'name': row['home_team_name']},  # API format
                        'awayTeam': {'name': row['away_team_name']},  # API format
                        'home_team_name': row['home_team_name'],
                        'away_team_name': row['away_team_name'],
                        'homeResult': row['home_ft_result'] if row['home_ft_result'] is not None else 0,
                        'awayResult': row['away_ft_result'] if row['away_ft_result'] is not None else 0,
                        'homeFTResult': row['home_ft_result'] if row['home_ft_result'] is not None else 0,
                        'awayFTResult': row['away_ft_result'] if row['away_ft_result'] is not None else 0,
                        'home_ft_result': row['home_ft_result'] if row['home_ft_result'] is not None else 0,
                        'away_ft_result': row['away_ft_result'] if row['away_ft_result'] is not None else 0,
                        'score_home': row['home_ft_result'] if row['home_ft_result'] is not None else 0,
                        'score_away': row['away_ft_result'] if row['away_ft_result'] is not None else 0,
                        'status': row['status'],
                        'statusName': row['status_name'],
                        'status_text': row['status_name'],
                        'country': row['country_name'],
                        'league_name': row['league_name'],
                        'calculated_xg_home': row['calculated_xg_home'],
                        'calculated_xg_away': row['calculated_xg_away'],
                        'round_name': round_name,
                        'season_year': season_year,
                        'from_db': True,
                        'year_matched': True  # Always True - we show all loaded games
                    }
                    all_games.append(game_dict)
                    
                    # Debug: print first few games
                    if len(all_games) <= 3:
                        print(f"[DEBUG] Game {row['id']}: date={row['date']}, season_year={season_year}")
                
                print(f"[INFO] Loaded {len(all_games)} games from database for league {league_id}, year {year_int}")
                
            except Exception as e:
                print(f"[ERROR] Error loading games from database: {e}")
                import traceback
                traceback.print_exc()
                # Kein API-Fallback mehr - nur Datenbank
                all_games = []
                # Don't show warning here - let it continue and show the error message later
                print(f"[WARNING] Failed to load games, all_games is now empty")
            
            # Show ALL games loaded from database - no additional filtering needed
            # All games from database are already finished games (have home_ft_result and away_ft_result)
            filtered_games = all_games.copy()  # Simply copy all games - they're all valid
            
            print(f"[DEBUG] Total games loaded: {len(all_games)}")
            print(f"[DEBUG] Filtered games (should be same as loaded): {len(filtered_games)}")
            
            # Verify all games are from database
            for game in filtered_games:
                if not game.get("from_db"):
                    print(f"[WARNING] Found non-database game: {game.get('id')}")
            
            print(f"[DEBUG] Filtered games: {len(filtered_games)}")
            print(f"[DEBUG] Total games loaded: {len(all_games)}")
            print(f"[DEBUG] League ID: {league_id}, Year: {year_int}")
            
            if not filtered_games:
                print(f"[ERROR] No filtered games! all_games count: {len(all_games)}")
                if len(all_games) > 0:
                    print(f"[DEBUG] First game example: {all_games[0]}")
                
                # Check if there are any games in database for this league at all
                total_in_db = 0
                finished_in_db = 0
                if conn:
                    try:
                        # Ensure league_id is integer for query
                        league_id_for_query = int(league_id) if league_id else None
                        if league_id_for_query is None:
                            print(f"[ERROR] Invalid league_id: {league_id}")
                            return
                        
                        check_rows = conn.execute("""
                            SELECT COUNT(*) as cnt
                            FROM games 
                            WHERE league_id = ?
                        """, (league_id_for_query,)).fetchone()
                        total_in_db = check_rows['cnt'] if check_rows else 0
                        
                        finished_rows = conn.execute("""
                            SELECT COUNT(*) as cnt
                            FROM games 
                            WHERE league_id = ?
                              AND home_ft_result IS NOT NULL 
                              AND away_ft_result IS NOT NULL
                        """, (league_id_for_query,)).fetchone()
                        finished_in_db = finished_rows['cnt'] if finished_rows else 0
                        
                        print(f"[DEBUG] Total games in DB for league {league_id}: {total_in_db}")
                        print(f"[DEBUG] Finished games in DB for league {league_id}: {finished_in_db}")
                    except Exception as e:
                        print(f"[ERROR] Error checking database: {e}")
                        total_in_db = 0
                        finished_in_db = 0
                
                # Show message if no games found at all
                info_text = f"Keine Spiele gefunden für {league_name}\n\n"
                info_text += f"Liga ID: {league_id}\n"
                info_text += f"Jahr: {selected_year}\n\n"
                info_text += f"Spiele in Datenbank (gesamt): {total_in_db}\n"
                info_text += f"Spiele in Datenbank (beendet): {finished_in_db}\n\n"
                if year_check:
                    info_text += f"Verfügbare Jahre: {', '.join([str(r[0]) for r in year_check])}\n"
                info_text += f"\nBitte prüfen Sie die Konsole für weitere Debug-Informationen."
                
                no_games_frame = tk.Frame(popup)
                no_games_frame.pack(fill=tk.BOTH, expand=True, pady=20)
                
                no_games_label = tk.Label(no_games_frame, text=info_text, fg="red", font=("Arial", 11), justify=tk.LEFT)
                no_games_label.pack(pady=10)
                
                popup.title(f"Games for {league_name} - No games found")
                return
            
            # Also load today's upcoming games for a quick double-click overview.
            today_upcoming_games = self._load_today_upcoming_games(conn, league_id_int)
            self._create_today_games_tab(today_games_tab, today_upcoming_games, league_name)

            # Sort games by date (most recent first)
            filtered_games.sort(key=lambda g: g.get("date", ""), reverse=True)
            
            # Calculate streaks for each game (for display in table)
            # Streaks should be counted backwards: newest game has highest number, oldest has 1
            # Games are sorted newest first (date DESC)
            game_streaks = {}
            
            # First pass: find maximum streaks for each game position
            # We need to find the longest consecutive sequence ending at each position
            max_streak_25 = 0
            max_streak_35 = 0
            max_streak_45 = 0
            
            current_streak_25 = 0
            current_streak_35 = 0
            current_streak_45 = 0
            
            # Count streaks forward to find maximum
            for idx, game in enumerate(filtered_games):
                home_g = game.get("homeResult") or game.get("homeFTResult") or game.get("score_home") or game.get("home_ft_result") or 0
                away_g = game.get("awayResult") or game.get("awayFTResult") or game.get("score_away") or game.get("away_ft_result") or 0
                total_g = int(home_g) + int(away_g)
                
                # Count Under streaks "in Folge" (from newest to oldest)
                # Under 2.5 = total <= 2
                if total_g <= 2:
                    current_streak_25 += 1
                    if current_streak_25 > max_streak_25:
                        max_streak_25 = current_streak_25
                else:
                    current_streak_25 = 0
                
                # Under 3.5 = total <= 3
                if total_g <= 3:
                    current_streak_35 += 1
                    if current_streak_35 > max_streak_35:
                        max_streak_35 = current_streak_35
                else:
                    current_streak_35 = 0
                
                # Under 4.5 = total <= 4
                if total_g <= 4:
                    current_streak_45 += 1
                    if current_streak_45 > max_streak_45:
                        max_streak_45 = current_streak_45
                else:
                    current_streak_45 = 0
            
            # Second pass: calculate streaks for display
            # Streaks should be counted forward: 1, 2, 3, 4... (not backwards)
            # If a game has > X.5 goals, streak = 0
            # If the next game has <= X.5 goals, streak = 1
            streak25 = 0
            streak35 = 0
            streak45 = 0
            
            for idx, game in enumerate(filtered_games):
                home_g = game.get("homeResult") or game.get("homeFTResult") or game.get("score_home") or game.get("home_ft_result") or 0
                away_g = game.get("awayResult") or game.get("awayFTResult") or game.get("score_away") or game.get("away_ft_result") or 0
                total_g = int(home_g) + int(away_g)
                
                # Count Under streaks "in Folge" (from newest to oldest)
                # Under 2.5 = total <= 2
                if total_g <= 2:
                    streak25 += 1
                else:
                    streak25 = 0
                    
                # Under 3.5 = total <= 3
                if total_g <= 3:
                    streak35 += 1
                else:
                    streak35 = 0
                    
                # Under 4.5 = total <= 4
                if total_g <= 4:
                    streak45 += 1
                else:
                    streak45 = 0
                
                # Store streak values directly (1, 2, 3, 4...)
                # If game is over X.5, streak is already 0
                # If game is under X.5, streak shows the count
                gid = game.get("id") or game.get("Id") or ""
                
                game_streaks[str(gid)] = {
                    'streak25': streak25,
                    'streak35': streak35,
                    'streak45': streak45
                }
            
            # Display filtered games with xG data from database
            print(f"[DEBUG] Starting to insert {len(filtered_games)} games into treeview")
            inserted_count = 0
            for idx, game in enumerate(filtered_games):
                gid = game.get("id") or game.get("Id") or ""
                
                # Get home team name - try multiple sources
                home = ""
                if isinstance(game.get("homeTeam"), dict):
                    home = game.get("homeTeam", {}).get("name", "")
                elif game.get("homeTeam"):
                    home = str(game.get("homeTeam", ""))
                if not home:
                    home = game.get("home_team_name") or game.get("home_team") or ""
                
                # Get away team name - try multiple sources
                away = ""
                if isinstance(game.get("awayTeam"), dict):
                    away = game.get("awayTeam", {}).get("name", "")
                elif game.get("awayTeam"):
                    away = str(game.get("awayTeam", ""))
                if not away:
                    away = game.get("away_team_name") or game.get("away_team") or ""
                
                if not home or not away:
                    print(f"[WARNING] Missing team names for game {gid}: home={home}, away={away}")
                    print(f"[DEBUG] Game keys: {list(game.keys())}")
                score_home = game.get("score_home") or game.get("homeResult") or game.get("homeFTResult") or game.get("home_ft_result") or 0
                score_away = game.get("score_away") or game.get("awayResult") or game.get("awayFTResult") or game.get("away_ft_result") or 0
                date = game.get("date") or game.get("gameDate") or ""
                # Format date if it's in ISO format
                if date and "T" in str(date):
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(date.replace("Z", "+00:00"))
                        date = dt.strftime("%Y-%m-%d %H:%M")
                    except:
                        pass
                status = game.get("statusName") or game.get("status") or game.get("status_name") or ""
                
                # Get xG from database (already loaded if from_db)
                xg_home_val = game.get("calculated_xg_home")
                xg_away_val = game.get("calculated_xg_away")
                xg_home_str = f"{xg_home_val:.2f}" if xg_home_val is not None else "N/A"
                xg_away_str = f"{xg_away_val:.2f}" if xg_away_val is not None else "N/A"
                
                # Calculate total goals for over/under markers
                total_goals = int(score_home) + int(score_away)
                
                # Determine over/under markers
                over25 = "✓" if total_goals > 2.5 else "✗"
                over35 = "✓" if total_goals > 3.5 else "✗"
                over45 = "✓" if total_goals > 4.5 else "✗"
                
                # Get streak values for this game
                streak25_val = game_streaks.get(str(gid), {}).get('streak25', 0)
                streak35_val = game_streaks.get(str(gid), {}).get('streak35', 0)
                streak45_val = game_streaks.get(str(gid), {}).get('streak45', 0)
                
                # Display streak values:
                # - If game is over X.5 goals, streak should be 0
                # - If game is under X.5 goals, streak should show the count (1, 2, 3, ...)
                # The streak calculation in the loop above already handles this correctly:
                #   - If total <= 2.5: streak25 is incremented (1, 2, 3, ...)
                #   - If total > 2.5: streak25 is reset to 0
                # So we just use the calculated streak values directly
                display_streak25 = streak25_val
                display_streak35 = streak35_val
                display_streak45 = streak45_val
                
                # Insert with xG data from database
                item_id = str(gid) if gid else f"game_{idx}"
                try:
                    # Show streak value: if > 0 show the number, if 0 and game is over X.5 show "0", otherwise show empty
                    tree.insert("", tk.END, iid=item_id, values=(gid, home, away, score_home, score_away, xg_home_str, xg_away_str, over25, over35, over45, str(display_streak25) if display_streak25 > 0 else ("0" if total_goals > 2.5 else ""), str(display_streak35) if display_streak35 > 0 else ("0" if total_goals > 3.5 else ""), str(display_streak45) if display_streak45 > 0 else ("0" if total_goals > 4.5 else ""), date, status))
                    inserted_count += 1
                    if (idx + 1) % 50 == 0:
                        popup.update_idletasks()  # Update UI periodically
                        print(f"[DEBUG] Inserted {idx + 1}/{len(filtered_games)} games")
                    
                    # Store color info for individual cells
                    # Color logic: 
                    # - Grün: > 4.5 (5+ Goals)
                    # - Gelb: == 4 Goals
                    # - Orange: == 3 Goals
                    # - Rot: < 2.5 (0, 1, 2 Goals)
                    if not hasattr(self, '_game_colors'):
                        self._game_colors = {}
                    
                    # Determine color category based on total goals
                    if total_goals > 4.5:
                        color_category = 'green'  # 5+ Goals
                    elif total_goals == 4:
                        color_category = 'yellow'  # Exactly 4 Goals
                    elif total_goals == 3:
                        color_category = 'orange'  # Exactly 3 Goals
                    else:  # total_goals < 2.5 (0, 1, or 2 Goals)
                        color_category = 'red'
                    
                    self._game_colors[item_id] = {
                        'over25': total_goals > 2.5,
                        'over35': total_goals > 3.5,
                        'over45': total_goals > 4.5,
                        'color_category': color_category,
                        'total_goals': total_goals
                    }
                except Exception as e:
                    print(f"[ERROR] Failed to insert game {gid}: {e}")
                    print(f"[DEBUG] Values: gid={gid}, home={home}, away={away}, score_home={score_home}, score_away={score_away}")
                    import traceback
                    traceback.print_exc()
                    continue
            
            print(f"[DEBUG] Successfully inserted {inserted_count}/{len(filtered_games)} games into treeview")
            
            # Verify items are in treeview
            tree_items = tree.get_children()
            print(f"[DEBUG] Treeview.get_children() returned {len(tree_items)} items")
            if len(tree_items) > 0:
                first_item = tree.item(tree_items[0])
                print(f"[DEBUG] First item in treeview: {first_item}")
            else:
                print(f"[ERROR] No items in treeview after insertion! inserted_count={inserted_count}, filtered_games={len(filtered_games)}")
            
            # Apply individual cell coloring after all items are inserted
            # Note: Due to ttk.Treeview limitations, we can only color rows, not individual cells
            # For true per-cell coloring, we would need a custom Canvas-based widget
            if len(tree_items) > 0:
                self._apply_cell_colors_workaround(tree)
            
            # Update window title with statistics
            xg_count = sum(1 for g in filtered_games if g.get("calculated_xg_home") is not None and g.get("calculated_xg_away") is not None)
            popup.title(f"Finished Games for {league_name} (Year {selected_year}) - {len(filtered_games)} games ({xg_count} mit xG)")
            print(f"[SUCCESS] Successfully displayed {len(filtered_games)} games in popup window")
            print(f"[DEBUG] Treeview has {len(tree.get_children())} items after insertion")
            
            # Force UI update - ensure treeview is visible
            popup.update_idletasks()
            tree.update_idletasks()
            popup.update()
            
            # Final update to ensure everything is visible
            popup.update_idletasks()
            popup.update()
            
            # Create goals chart grouped by month for displayed years
            # Load games for all years
            all_years_games = []
            for year in [int(y) for y in self.years_to_show]:
                try:
                    year_rows = conn.execute("""
                        SELECT id, date, home_team_name, away_team_name,
                               home_ft_result, away_ft_result, status, status_name,
                               country_name, league_name, league_id, season_year,
                               calculated_xg_home, calculated_xg_away
                        FROM games 
                        WHERE league_id = ?
                          AND season_year = ?
                          AND home_ft_result IS NOT NULL 
                          AND away_ft_result IS NOT NULL
                        ORDER BY date ASC
                    """, (league_id_int, year)).fetchall()
                    
                    for row in year_rows:
                        game_dict = {
                            'id': row['id'],
                            'date': row['date'],
                            'home_team_name': row['home_team_name'],
                            'away_team_name': row['away_team_name'],
                            'home_ft_result': row['home_ft_result'] if row['home_ft_result'] is not None else 0,
                            'away_ft_result': row['away_ft_result'] if row['away_ft_result'] is not None else 0,
                            'season_year': row['season_year'],
                            'calculated_xg_home': row['calculated_xg_home'],
                            'calculated_xg_away': row['calculated_xg_away'],
                        }
                        all_years_games.append(game_dict)
                except Exception as e:
                    print(f"[WARNING] Could not load games for year {year}: {e}")
            
            self._create_goals_chart(chart_tab, all_years_games, league_name)
            self._create_goals_per_game_chart(goals_per_game_tab, all_years_games, league_name, league_id_int, conn)
            
            # Populate Pro Spiel and Pro Runde tabs (with season selector)
            self._create_per_game_stats_tab(per_game_tab, filtered_games, league_name, selected_year, league_id_int, conn)
            self._create_per_round_stats_tab(per_round_tab, league_id_int, conn, league_name, year_int)
        except Exception as e:
            print(f"[ERROR] Exception in show_games_list: {e}")
            import traceback
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to load games: {e}\n\nCheck console for details.")

    def get_games_count_for_league(self, league_id, year):
        """Get the number of games for a league in a specific year - first from database, then API"""
        # First try database
        try:
            from database import DatabaseManager
            import sqlite3
            db_manager = DatabaseManager("data/flashscore.db")
            conn = db_manager.get_connection()
            conn.row_factory = sqlite3.Row
            
            # Set timeout for this connection to handle locks
            try:
                conn.execute("PRAGMA busy_timeout = 30000")  # 30 seconds timeout
            except:
                pass
            
            # Check if league_id exists in database - count ALL games (finished and unfinished)
            total_games_count = conn.execute("""
                SELECT COUNT(*) as count
                FROM games 
                WHERE league_id = ? AND season_year = ?
            """, (league_id, int(year))).fetchone()
            
            # Count finished games (with results) for statistics
            finished_games_count = conn.execute("""
                SELECT COUNT(*) as count
                FROM games 
                WHERE league_id = ? AND season_year = ?
                  AND home_ft_result IS NOT NULL 
                  AND away_ft_result IS NOT NULL
            """, (league_id, int(year))).fetchone()
            
            # Debug: Check what years are actually in DB for this league
            if total_games_count and total_games_count['count'] == 0:
                # Check what years exist for this league
                years_in_db = conn.execute("""
                    SELECT DISTINCT season_year, COUNT(*) as cnt
                    FROM games 
                    WHERE league_id = ?
                    GROUP BY season_year
                    ORDER BY season_year DESC
                """, (league_id,)).fetchall()
                if years_in_db:
                    print(f"[DEBUG] League {league_id}: No games for year {year}, but found years: {[r['season_year'] for r in years_in_db]}")
            
            if total_games_count and total_games_count['count'] > 0:
                # Get detailed statistics from database - only for finished games
                # Count finished games that have results (home_ft_result AND away_ft_result are not NULL)
                # This ensures we count all finished games regardless of status
                stats = conn.execute("""
                    SELECT 
                        COUNT(*) as total_finished,
                        SUM(CASE WHEN (COALESCE(home_ft_result, 0) + COALESCE(away_ft_result, 0)) > 2.5 THEN 1 ELSE 0 END) as over25,
                        SUM(CASE WHEN (COALESCE(home_ft_result, 0) + COALESCE(away_ft_result, 0)) > 3.5 THEN 1 ELSE 0 END) as over35,
                        SUM(CASE WHEN (COALESCE(home_ft_result, 0) + COALESCE(away_ft_result, 0)) > 4.5 THEN 1 ELSE 0 END) as over45
                    FROM games 
                    WHERE league_id = ? AND season_year = ? 
                      AND home_ft_result IS NOT NULL 
                      AND away_ft_result IS NOT NULL
                """, (league_id, int(year))).fetchone()
                
                # Get games for streak calculation - ONLY for the specified year
                # Calculate total_goals from home_ft_result and away_ft_result
                # Only include games that have both results (finished games) and match the year
                # Streak is calculated from the most recent game backwards within the year
                all_games_for_streak = conn.execute("""
                    SELECT 
                        COALESCE(home_ft_result, 0) + COALESCE(away_ft_result, 0) as total_goals,
                        home_ft_result,
                        away_ft_result,
                        date,
                        season_year
                    FROM games 
                    WHERE league_id = ? 
                      AND season_year = ?
                      AND home_ft_result IS NOT NULL 
                      AND away_ft_result IS NOT NULL
                    ORDER BY date DESC
                """, (league_id, int(year))).fetchall()
                
                # Get last 10 and last 20 games for statistics (from the specified year)
                last_games = all_games_for_streak[:20] if len(all_games_for_streak) >= 20 else all_games_for_streak
                
                # Calculate last 10 and last 20 stats
                last10_total = min(10, len(last_games))
                last10_over25_count = sum(1 for g in last_games[:10] if (g['total_goals'] or 0) > 2.5) if len(last_games) >= 10 else 0
                last10_over35_count = sum(1 for g in last_games[:10] if (g['total_goals'] or 0) > 3.5) if len(last_games) >= 10 else 0
                last10_over45_count = sum(1 for g in last_games[:10] if (g['total_goals'] or 0) > 4.5) if len(last_games) >= 10 else 0
                last20_total = min(20, len(last_games))
                last20_over25_count = sum(1 for g in last_games if (g['total_goals'] or 0) > 2.5) if len(last_games) >= 20 else 0
                last20_over35_count = sum(1 for g in last_games if (g['total_goals'] or 0) > 3.5) if len(last_games) >= 20 else 0
                last20_over45_count = sum(1 for g in last_games if (g['total_goals'] or 0) > 4.5) if len(last_games) >= 20 else 0
                
                # Calculate percentages
                # Use total_games_count for display (all games), but stats only for finished games
                total_all_games = total_games_count['count'] if total_games_count else 0
                total_finished = stats['total_finished'] or 0
                over25_count = stats['over25'] or 0
                over35_count = stats['over35'] or 0
                over45_count = stats['over45'] or 0
                
                # Use total_finished for percentage calculations (since we only have stats for finished games)
                total = total_finished
                
                over25_pct = (over25_count / total * 100) if total > 0 else 0
                over35_pct = (over35_count / total * 100) if total > 0 else 0
                over45_pct = (over45_count / total * 100) if total > 0 else 0
                
                last10_over25_pct = (last10_over25_count / last10_total * 100) if last10_total > 0 else 0
                last10_over35_pct = (last10_over35_count / last10_total * 100) if last10_total > 0 else 0
                last10_over45_pct = (last10_over45_count / last10_total * 100) if last10_total > 0 else 0
                
                last20_over25_pct = (last20_over25_count / last20_total * 100) if last20_total > 0 else 0
                last20_over35_pct = (last20_over35_count / last20_total * 100) if last20_total > 0 else 0
                last20_over45_pct = (last20_over45_count / last20_total * 100) if last20_total > 0 else 0
                
                # Calculate streaks - count consecutive games from the most recent game within the year
                # If last game > X.5: count how many consecutive games have > X.5
                # If last game <= X.5: count how many consecutive games have <= X.5 (negative streak)
                # Use all games from the specified year, ordered by date DESC (most recent first)
                streak25 = 0
                streak35 = 0
                streak45 = 0
                if all_games_for_streak:
                    # Streak 2.5: NUR für negative Zahlen (<= 2.5 goals)
                    # Positive Zahlen (größer als 0) werden nicht berücksichtigt
                    first_game_total = all_games_for_streak[0]['total_goals'] or 0
                    if first_game_total <= 2.5:
                        # Count consecutive games with <= 2.5 goals (negative streak)
                        for g in all_games_for_streak:
                            total = g['total_goals'] or 0
                            if total <= 2.5:
                                streak25 += 1
                            else:
                                break
                        # Make it negative to indicate "under" streak
                        streak25 = -streak25
                    # Wenn letztes Spiel > 2.5, dann streak25 = 0 (nicht berücksichtigen)
                    
                    # Streak 3.5: NUR für negative Zahlen (<= 3.5 goals)
                    first_game_total = all_games_for_streak[0]['total_goals'] or 0
                    if first_game_total <= 3.5:
                        for g in all_games_for_streak:
                            total = g['total_goals'] or 0
                            if total <= 3.5:
                                streak35 += 1
                            else:
                                break
                        streak35 = -streak35
                    # Wenn letztes Spiel > 3.5, dann streak35 = 0 (nicht berücksichtigen)
                    
                    # Streak 4.5: NUR für negative Zahlen (<= 4.5 goals)
                    first_game_total = all_games_for_streak[0]['total_goals'] or 0
                    if first_game_total <= 4.5:
                        for g in all_games_for_streak:
                            total = g['total_goals'] or 0
                            if total <= 4.5:
                                streak45 += 1
                            else:
                                break
                        streak45 = -streak45
                    # Wenn letztes Spiel > 4.5, dann streak45 = 0 (nicht berücksichtigen)
                
                result_dict = {
                    "total": total_all_games,  # Return total ALL games (finished + unfinished) for display
                    "total_finished": total_finished,  # Keep track of finished games for statistics
                    "over25": f"{over25_pct:.1f}%",
                    "over35": f"{over35_pct:.1f}%",
                    "over45": f"{over45_pct:.1f}%",
                    "last10_over25": f"{last10_over25_pct:.1f}%",
                    "last10_over35": f"{last10_over35_pct:.1f}%",
                    "last10_over45": f"{last10_over45_pct:.1f}%",
                    "last20_over25": f"{last20_over25_pct:.1f}%",
                    "last20_over35": f"{last20_over35_pct:.1f}%",
                    "last20_over45": f"{last20_over45_pct:.1f}%",
                    "streak25": streak25,
                    "streak35": streak35,
                    "streak45": streak45
                }
                
                conn.close()
                return result_dict
        except Exception as e:
            print(f"[ERROR] Error getting games count from database: {e}")
            import traceback
            traceback.print_exc()
        
        # Kein API-Fallback mehr - nur Datenbank
        # Return empty result if database fails
        return {
            "total": 0,
            "total_finished": 0,
            "over25": "0.0%",
            "over35": "0.0%",
            "over45": "0.0%",
            "last10_over25": "0.0%",
            "last10_over35": "0.0%",
            "last10_over45": "0.0%",
            "last20_over25": "0.0%",
            "last20_over35": "0.0%",
            "last20_over45": "0.0%",
            "streak25": 0,
            "streak35": 0,
            "streak45": 0
        }
    
    def load_xg_data_async(self, tree, filtered_games, client, popup, progress_label, load_xg_button):
        """Load xG data asynchronously with rate limiting"""
        import time
        
        def load_xg_thread():
            total_games = len(filtered_games)
            progress_label.config(text="Loading xG data... (0/0)", fg="blue")
            progress_label.pack(pady=2)
            load_xg_button.config(state="disabled", text="Loading xG...")
            
            for idx, game in enumerate(filtered_games):
                gid = game.get("id") or game.get("Id") or ""
                if not gid:
                    continue
                
                try:
                    # Update progress
                    progress_label.config(text=f"Loading xG data... ({idx + 1}/{total_games})")
                    popup.update()
                    
                    # First try to get xG from database
                    xg_home = "N/A"
                    xg_away = "N/A"
                    
                    try:
                        from database import DatabaseManager
                        db_manager = DatabaseManager("data/flashscore.db")
                        conn = db_manager.get_connection()
                        conn.row_factory = sqlite3.Row
                        
                        game_row = conn.execute(
                            "SELECT calculated_xg_home, calculated_xg_away FROM games WHERE id = ?",
                            (int(gid),)
                        ).fetchone()
                        conn.close()
                        
                        if game_row:
                            calc_xg_home = game_row['calculated_xg_home']
                            calc_xg_away = game_row['calculated_xg_away']
                            if calc_xg_home is not None:
                                xg_home = f"{calc_xg_home:.2f}"
                            if calc_xg_away is not None:
                                xg_away = f"{calc_xg_away:.2f}"
                    except Exception as e:
                        print(f"[WARNING] Error loading xG from DB for game {gid}: {e}")
                    
                    # Fallback to API only if not in database
                    if xg_home == "N/A" or xg_away == "N/A":
                        # Fetch game details with rate limiting (small delay between requests)
                        if idx > 0:
                            time.sleep(0.3)  # 300ms delay between requests to avoid rate limiting
                        
                        game_details = client.get_game(int(gid))
                        
                        # Extract xG from statistics
                        if isinstance(game_details, dict):
                            data = game_details.get("data", {})
                            if isinstance(data, dict):
                                statistics = data.get("statistics", {})
                                if isinstance(statistics, dict):
                                    calc_xg_home = statistics.get("calculatedXgHome")
                                    calc_xg_away = statistics.get("calculatedXgAway")
                                    if calc_xg_home is not None:
                                        xg_home = f"{calc_xg_home:.2f}"
                                    if calc_xg_away is not None:
                                        xg_away = f"{calc_xg_away:.2f}"
                    
                    # Update tree item
                    item_id = str(gid)
                    if tree.exists(item_id):
                        current_values = list(tree.item(item_id, "values"))
                        current_tags = tree.item(item_id, "tags")
                        # Update xG columns (index 4 and 5)
                        current_values[4] = xg_home
                        current_values[5] = xg_away
                        tree.item(item_id, values=current_values, tags=current_tags)
                    
                except Exception as e:
                    # If xG fetch fails, keep N/A
                    print(f"Error fetching xG for game {gid}: {e}")
                    continue
            
            # Hide progress and re-enable button
            progress_label.config(text="xG data loaded!", fg="green")
            load_xg_button.config(state="normal", text="Reload xG Data")
            popup.after(2000, lambda: progress_label.config(text=""))
        
        # Start loading in a separate thread
        thread = threading.Thread(target=load_xg_thread, daemon=True)
        thread.start()
    
    def _apply_cell_colors_workaround(self, tree):
        """Apply cell coloring workaround - colors cells by modifying the tree after rendering"""
        # Since ttk.Treeview doesn't support per-cell coloring, we use a workaround:
        # We'll use the tree's styling system, but note that it only supports row-level coloring
        # For true per-cell coloring, we would need a custom Canvas-based widget
        
        if not hasattr(self, '_game_colors'):
            return
        
        # Configure tags for goal-based coloring
        # Grün: > 4.5 (5+ Goals)
        # Gelb: == 4 Goals
        # Orange: == 3 Goals
        # Rot: < 2.5 (0, 1, 2 Goals)
        tree.tag_configure('green', background="#90EE90")   # Light green - 5+ Goals
        tree.tag_configure('yellow', background="#FFFF99")  # Light yellow - 4 Goals
        tree.tag_configure('orange', background="#FFA500")   # Orange - 3 Goals
        tree.tag_configure('red', background="#FFB6C1")     # Light red - 0, 1, 2 Goals
        
        # Apply tags based on total goals
        # Note: This colors the whole row, not individual cells
        # Individual cell coloring would require a custom widget implementation
        for item_id, colors in self._game_colors.items():
            if not tree.exists(item_id):
                continue
            
            # Use color_category from stored data
            color_category = colors.get('color_category', 'red')
            tree.item(item_id, tags=(color_category,))
        
        # Store color info for potential future custom widget implementation
        # The individual cell colors (over35, over45) are shown via ✓/✗ markers
    
    def _create_per_game_stats_tab(self, parent, games, league_name, selected_year, league_id=None, conn=None):
        """Create a chart showing goal statistics per game with season selector"""
        if not HAS_MATPLOTLIB:
            no_matplotlib_label = tk.Label(parent, 
                                          text="Matplotlib nicht installiert.\nBitte installieren Sie es mit: pip install matplotlib",
                                          font=("Arial", 12), fg="red")
            no_matplotlib_label.pack(expand=True)
            return
        
        # Season selector frame at top
        selector_frame = tk.Frame(parent)
        selector_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(selector_frame, text="Saison:", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=(0, 5))
        
        season_var = tk.StringVar(value=str(selected_year))
        season_combo = ttk.Combobox(selector_frame, textvariable=season_var,
                                    values=list(self.years_to_show), state="readonly", width=8)
        season_combo.pack(side=tk.LEFT, padx=5)
        
        # Chart container (will be cleared and redrawn on season change)
        chart_container = tk.Frame(parent)
        chart_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        def draw_per_game_chart(game_data, year_str):
            """Draw or redraw the per-game chart"""
            # Clear previous chart
            for widget in chart_container.winfo_children():
                widget.destroy()
            
            if not game_data:
                no_data_label = tk.Label(chart_container, text=f"Keine Spiele für Saison {year_str}", 
                                        fg="gray", font=("Arial", 12))
                no_data_label.pack(expand=True)
                return
            
            # Sort games by date (oldest first for chart timeline)
            sorted_games = sorted(game_data, key=lambda g: g.get("date", ""))
            
            # Extract data
            game_labels = []
            goals_list = []
            home_goals_list = []
            away_goals_list = []
            
            for idx, game in enumerate(sorted_games):
                h = int(game.get("home_ft_result") or game.get("homeResult") or game.get("score_home") or 0)
                a = int(game.get("away_ft_result") or game.get("awayResult") or game.get("score_away") or 0)
                total = h + a
                
                game_labels.append(f"{idx+1}")
                goals_list.append(total)
                home_goals_list.append(h)
                away_goals_list.append(a)
            
            # Calculate running average
            running_avg = []
            running_sum = 0
            for i, g in enumerate(goals_list):
                running_sum += g
                running_avg.append(running_sum / (i + 1))
            
            # Statistics
            total_games = len(goals_list)
            avg_goals = sum(goals_list) / total_games if total_games else 0
            max_goals = max(goals_list) if goals_list else 0
            min_goals = min(goals_list) if goals_list else 0
            over25 = sum(1 for g in goals_list if g > 2)
            over35 = sum(1 for g in goals_list if g > 3)
            over45 = sum(1 for g in goals_list if g > 4)
            
            # Create figure
            fig = Figure(figsize=(14, 7), dpi=100)
            ax1 = fig.add_subplot(111)
            
            x = list(range(len(goals_list)))
            
            # Stacked bar: home goals (bottom) + away goals (top)
            bars_home = ax1.bar(x, home_goals_list, color='#3498db', alpha=0.8, label='Heim Tore', edgecolor='white', linewidth=0.5)
            bars_away = ax1.bar(x, away_goals_list, bottom=home_goals_list, color='#e74c3c', alpha=0.8, label='Gast Tore', edgecolor='white', linewidth=0.5)
            
            # Color the bar edges based on total goals
            for i, (bh, ba) in enumerate(zip(bars_home, bars_away)):
                total = goals_list[i]
                if total >= 5:
                    edge_color = '#27ae60'
                elif total == 4:
                    edge_color = '#f39c12'
                elif total == 3:
                    edge_color = '#e67e22'
                else:
                    edge_color = '#c0392b'
                bh.set_edgecolor(edge_color)
                ba.set_edgecolor(edge_color)
                bh.set_linewidth(1.5)
                ba.set_linewidth(1.5)
            
            # Running average line
            ax1.plot(x, running_avg, color='#2c3e50', linewidth=2, linestyle='-', label=f'Ø Laufend ({avg_goals:.2f})', zorder=5)
            
            # Threshold lines
            ax1.axhline(y=2.5, color='#e74c3c', linewidth=1, linestyle='--', alpha=0.6, label='2.5 Linie')
            ax1.axhline(y=3.5, color='#e67e22', linewidth=1, linestyle='--', alpha=0.6, label='3.5 Linie')
            
            # Total goals number on top of each bar
            for i, total in enumerate(goals_list):
                ax1.text(i, total + 0.1, str(total), ha='center', va='bottom', fontsize=7, fontweight='bold')
            
            # Labels and title
            ax1.set_xlabel('Spiel Nr.', fontsize=11, fontweight='bold')
            ax1.set_ylabel('Tore', fontsize=11, fontweight='bold')
            ax1.set_title(f'Tore pro Spiel – {league_name} (Saison {year_str})', 
                          fontsize=13, fontweight='bold', pad=15)
            
            # X-axis ticks
            if len(x) > 40:
                step = max(1, len(x) // 20)
                ax1.set_xticks(x[::step])
                ax1.set_xticklabels(game_labels[::step], fontsize=7)
            else:
                ax1.set_xticks(x)
                ax1.set_xticklabels(game_labels, fontsize=7)
            
            ax1.set_ylim(0, max_goals + 1.5)
            ax1.grid(True, alpha=0.3, axis='y')
            ax1.legend(loc='upper right', fontsize=8, framealpha=0.9)
            
            # Statistics text box
            stats_text = (f"Spiele: {total_games}\n"
                         f"Tore gesamt: {sum(goals_list)}\n"
                         f"Ø Tore/Spiel: {avg_goals:.2f}\n"
                         f"Min: {min_goals} | Max: {max_goals}\n"
                         f"Over 2.5: {over25} ({over25/total_games*100:.0f}%)\n"
                         f"Over 3.5: {over35} ({over35/total_games*100:.0f}%)\n"
                         f"Over 4.5: {over45} ({over45/total_games*100:.0f}%)")
            
            ax1.text(0.02, 0.98, stats_text, transform=ax1.transAxes,
                    fontsize=9, verticalalignment='top', horizontalalignment='left',
                    bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.9))
            
            fig.tight_layout()
            
            # Create canvas
            canvas = FigureCanvasTkAgg(fig, chart_container)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            
            # Toolbar
            try:
                from matplotlib.backends.backend_tkagg import NavigationToolbar2Tk
                toolbar = NavigationToolbar2Tk(canvas, chart_container)
                toolbar.update()
                toolbar.pack(side=tk.BOTTOM, fill=tk.X)
            except Exception as e:
                print(f"[WARNING] Could not create toolbar: {e}")
        
        def on_season_change(event=None):
            """Handle season change"""
            new_year = season_var.get()
            year_int = int(new_year)
            if conn and league_id:
                try:
                    rows = conn.execute("""
                        SELECT id, date, home_team_name, away_team_name,
                               home_ft_result, away_ft_result, season_year,
                               calculated_xg_home, calculated_xg_away
                        FROM games 
                        WHERE league_id = ?
                          AND season_year = ?
                          AND home_ft_result IS NOT NULL 
                          AND away_ft_result IS NOT NULL
                        ORDER BY date ASC
                    """, (league_id, year_int)).fetchall()
                    
                    new_games = []
                    for row in rows:
                        new_games.append({
                            'id': row['id'],
                            'date': row['date'],
                            'home_team_name': row['home_team_name'],
                            'away_team_name': row['away_team_name'],
                            'home_ft_result': row['home_ft_result'] if row['home_ft_result'] is not None else 0,
                            'away_ft_result': row['away_ft_result'] if row['away_ft_result'] is not None else 0,
                            'season_year': row['season_year'],
                        })
                    draw_per_game_chart(new_games, new_year)
                except Exception as e:
                    print(f"[ERROR] Failed to load games for season {new_year}: {e}")
            else:
                draw_per_game_chart(games, new_year)
        
        season_combo.bind("<<ComboboxSelected>>", on_season_change)
        
        # Draw initial chart
        draw_per_game_chart(games, str(selected_year))
    
    def _create_per_round_stats_tab(self, parent, league_id, conn, league_name, year_int):
        """Create a chart showing goal statistics per round/matchday with season selector"""
        if not HAS_MATPLOTLIB:
            no_matplotlib_label = tk.Label(parent, 
                                          text="Matplotlib nicht installiert.\nBitte installieren Sie es mit: pip install matplotlib",
                                          font=("Arial", 12), fg="red")
            no_matplotlib_label.pack(expand=True)
            return
        
        if not conn:
            no_data_label = tk.Label(parent, text="Keine Datenbankverbindung", fg="gray", font=("Arial", 12))
            no_data_label.pack(expand=True)
            return
        
        # Season selector frame at top
        selector_frame = tk.Frame(parent)
        selector_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(selector_frame, text="Saison:", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=(0, 5))
        
        season_var = tk.StringVar(value=str(year_int))
        season_combo = ttk.Combobox(selector_frame, textvariable=season_var,
                                    values=list(self.years_to_show), state="readonly", width=8)
        season_combo.pack(side=tk.LEFT, padx=5)
        
        # Chart container (will be cleared and redrawn on season change)
        chart_container = tk.Frame(parent)
        chart_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        def _extract_round_number(round_name):
            """Try to extract a numeric round number from round_name for sorting"""
            import re
            if not round_name:
                return 9999
            # Try to find number at end like "Round 5", "Clausura - 10", etc.
            match = re.search(r'(\d+)\s*$', str(round_name))
            if match:
                return int(match.group(1))
            return 9999
        
        def draw_per_round_chart(sel_year):
            """Draw or redraw the per-round chart"""
            # Clear previous chart
            for widget in chart_container.winfo_children():
                widget.destroy()
            
            try:
                from collections import OrderedDict
                
                rows = conn.execute("""
                    SELECT round_name, date,
                           home_team_name, away_team_name,
                           home_ft_result, away_ft_result
                    FROM games 
                    WHERE league_id = ?
                      AND season_year = ?
                      AND home_ft_result IS NOT NULL 
                      AND away_ft_result IS NOT NULL
                    ORDER BY date ASC
                """, (league_id, sel_year)).fetchall()
                
                if not rows:
                    no_data_label = tk.Label(chart_container, text=f"Keine Spiele für Saison {sel_year} gefunden", 
                                            fg="gray", font=("Arial", 12))
                    no_data_label.pack(expand=True)
                    return
                
                # Group games by round
                rounds = OrderedDict()
                for row in rows:
                    rnd = row['round_name'] if row['round_name'] else "Unbekannt"
                    if rnd not in rounds:
                        rounds[rnd] = {
                            'games': 0, 'total_goals': 0, 'home_goals': 0, 'away_goals': 0,
                            'over25': 0, 'over35': 0, 'over45': 0,
                        }
                    
                    h = int(row['home_ft_result']) if row['home_ft_result'] is not None else 0
                    a = int(row['away_ft_result']) if row['away_ft_result'] is not None else 0
                    total = h + a
                    
                    rounds[rnd]['games'] += 1
                    rounds[rnd]['total_goals'] += total
                    rounds[rnd]['home_goals'] += h
                    rounds[rnd]['away_goals'] += a
                    if total > 2:
                        rounds[rnd]['over25'] += 1
                    if total > 3:
                        rounds[rnd]['over35'] += 1
                    if total > 4:
                        rounds[rnd]['over45'] += 1
                
                # Sort rounds by round number
                sorted_round_names = sorted(rounds.keys(), key=_extract_round_number)
                
                # Prepare data for chart
                round_labels = []
                total_goals_per_round = []
                home_goals_per_round = []
                away_goals_per_round = []
                avg_per_round = []
                games_per_round = []
                
                for rnd_name in sorted_round_names:
                    data = rounds[rnd_name]
                    # Short label: extract just the number if possible
                    import re
                    match = re.search(r'(\d+)\s*$', str(rnd_name))
                    label = match.group(1) if match else rnd_name[:10]
                    
                    round_labels.append(label)
                    total_goals_per_round.append(data['total_goals'])
                    home_goals_per_round.append(data['home_goals'])
                    away_goals_per_round.append(data['away_goals'])
                    games_count = data['games']
                    games_per_round.append(games_count)
                    avg_per_round.append(data['total_goals'] / games_count if games_count > 0 else 0)
                
                # Statistics
                all_goals = sum(total_goals_per_round)
                all_games = sum(games_per_round)
                total_rounds = len(sorted_round_names)
                avg_goals_round = all_goals / total_rounds if total_rounds else 0
                avg_goals_game = all_goals / all_games if all_games else 0
                max_round_goals = max(total_goals_per_round) if total_goals_per_round else 0
                min_round_goals = min(total_goals_per_round) if total_goals_per_round else 0
                
                # Create figure with two subplots
                fig = Figure(figsize=(14, 8), dpi=100)
                
                # Top subplot: Total goals per round (stacked bar)
                ax1 = fig.add_subplot(211)
                x = list(range(len(sorted_round_names)))
                
                bars_home = ax1.bar(x, home_goals_per_round, color='#3498db', alpha=0.8, label='Heim Tore', edgecolor='white', linewidth=0.5)
                bars_away = ax1.bar(x, away_goals_per_round, bottom=home_goals_per_round, color='#e74c3c', alpha=0.8, label='Gast Tore', edgecolor='white', linewidth=0.5)
                
                # Color edges based on total
                for i in range(len(x)):
                    total = total_goals_per_round[i]
                    avg = avg_per_round[i]
                    if avg >= 3.5:
                        edge_color = '#27ae60'
                    elif avg >= 2.5:
                        edge_color = '#f39c12'
                    else:
                        edge_color = '#c0392b'
                    bars_home[i].set_edgecolor(edge_color)
                    bars_away[i].set_edgecolor(edge_color)
                    bars_home[i].set_linewidth(1.5)
                    bars_away[i].set_linewidth(1.5)
                
                # Average line per round
                running_avg_round = []
                running_sum = 0
                for i, g in enumerate(total_goals_per_round):
                    running_sum += g
                    running_avg_round.append(running_sum / (i + 1))
                ax1.plot(x, running_avg_round, color='#2c3e50', linewidth=2, linestyle='-', label=f'Ø Laufend', zorder=5)
                
                # Total goals number on top of each bar
                for i, total in enumerate(total_goals_per_round):
                    ax1.text(i, total + 0.3, str(total), ha='center', va='bottom', fontsize=7, fontweight='bold')
                
                ax1.set_ylabel('Tore gesamt', fontsize=10, fontweight='bold')
                ax1.set_title(f'Tore pro Runde – {league_name} (Saison {sel_year})', 
                              fontsize=13, fontweight='bold', pad=10)
                
                if len(x) > 30:
                    step = max(1, len(x) // 20)
                    ax1.set_xticks(x[::step])
                    ax1.set_xticklabels([round_labels[i] for i in range(0, len(round_labels), step)], fontsize=7)
                else:
                    ax1.set_xticks(x)
                    ax1.set_xticklabels(round_labels, fontsize=7)
                
                ax1.set_ylim(0, max_round_goals + 3)
                ax1.grid(True, alpha=0.3, axis='y')
                ax1.legend(loc='upper right', fontsize=8, framealpha=0.9)
                
                # Statistics text box
                stats_text = (f"Runden: {total_rounds} | Spiele: {all_games}\n"
                             f"Tore gesamt: {all_goals}\n"
                             f"Ø Tore/Runde: {avg_goals_round:.1f}\n"
                             f"Ø Tore/Spiel: {avg_goals_game:.2f}\n"
                             f"Min Runde: {min_round_goals} | Max Runde: {max_round_goals}")
                ax1.text(0.02, 0.98, stats_text, transform=ax1.transAxes,
                        fontsize=8, verticalalignment='top', horizontalalignment='left',
                        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.9))
                
                # Bottom subplot: Average goals per game per round (line chart)
                ax2 = fig.add_subplot(212)
                
                ax2.bar(x, avg_per_round, color='#9b59b6', alpha=0.7, edgecolor='white', linewidth=0.5, label='Ø Tore/Spiel')
                ax2.axhline(y=2.5, color='#e74c3c', linewidth=1, linestyle='--', alpha=0.6, label='2.5 Linie')
                ax2.axhline(y=3.5, color='#e67e22', linewidth=1, linestyle='--', alpha=0.6, label='3.5 Linie')
                
                # Running avg line
                running_avg_game = []
                running_sum2 = 0
                running_count2 = 0
                for i in range(len(avg_per_round)):
                    running_sum2 += total_goals_per_round[i]
                    running_count2 += games_per_round[i]
                    running_avg_game.append(running_sum2 / running_count2 if running_count2 > 0 else 0)
                ax2.plot(x, running_avg_game, color='#2c3e50', linewidth=2, linestyle='-', label=f'Ø Gesamt ({avg_goals_game:.2f})', zorder=5)
                
                # Value on each bar
                for i, avg in enumerate(avg_per_round):
                    ax2.text(i, avg + 0.08, f"{avg:.1f}", ha='center', va='bottom', fontsize=6, fontweight='bold')
                
                ax2.set_xlabel('Runde', fontsize=10, fontweight='bold')
                ax2.set_ylabel('Ø Tore/Spiel', fontsize=10, fontweight='bold')
                ax2.set_title('Durchschnitt Tore pro Spiel je Runde', fontsize=11, fontweight='bold', pad=5)
                
                if len(x) > 30:
                    step = max(1, len(x) // 20)
                    ax2.set_xticks(x[::step])
                    ax2.set_xticklabels([round_labels[i] for i in range(0, len(round_labels), step)], fontsize=7)
                else:
                    ax2.set_xticks(x)
                    ax2.set_xticklabels(round_labels, fontsize=7)
                
                max_avg = max(avg_per_round) if avg_per_round else 5
                ax2.set_ylim(0, max_avg + 1)
                ax2.grid(True, alpha=0.3, axis='y')
                ax2.legend(loc='upper right', fontsize=8, framealpha=0.9)
                
                fig.tight_layout()
                
                # Create canvas
                canvas = FigureCanvasTkAgg(fig, chart_container)
                canvas.draw()
                canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
                
                # Toolbar
                try:
                    from matplotlib.backends.backend_tkagg import NavigationToolbar2Tk
                    toolbar = NavigationToolbar2Tk(canvas, chart_container)
                    toolbar.update()
                    toolbar.pack(side=tk.BOTTOM, fill=tk.X)
                except Exception as e:
                    print(f"[WARNING] Could not create toolbar: {e}")
                    
            except Exception as e:
                print(f"[ERROR] Error creating per-round chart: {e}")
                import traceback
                traceback.print_exc()
                error_label = tk.Label(chart_container, text=f"Fehler: {e}", fg="red", font=("Arial", 11))
                error_label.pack(expand=True)
        
        def on_season_change(event=None):
            """Handle season change for per-round chart"""
            new_year = int(season_var.get())
            draw_per_round_chart(new_year)
        
        season_combo.bind("<<ComboboxSelected>>", on_season_change)
        
        # Draw initial chart
        draw_per_round_chart(year_int)
    
    def _create_goals_chart(self, parent, games, league_name):
        """Create a chart showing average goals per month with season switcher"""
        if not HAS_MATPLOTLIB:
            no_matplotlib_label = tk.Label(parent, 
                                          text="Matplotlib nicht installiert.\nBitte installieren Sie es mit: pip install matplotlib",
                                          font=("Arial", 12), fg="red")
            no_matplotlib_label.pack(expand=True)
            return
        
        if not games:
            no_data_label = tk.Label(parent, text="Keine Spiele zum Anzeigen", fg="gray", font=("Arial", 12))
            no_data_label.pack(expand=True)
            return
        
        # Create control frame for season selection
        control_frame = tk.Frame(parent)
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(control_frame, text="Saison:", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=5)
        
        season_var = tk.StringVar(value="Alle")
        season_options = ["Alle"] + list(self.years_to_show)
        season_combo = ttk.Combobox(control_frame, textvariable=season_var, values=season_options, 
                                   state="readonly", width=10)
        season_combo.pack(side=tk.LEFT, padx=5)
        
        # Chart frame
        chart_frame = tk.Frame(parent)
        chart_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        def update_chart(selected_season="Alle"):
            """Update chart based on selected season"""
            # Clear previous chart
            for widget in chart_frame.winfo_children():
                widget.destroy()
            
            # Filter games by season
            if selected_season == "Alle":
                filtered_games = games
                title_suffix = " (2022-2026)"
            else:
                year = int(selected_season)
                filtered_games = [g for g in games if g.get('season_year') == year]
                title_suffix = f" ({selected_season})"
            
            if not filtered_games:
                no_data_label = tk.Label(chart_frame, text=f"Keine Spiele für {selected_season} gefunden", 
                                        fg="gray", font=("Arial", 12))
                no_data_label.pack(expand=True)
                return
            
            # Group goals by month
            goals_by_month_year = defaultdict(lambda: {'goals': 0, 'games': 0})
            
            for game in filtered_games:
                date_str = game.get("date", "")
                if not date_str:
                    continue
                
                try:
                    # Parse date - handle different formats
                    if "T" in str(date_str):
                        dt = datetime.fromisoformat(str(date_str).replace("Z", "+00:00"))
                    else:
                        # Try parsing as simple date string
                        dt = datetime.strptime(str(date_str)[:10], "%Y-%m-%d")
                    
                    # Create month key (YYYY-MM)
                    month_key = dt.strftime("%Y-%m")
                    
                    # Calculate total goals
                    score_home = game.get("score_home") or game.get("homeResult") or game.get("homeFTResult") or game.get("home_ft_result") or 0
                    score_away = game.get("score_away") or game.get("awayResult") or game.get("awayFTResult") or game.get("away_ft_result") or 0
                    total_goals = int(score_home) + int(score_away)
                    
                    goals_by_month_year[month_key]['goals'] += total_goals
                    goals_by_month_year[month_key]['games'] += 1
                    
                except Exception as e:
                    print(f"[WARNING] Could not parse date {date_str}: {e}")
                    continue
            
            if not goals_by_month_year:
                no_data_label = tk.Label(chart_frame, text="Keine gültigen Datumsdaten gefunden", 
                                        fg="gray", font=("Arial", 12))
                no_data_label.pack(expand=True)
                return
            
            # Sort months chronologically
            sorted_months = sorted(goals_by_month_year.keys())
            month_labels = [datetime.strptime(m, "%Y-%m").strftime("%b %Y") for m in sorted_months]
            
            # Calculate average goals per month (this is what we show on left axis)
            avg_goals_per_month = [goals_by_month_year[m]['goals'] / goals_by_month_year[m]['games'] 
                                   if goals_by_month_year[m]['games'] > 0 else 0 
                                   for m in sorted_months]
            games_counts = [goals_by_month_year[m]['games'] for m in sorted_months]
            total_goals_per_month = [goals_by_month_year[m]['goals'] for m in sorted_months]
            
            # Create matplotlib figure with better size handling
            # Calculate figure width based on number of months (min 10, max 20)
            num_months = len(month_labels)
            fig_width = max(10, min(20, num_months * 0.8))
            fig = Figure(figsize=(fig_width, 7), dpi=100)
            ax = fig.add_subplot(111)
            
            # Create bar chart with average goals (left axis)
            bars = ax.bar(month_labels, avg_goals_per_month, color='#2E86AB', alpha=0.7, label='Ø Tore pro Spiel')
            
            # Add total goals line (right axis) - optional, can be removed if not needed
            ax2 = ax.twinx()
            ax2.plot(month_labels, total_goals_per_month, color='#FF6B35', marker='o', linewidth=2, markersize=6, 
                    linestyle='--', alpha=0.6, label='Gesamt Tore')
            
            # Set labels and title
            ax.set_xlabel('Monat', fontsize=12, fontweight='bold')
            ax.set_ylabel('Ø Tore pro Spiel', fontsize=12, fontweight='bold', color='#2E86AB')
            ax2.set_ylabel('Gesamt Tore', fontsize=12, fontweight='bold', color='#FF6B35')
            ax.set_title(f'Durchschnittliche Tore pro Monat - {league_name}{title_suffix}', 
                        fontsize=14, fontweight='bold', pad=20)
            
            # Rotate x-axis labels for better readability
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
            
            # Add grid
            ax.grid(True, alpha=0.3, axis='y')
            
            # Add value labels on bars (show average and game count)
            for i, (bar, avg, games_count) in enumerate(zip(bars, avg_goals_per_month, games_counts)):
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{avg:.2f}\n({games_count} Spiele)',
                       ha='center', va='bottom', fontsize=9)
            
            # Add legends
            ax.legend(loc='upper left')
            ax2.legend(loc='upper right')
            
            # Adjust layout
            fig.tight_layout()
            
            # Create canvas and add to frame
            canvas = FigureCanvasTkAgg(fig, chart_frame)
            canvas.draw()
            
            # Pack canvas first
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            
            # Add toolbar for zoom/pan functionality (prevents disappearing bars)
            try:
                from matplotlib.backends.backend_tkagg import NavigationToolbar2Tk
                toolbar = NavigationToolbar2Tk(canvas, chart_frame)
                toolbar.update()
                # Pack toolbar after canvas
                toolbar.pack(side=tk.BOTTOM, fill=tk.X)
            except Exception as e:
                print(f"[WARNING] Could not create toolbar: {e}")
            
            # Store canvas reference for updates
            parent._chart_canvas = canvas
            
            # Ensure canvas is properly displayed
            canvas.get_tk_widget().update_idletasks()
        
        # Initial chart
        update_chart("Alle")
        
        # Bind season change
        def on_season_change(event=None):
            selected = season_var.get()
            update_chart(selected)
        
        season_combo.bind("<<ComboboxSelected>>", on_season_change)
    
    def _create_goals_per_game_chart(self, parent, games, league_name, league_id, conn):
        """Create a chart showing goals per game distribution with season switcher"""
        if not HAS_MATPLOTLIB:
            no_matplotlib_label = tk.Label(parent, 
                                          text="Matplotlib nicht installiert.\nBitte installieren Sie es mit: pip install matplotlib",
                                          font=("Arial", 12), fg="red")
            no_matplotlib_label.pack(expand=True)
            return
        
        # Create control frame for season selection
        control_frame = tk.Frame(parent)
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(control_frame, text="Saison:", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=5)
        
        season_var = tk.StringVar(value="Alle")
        season_options = ["Alle"] + list(self.years_to_show)
        season_combo = ttk.Combobox(control_frame, textvariable=season_var, values=season_options, 
                                   state="readonly", width=10)
        season_combo.pack(side=tk.LEFT, padx=5)
        
        # Chart frame
        chart_frame = tk.Frame(parent)
        chart_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        def update_chart(selected_season="Alle"):
            """Update chart based on selected season"""
            # Clear previous chart
            for widget in chart_frame.winfo_children():
                widget.destroy()
            
            # Filter games by season
            if selected_season == "Alle":
                filtered_games = games
                title_suffix = " (2022-2026)"
            else:
                year = int(selected_season)
                filtered_games = [g for g in games if g.get('season_year') == year]
                title_suffix = f" ({selected_season})"
            
            if not filtered_games:
                no_data_label = tk.Label(chart_frame, text=f"Keine Spiele für {selected_season} gefunden", 
                                        fg="gray", font=("Arial", 12))
                no_data_label.pack(expand=True)
                return
            
            # Extract goals per game
            goals_per_game = []
            for game in filtered_games:
                score_home = game.get("score_home") or game.get("homeResult") or game.get("homeFTResult") or game.get("home_ft_result") or 0
                score_away = game.get("score_away") or game.get("awayResult") or game.get("awayFTResult") or game.get("away_ft_result") or 0
                total_goals = int(score_home) + int(score_away)
                goals_per_game.append(total_goals)
            
            if not goals_per_game:
                no_data_label = tk.Label(chart_frame, text="Keine gültigen Tordaten gefunden", 
                                        fg="gray", font=("Arial", 12))
                no_data_label.pack(expand=True)
                return
            
            # Create matplotlib figure
            fig = Figure(figsize=(12, 6), dpi=100)
            ax = fig.add_subplot(111)
            
            # Create histogram
            max_goals = max(goals_per_game) if goals_per_game else 10
            n, bins, patches = ax.hist(goals_per_game, bins=range(0, max_goals + 2), 
                                      edgecolor='black', alpha=0.7, color='#2E86AB')
            
            # Color bars based on goals (similar to table coloring)
            for i, patch in enumerate(patches):
                if i > 4.5:
                    patch.set_facecolor('#90EE90')  # Green - 5+ Goals
                elif i == 4:
                    patch.set_facecolor('#FFFF99')  # Yellow - 4 Goals
                elif i == 3:
                    patch.set_facecolor('#FFA500')  # Orange - 3 Goals
                else:
                    patch.set_facecolor('#FFB6C1')  # Light red - 0, 1, 2 Goals
            
            # Calculate statistics
            total_games = len(goals_per_game)
            avg_goals = sum(goals_per_game) / total_games if total_games > 0 else 0
            max_goals_val = max(goals_per_game) if goals_per_game else 0
            min_goals_val = min(goals_per_game) if goals_per_game else 0
            
            # Count games by goal ranges
            over_25 = sum(1 for g in goals_per_game if g > 2.5)
            over_35 = sum(1 for g in goals_per_game if g > 3.5)
            over_45 = sum(1 for g in goals_per_game if g > 4.5)
            
            # Set labels and title
            ax.set_xlabel('Anzahl Tore pro Spiel', fontsize=12, fontweight='bold')
            ax.set_ylabel('Anzahl Spiele', fontsize=12, fontweight='bold')
            ax.set_title(f'Verteilung der Tore pro Spiel - {league_name}{title_suffix}', 
                        fontsize=14, fontweight='bold', pad=20)
            
            # Add grid
            ax.grid(True, alpha=0.3, axis='y')
            
            # Add value labels on bars
            for i, (count, patch) in enumerate(zip(n, patches)):
                if count > 0:
                    height = patch.get_height()
                    ax.text(patch.get_x() + patch.get_width()/2., height,
                           f'{int(count)}',
                           ha='center', va='bottom', fontsize=9, fontweight='bold')
            
            # Add statistics text box
            stats_text = f"""Statistiken:
Gesamt Spiele: {total_games}
Ø Tore pro Spiel: {avg_goals:.2f}
Min Tore: {min_goals_val}
Max Tore: {max_goals_val}
Over 2.5: {over_25} ({over_25/total_games*100:.1f}%)
Over 3.5: {over_35} ({over_35/total_games*100:.1f}%)
Over 4.5: {over_45} ({over_45/total_games*100:.1f}%)"""
            
            ax.text(0.98, 0.98, stats_text, transform=ax.transAxes,
                   fontsize=10, verticalalignment='top', horizontalalignment='right',
                   bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
            
            # Adjust layout
            fig.tight_layout()
            
            # Create canvas and add to frame
            canvas = FigureCanvasTkAgg(fig, chart_frame)
            canvas.draw()
            
            # Pack canvas first
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            
            # Add toolbar for zoom/pan functionality (prevents disappearing bars)
            try:
                from matplotlib.backends.backend_tkagg import NavigationToolbar2Tk
                toolbar = NavigationToolbar2Tk(canvas, chart_frame)
                toolbar.update()
                # Pack toolbar after canvas
                toolbar.pack(side=tk.BOTTOM, fill=tk.X)
            except Exception as e:
                print(f"[WARNING] Could not create toolbar: {e}")
            
            # Store canvas reference for updates
            parent._chart_canvas = canvas
            
            # Ensure canvas is properly displayed
            canvas.get_tk_widget().update_idletasks()
        
        # Initial chart
        update_chart("Alle")
        
        # Bind season change
        def on_season_change(event=None):
            selected = season_var.get()
            update_chart(selected)
        
        season_combo.bind("<<ComboboxSelected>>", on_season_change)