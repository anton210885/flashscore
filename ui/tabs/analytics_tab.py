import tkinter as tk
from tkinter import ttk, messagebox, Toplevel, scrolledtext
import threading
import http.client
import json
from datetime import datetime
import queue

class APILoaderThread(threading.Thread):
    """Thread for loading API data in background"""
    def __init__(self, match_id, api_base="api.sstats.net", callback=None):
        super().__init__()
        self.match_id = match_id
        self.api_base = api_base
        self.callback = callback
        self.result = None
        self.error = None
    
    def run(self):
        try:
            print(f"[DEBUG] Loading match: {self.match_id}")
            
            # 1. Load fixture data
            fixture_data = self.load_fixture_data()
            print(f"[DEBUG] Fixture status: {fixture_data.get('status') if fixture_data else 'None'}")
            
            # 2. Load Glicko data
            glicko_data = self.load_glicko_data()
            print(f"[DEBUG] Glicko status: {glicko_data.get('status') if glicko_data else 'None'}")
            
            # 3. Set result
            self.result = (fixture_data, glicko_data)
            
        except Exception as e:
            print(f"[ERROR] Thread error: {str(e)}")
            self.error = str(e)
        
        if self.callback:
            self.callback(self.result, self.error)
    
    def load_fixture_data(self):
        """Load fixture data from API"""
        try:
            conn = http.client.HTTPSConnection(self.api_base)
            conn.request("GET", f"/Games/{self.match_id}")
            res = conn.getresponse()
            
            print(f"[DEBUG] Fixture HTTP status: {res.status}")
            data = res.read()
            json_data = json.loads(data.decode("utf-8"))
            
            # Debug: Show what we received
            print(f"[DEBUG] Fixture keys: {list(json_data.keys())}")
            if 'data' in json_data:
                print(f"[DEBUG] Data has 'game': {'game' in json_data['data']}")
            
            return json_data
            
        except Exception as e:
            print(f"[ERROR] Error loading fixture: {e}")
            return {"status": "error", "data": {}}
    
    def load_glicko_data(self):
        """Load Glicko data from API"""
        try:
            conn = http.client.HTTPSConnection(self.api_base)
            conn.request("GET", f"/Games/glicko/{self.match_id}")
            res = conn.getresponse()
            
            print(f"[DEBUG] Glicko HTTP status: {res.status}")
            data = res.read()
            json_data = json.loads(data.decode("utf-8"))
            
            # Debug: Show what we received
            print(f"[DEBUG] Glicko keys: {list(json_data.keys())}")
            if 'data' in json_data:
                print(f"[DEBUG] Data has 'glicko': {'glicko' in json_data['data']}")
                if 'glicko' in json_data['data']:
                    glicko = json_data['data']['glicko']
                    print(f"[DEBUG] Glicko data sample: homeRating={glicko.get('homeRating')}, awayRating={glicko.get('awayRating')}")
            
            return json_data
            
        except Exception as e:
            print(f"[ERROR] Error loading Glicko: {e}")
            return {"status": "error", "data": {}}


class AnalyticsTab(tk.Frame):
    def __init__(self, parent, services):
        super().__init__(parent)
        self.services = services
        self.api_base = "api.sstats.net"
        self.current_match_id = None
        self.fixture_data = None
        self.glicko_data = None
        self.loader_thread = None
        
        self.setup_ui()
        self.load_sample_matches()
        
    def setup_ui(self):
        # Main layout
        main_layout = tk.Frame(self)
        main_layout.pack(fill=tk.BOTH, expand=True)
        
        # Top controls
        controls_frame = tk.Frame(main_layout)
        controls_frame.pack(fill=tk.X, padx=5, pady=5)
        
        tk.Label(controls_frame, text="Match ID:").pack(side=tk.LEFT)
        self.match_id_input = tk.Entry(controls_frame, width=20)
        self.match_id_input.pack(side=tk.LEFT, padx=5)
        
        self.load_button = ttk.Button(controls_frame, text="Load Match", command=self.load_match_data)
        self.load_button.pack(side=tk.LEFT, padx=5)
        
        self.status_label = tk.Label(controls_frame, text="Ready")
        self.status_label.pack(side=tk.LEFT, padx=10)
        
        self.last_update_label = tk.Label(controls_frame, text="Last update: Never")
        self.last_update_label.pack(side=tk.RIGHT)
        
        # Progress bar
        self.progress_bar = ttk.Progressbar(main_layout, mode='indeterminate')
        self.progress_bar.pack(fill=tk.X, padx=5, pady=2)
        
        # Main content with splitter
        self.paned = tk.PanedWindow(main_layout, orient=tk.HORIZONTAL)
        self.paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Left panel - Match info
        left_frame = tk.Frame(self.paned)
        self.paned.add(left_frame, minsize=400)
        
        # Match header
        self.match_header = tk.Label(left_frame, text="Select a match", font=("Arial", 16, "bold"))
        self.match_header.pack(pady=10)
        
        # Score display
        score_frame = tk.Frame(left_frame)
        score_frame.pack(pady=5)
        self.score_display = tk.Label(score_frame, text="- : -", font=("Arial", 24, "bold"))
        self.score_display.pack()
        
        # Match details
        details_frame = tk.Frame(left_frame)
        details_frame.pack(fill=tk.X, pady=5)
        
        # League and round
        self.match_league_label = tk.Label(details_frame, text="League: Unknown")
        self.match_league_label.pack(anchor=tk.W)
        self.match_round_label = tk.Label(details_frame, text="Round: Unknown")
        self.match_round_label.pack(anchor=tk.W)
        
        # Date and status
        self.match_date_label = tk.Label(details_frame, text="Date: Unknown")
        self.match_date_label.pack(anchor=tk.W)
        self.match_status_label = tk.Label(details_frame, text="Status: Unknown")
        self.match_status_label.pack(anchor=tk.W)
        self.match_type_label = tk.Label(details_frame, text="Type: Unknown")
        self.match_type_label.pack(anchor=tk.W)
        
        # Half time and full time scores
        scores_frame = tk.Frame(details_frame)
        scores_frame.pack(fill=tk.X, pady=5)
        self.ht_score_label = tk.Label(scores_frame, text="HT: -")
        self.ht_score_label.pack(side=tk.LEFT, padx=10)
        self.ft_score_label = tk.Label(scores_frame, text="FT: -")
        self.ft_score_label.pack(side=tk.LEFT, padx=10)
        
        # Teams info
        teams_frame = tk.Frame(left_frame)
        teams_frame.pack(fill=tk.X, pady=10)
        
        # Home team
        home_frame = tk.LabelFrame(teams_frame, text="Home Team")
        home_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.home_name_label = tk.Label(home_frame, text="Team Name")
        self.home_name_label.pack(anchor=tk.W)
        self.home_country_label = tk.Label(home_frame, text="Country: Unknown")
        self.home_country_label.pack(anchor=tk.W)
        self.home_id_label = tk.Label(home_frame, text="ID: Unknown")
        self.home_id_label.pack(anchor=tk.W)
        
        # Away team
        away_frame = tk.LabelFrame(teams_frame, text="Away Team")
        away_frame.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=5)
        self.away_name_label = tk.Label(away_frame, text="Team Name")
        self.away_name_label.pack(anchor=tk.W)
        self.away_country_label = tk.Label(away_frame, text="Country: Unknown")
        self.away_country_label.pack(anchor=tk.W)
        self.away_id_label = tk.Label(away_frame, text="ID: Unknown")
        self.away_id_label.pack(anchor=tk.W)
        
        # Right panel - Tabs
        right_frame = tk.Frame(self.paned)
        self.paned.add(right_frame, minsize=500)
        
        self.notebook = ttk.Notebook(right_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Glicko tab
        self.glicko_tab = tk.Frame(self.notebook)
        self.notebook.add(self.glicko_tab, text="Glicko")
        self.setup_glicko_tab()
        
        # Odds tab
        self.odds_tab = tk.Frame(self.notebook)
        self.notebook.add(self.odds_tab, text="Odds")
        self.setup_odds_tab()
        
        # Periods tab
        self.periods_tab = tk.Frame(self.notebook)
        self.notebook.add(self.periods_tab, text="Periods")
        self.setup_periods_tab()
        
    def setup_glicko_tab(self):
        # Ratings
        ratings_frame = tk.LabelFrame(self.glicko_tab, text="Ratings")
        ratings_frame.pack(fill=tk.X, pady=5)
        
        # Home rating
        home_rating_frame = tk.Frame(ratings_frame)
        home_rating_frame.pack(fill=tk.X, pady=2)
        tk.Label(home_rating_frame, text="Home:").pack(side=tk.LEFT)
        self.home_rating_value = tk.Label(home_rating_frame, text="1500")
        self.home_rating_value.pack(side=tk.LEFT, padx=5)
        self.home_rating_bar = ttk.Progressbar(home_rating_frame, maximum=2000, value=1500)
        self.home_rating_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Away rating
        away_rating_frame = tk.Frame(ratings_frame)
        away_rating_frame.pack(fill=tk.X, pady=2)
        tk.Label(away_rating_frame, text="Away:").pack(side=tk.LEFT)
        self.away_rating_value = tk.Label(away_rating_frame, text="1500")
        self.away_rating_value.pack(side=tk.LEFT, padx=5)
        self.away_rating_bar = ttk.Progressbar(away_rating_frame, maximum=2000, value=1500)
        self.away_rating_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Win probabilities
        prob_frame = tk.LabelFrame(self.glicko_tab, text="Win Probabilities")
        prob_frame.pack(fill=tk.X, pady=5)
        
        self.home_win_prob = ttk.Progressbar(prob_frame, maximum=100, value=33)
        self.home_win_prob.pack(fill=tk.X, pady=2)
        self.home_win_prob_label = tk.Label(prob_frame, text="33.3%")
        self.home_win_prob_label.pack()
        tk.Label(prob_frame, text="Home Win").pack()
        
        self.draw_prob = ttk.Progressbar(prob_frame, maximum=100, value=34)
        self.draw_prob.pack(fill=tk.X, pady=2)
        self.draw_prob_label = tk.Label(prob_frame, text="33.3%")
        self.draw_prob_label.pack()
        tk.Label(prob_frame, text="Draw").pack()
        
        self.away_win_prob = ttk.Progressbar(prob_frame, maximum=100, value=33)
        self.away_win_prob.pack(fill=tk.X, pady=2)
        self.away_win_prob_label = tk.Label(prob_frame, text="33.3%")
        self.away_win_prob_label.pack()
        tk.Label(prob_frame, text="Away Win").pack()
        
        # xG
        xg_frame = tk.LabelFrame(self.glicko_tab, text="Expected Goals (xG)")
        xg_frame.pack(fill=tk.X, pady=5)
        
        self.home_xg_bar = ttk.Progressbar(xg_frame, maximum=50, value=0)
        self.home_xg_bar.pack(fill=tk.X, pady=2)
        self.home_xg_label = tk.Label(xg_frame, text="0.00")
        self.home_xg_label.pack()
        tk.Label(xg_frame, text="Home xG").pack()
        
        self.away_xg_bar = ttk.Progressbar(xg_frame, maximum=50, value=0)
        self.away_xg_bar.pack(fill=tk.X, pady=2)
        self.away_xg_label = tk.Label(xg_frame, text="0.00")
        self.away_xg_label.pack()
        tk.Label(xg_frame, text="Away xG").pack()
        
        # Glicko table
        table_frame = tk.LabelFrame(self.glicko_tab, text="Glicko Details")
        table_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.glicko_table = ttk.Treeview(table_frame, columns=("Team", "Rating", "RD", "Volatility"), show="headings", height=2)
        self.glicko_table.heading("Team", text="Team")
        self.glicko_table.heading("Rating", text="Rating")
        self.glicko_table.heading("RD", text="RD")
        self.glicko_table.heading("Volatility", text="Volatility")
        self.glicko_table.pack(fill=tk.BOTH, expand=True)
        
        self.glicko_updated_label = tk.Label(table_frame, text="Updated: Not available")
        self.glicko_updated_label.pack(anchor=tk.W)
        
    def setup_odds_tab(self):
        self.odds_table = ttk.Treeview(self.odds_tab, columns=("Market", "ID", "Current", "Opening"), show="headings")
        self.odds_table.heading("Market", text="Market")
        self.odds_table.heading("ID", text="ID")
        self.odds_table.heading("Current", text="Current")
        self.odds_table.heading("Opening", text="Opening")
        self.odds_table.pack(fill=tk.BOTH, expand=True)
        
    def setup_periods_tab(self):
        self.periods_table = ttk.Treeview(self.periods_tab, columns=("Type", "Time", "Details"), show="headings")
        self.periods_table.heading("Type", text="Type")
        self.periods_table.heading("Time", text="Time")
        self.periods_table.heading("Details", text="Details")
        self.periods_table.pack(fill=tk.BOTH, expand=True)
        
    def load_sample_matches(self):
        # Could load some sample match IDs
        pass
        
    def set_loading_state(self, loading):
        if loading:
            self.progress_bar.start()
            self.load_button.config(state=tk.DISABLED)
            self.status_label.config(text="Loading...")
        else:
            self.progress_bar.stop()
            self.load_button.config(state=tk.NORMAL)
            
    def load_match_data(self, use_database=True):
        match_id = self.match_id_input.get().strip()
        if not match_id:
            messagebox.showwarning("Warning", "Please enter a Match ID")
            return
        
        print(f"\n{'='*60}")
        print(f"Loading match data: {match_id}")
        print(f"{'='*60}")
        
        self.set_loading_state(True)
        self.current_match_id = match_id
        
        # Try to load from database first if use_database is True
        if use_database:
            try:
                from database import DatabaseManager
                db_manager = DatabaseManager("data/flashscore.db")
                game = db_manager.get_game(int(match_id))
                
                if game:
                    print(f"[INFO] Found game {match_id} in database, using database data")
                    # Convert database game to API format
                    fixture_data = self._convert_db_game_to_api_format(game, db_manager)
                    glicko_data = self._get_glicko_from_db(db_manager, int(match_id))
                    
                    self.after(0, lambda: self.on_data_loaded((fixture_data, glicko_data), None))
                    return
                else:
                    print(f"[INFO] Game {match_id} not found in database, loading from API")
            except Exception as e:
                print(f"[WARNING] Error loading from database: {e}, falling back to API")
        
        # Load from API if not in database or use_database is False
        def callback(result, error):
            self.after(0, lambda: self.on_data_loaded(result, error))
        
        self.loader_thread = APILoaderThread(match_id, self.api_base, callback)
        self.loader_thread.start()
    
    def _convert_db_game_to_api_format(self, game, db_manager):
        """Convert database game format to API response format"""
        if game is not None and not isinstance(game, dict):
            try:
                game = dict(game)
            except Exception:
                game = {k: game[k] for k in game.keys()}

        # Get statistics
        stats = db_manager.get_connection().execute(
            "SELECT * FROM game_statistics WHERE game_id = ?", (game["id"],)
        ).fetchone()
        
        # Get odds
        odds = db_manager.get_connection().execute(
            "SELECT * FROM game_odds WHERE game_id = ?", (game["id"],)
        ).fetchall()
        
        # Convert to API format
        fixture = {
            "id": game["id"],
            "flashId": game.get("flash_id"),
            "date": game.get("date"),
            "dateUtc": game.get("date_utc"),
            "status": game.get("status"),
            "statusName": game.get("status_name"),
            "elapsed": game.get("elapsed"),
            "extraMinutes": game.get("extra_minutes"),
            "homeResult": game.get("home_result"),
            "awayResult": game.get("away_result"),
            "homeHTResult": game.get("home_ht_result"),
            "awayHTResult": game.get("away_ht_result"),
            "homeFTResult": game.get("home_ft_result"),
            "awayFTResult": game.get("away_ft_result"),
            "homeTeam": {
                "id": game.get("home_team_id"),
                "name": game.get("home_team_name")
            },
            "awayTeam": {
                "id": game.get("away_team_id"),
                "name": game.get("away_team_name")
            },
            "season": {
                "year": game.get("season_year"),
                "league": {
                    "id": game.get("league_id"),
                    "name": game.get("league_name"),
                    "country": {
                        "code": game.get("country_code"),
                        "name": game.get("country_name")
                    }
                }
            }
        }
        
        # Add statistics if available
        statistics = None
        if stats:
            statistics = {
                "calculatedXgHome": game.get("calculated_xg_home"),
                "calculatedXgAway": game.get("calculated_xg_away"),
                "expectedGoalsHome": game.get("calculated_xg_home"),
                "expectedGoalsAway": game.get("calculated_xg_away"),
                # Add other statistics fields as needed
            }
        
        # Add odds if available
        odds_list = []
        if odds:
            for odd in odds:
                odds_list.append({
                    "marketId": odd[2],  # market_id
                    "marketName": odd[3],  # market_name
                    "odds": [{
                        "name": odd[4],  # name
                        "value": odd[5],  # value
                        "openingValue": odd[6]  # opening_value
                    }]
                })
        
        if odds_list:
            fixture["odds"] = odds_list
        
        return {
            "status": "OK",
            "data": {
                "game": fixture,
                "statistics": statistics
            }
        }
    
    def _get_glicko_from_db(self, db_manager, game_id):
        """Get Glicko data from database"""
        try:
            glicko = db_manager.get_connection().execute(
                "SELECT * FROM game_glicko WHERE game_id = ?", (game_id,)
            ).fetchone()
            
            if glicko:
                return {
                    "status": "OK",
                    "data": {
                        "glicko": {
                            "homeRating": glicko[1],  # home_rating
                            "homeRd": glicko[2],  # home_rd
                            "homeVolatility": glicko[3],  # home_volatility
                            "awayRating": glicko[4],  # away_rating
                            "awayRd": glicko[5],  # away_rd
                            "awayVolatility": glicko[6],  # away_volatility
                            "homeXg": glicko[7],  # home_xg
                            "awayXg": glicko[8],  # away_xg
                            "homeWinProbability": glicko[9],  # home_win_probability
                            "awayWinProbability": glicko[10],  # away_win_probability
                            "updated": glicko[12]  # updated
                        }
                    }
                }
        except Exception as e:
            print(f"[WARNING] Error loading Glicko from database: {e}")
        
        return {"status": "OK", "data": {}}
    
    def load_match_by_id(self, match_id, use_database=True):
        """Load match data by directly setting the ID"""
        self.match_id_input.delete(0, tk.END)
        self.match_id_input.insert(0, str(match_id))
        self.load_match_data(use_database=use_database)
        
    def on_data_loaded(self, result, error):
        if error:
            messagebox.showerror("Error", f"Failed to load data: {error}")
            self.set_loading_state(False)
            return
        
        fixture_data, glicko_data = result
        print("\n[INFO] Data received, updating UI")
        
        self.fixture_data = fixture_data
        self.glicko_data = glicko_data
        
        self.update_match_info()
        self.update_glicko_predictions()
        self.update_odds_table()
        self.update_periods_table()
        
        now = datetime.now().strftime("%H:%M:%S")
        self.last_update_label.config(text=f"Last update: {now}")
        
        self.set_loading_state(False)
        self.status_label.config(text=f" Match {self.current_match_id} loaded")
        
    def update_match_info(self):
        if not self.fixture_data:
            print("[ERROR] No fixture data available")
            return
        
        try:
            status = self.fixture_data.get("status", "").upper()
            if status not in ["SUCCESS", "OK"]:
                print(f"[WARN] Fixture status is not OK: {status}")
                return
            
            data = self.fixture_data.get("data", {})
            
            if "game" in data:
                fixture = data.get("game", {})
                print("[INFO] Using 'game' data from API")
            elif "fixture" in data:
                fixture = data.get("fixture", {})
                print("[INFO] Using 'fixture' data from API")
            else:
                print("[ERROR] No game/fixture data found in response")
                return
            
            print(f"[DEBUG] Fixture keys: {list(fixture.keys())}")
            
            home_team = fixture.get("homeTeam", {}).get("name", "Home Team")
            away_team = fixture.get("awayTeam", {}).get("name", "Away Team")
            
            print(f"[DEBUG] Teams: {home_team} vs {away_team}")
            self.match_header.config(text=f"{home_team}  {away_team}")
            
            home_result = fixture.get("homeResult")
            away_result = fixture.get("awayResult")
            
            print(f"[DEBUG] Scores: {home_result} - {away_result}")
            
            if home_result is not None and away_result is not None:
                self.score_display.config(text=f"{home_result} : {away_result}")
            else:
                self.score_display.config(text="- : -")
            
            home_ht = fixture.get("homeHTResult")
            away_ht = fixture.get("awayHTResult")
            if home_ht is not None and away_ht is not None:
                self.ht_score_label.config(text=f"HT: {home_ht} - {away_ht}")
            else:
                self.ht_score_label.config(text="HT: -")
            
            home_ft = fixture.get("homeFTResult")
            away_ft = fixture.get("awayFTResult")
            if home_ft is not None and away_ft is not None:
                self.ft_score_label.config(text=f"FT: {home_ft} - {away_ft}")
            else:
                self.ft_score_label.config(text="FT: -")
            
            date_str = fixture.get("date") or fixture.get("dateUtc") or "Unknown"
            if date_str and date_str != "Unknown":
                try:
                    if isinstance(date_str, int):
                        dt = datetime.fromtimestamp(date_str)
                    else:
                        date_str = date_str.replace('Z', '+00:00')
                        dt = datetime.fromisoformat(date_str)
                    date_str = dt.strftime("%Y-%m-%d %H:%M")
                except Exception as e:
                    print(f"[WARN] Date parsing error: {e}")
            self.match_date_label.config(text=f"Date: {date_str}")
            
            status_name = fixture.get("statusName") or str(fixture.get("status", "Unknown"))
            elapsed = fixture.get("elapsed")
            extra = fixture.get("extraMinutes")
            
            status_text = str(status_name)
            if elapsed is not None:
                status_text = f"{status_name} ({elapsed}'"
                if extra is not None:
                    status_text += f"+{extra}"
                status_text += ")"
            self.match_status_label.config(text=f"Status: {status_text}")
            
            season = fixture.get("season", {})
            league = season.get("league", {})
            league_name = league.get("name", "Unknown League")
            country = league.get("country", {})
            country_name = country.get("name", "")
            
            if country_name:
                league_display = f"{league_name} ({country_name})"
            else:
                league_display = league_name
            self.match_league_label.config(text=f"League: {league_display}")
            
            round_name = fixture.get("roundName") or "Unknown Round"
            self.match_round_label.config(text=f"Round: {round_name}")
            
            status_lower = str(status_name).lower()
            if "live" in status_lower:
                match_type = "Live Match"
            elif "finished" in status_lower:
                match_type = "Finished"
            elif "postponed" in status_lower:
                match_type = "Postponed"
            elif "cancel" in status_lower:
                match_type = "Cancelled"
            else:
                match_type = "Scheduled"
            self.match_type_label.config(text=f"Type: {match_type}")
            
            home_team_data = fixture.get("homeTeam", {})
            away_team_data = fixture.get("awayTeam", {})
            
            self.home_name_label.config(text=home_team_data.get("name", "Home Team"))
            home_country = home_team_data.get("country", {})
            self.home_country_label.config(text=f"Country: {home_country.get('name', 'Unknown')}")
            self.home_id_label.config(text=f"ID: {home_team_data.get('id', 'Unknown')}")
            
            self.away_name_label.config(text=away_team_data.get("name", "Away Team"))
            away_country = away_team_data.get("country", {})
            self.away_country_label.config(text=f"Country: {away_country.get('name', 'Unknown')}")
            self.away_id_label.config(text=f"ID: {away_team_data.get('id', 'Unknown')}")
            
            print("[SUCCESS] Match info updated successfully!")
            
        except Exception as e:
            print(f"[ERROR] Error updating match info: {e}")
            import traceback
            traceback.print_exc()
            
    def update_glicko_predictions(self):
        if not self.glicko_data:
            print("[ERROR] No Glicko data available")
            self.clear_glicko_data()
            return
        
        try:
            status = self.glicko_data.get("status", "").upper()
            if status not in ["SUCCESS", "OK"]:
                print(f"[WARN] Glicko status is not OK: {status}")
                self.clear_glicko_data()
                return
            
            data = self.glicko_data.get("data", {})
            glicko = data.get("glicko", {})
            
            if not glicko:
                print("[ERROR] No Glicko data found")
                self.clear_glicko_data()
                return
            
            print(f"[DEBUG] Glicko data keys: {list(glicko.keys())}")
            
            home_rating = glicko.get("homeRating", 1500)
            away_rating = glicko.get("awayRating", 1500)
            
            print(f"[DEBUG] Ratings: Home={home_rating}, Away={away_rating}")
            
            max_rating = max(home_rating, away_rating, 2000)
            min_rating = min(home_rating, away_rating, 1000)
            
            self.home_rating_bar.config(maximum=max_rating, value=int(home_rating))
            self.away_rating_bar.config(maximum=max_rating, value=int(away_rating))
            
            self.home_rating_value.config(text=f"{home_rating:.0f}")
            self.away_rating_value.config(text=f"{away_rating:.0f}")
            
            home_win_prob = glicko.get("homeWinProbability", 0.33)
            away_win_prob = glicko.get("awayWinProbability", 0.33)
            draw_prob = 1.0 - home_win_prob - away_win_prob
            
            draw_prob = max(0, draw_prob)
            total = home_win_prob + away_win_prob + draw_prob
            
            if total > 0:
                home_win_percent = (home_win_prob / total) * 100
                away_win_percent = (away_win_prob / total) * 100
                draw_percent = (draw_prob / total) * 100
            else:
                home_win_percent = 33.33
                away_win_percent = 33.33
                draw_percent = 33.34
            
            print(f"[DEBUG] Win probabilities: Home={home_win_percent:.1f}%, Draw={draw_percent:.1f}%, Away={away_win_percent:.1f}%")
            
            self.home_win_prob.config(value=int(home_win_percent))
            self.home_win_prob_label.config(text=f"{home_win_percent:.1f}%")
            self.draw_prob.config(value=int(draw_percent))
            self.draw_prob_label.config(text=f"{draw_percent:.1f}%")
            self.away_win_prob.config(value=int(away_win_percent))
            self.away_win_prob_label.config(text=f"{away_win_percent:.1f}%")
            
            home_xg = glicko.get("homeXg", 0)
            away_xg = glicko.get("awayXg", 0)
            
            print(f"[DEBUG] xG: Home={home_xg:.2f}, Away={away_xg:.2f}")
            
            max_xg = max(home_xg, away_xg, 5.0)
            scale_factor = 10
            
            self.home_xg_bar.config(maximum=int(max_xg * scale_factor), value=int(home_xg * scale_factor))
            self.home_xg_label.config(text=f"{home_xg:.2f}")
            self.away_xg_bar.config(maximum=int(max_xg * scale_factor), value=int(away_xg * scale_factor))
            self.away_xg_label.config(text=f"{away_xg:.2f}")
            
            # Glicko table
            for item in self.glicko_table.get_children():
                self.glicko_table.delete(item)
            
            self.glicko_table.insert("", tk.END, values=("Home", f"{home_rating:.0f}", f"{glicko.get('homeRd', 0):.1f}", f"{glicko.get('homeVolatility', 0):.4f}"))
            self.glicko_table.insert("", tk.END, values=("Away", f"{away_rating:.0f}", f"{glicko.get('awayRd', 0):.1f}", f"{glicko.get('awayVolatility', 0):.4f}"))
            
            updated = glicko.get("updated")
            if updated and updated != "0001-01-01T00:00:00+00:00":
                try:
                    updated = updated.replace('Z', '+00:00')
                    dt = datetime.fromisoformat(updated)
                    updated_str = dt.strftime("%Y-%m-%d %H:%M")
                    self.glicko_updated_label.config(text=f"Updated: {updated_str}")
                except:
                    self.glicko_updated_label.config(text=f"Updated: {updated}")
            else:
                self.glicko_updated_label.config(text="Updated: Not available")
            
            print("[SUCCESS] Glicko predictions updated successfully!")
            
        except Exception as e:
            print(f"[ERROR] Error updating Glicko predictions: {e}")
            import traceback
            traceback.print_exc()
            self.clear_glicko_data()
            
    def clear_glicko_data(self):
        self.home_rating_value.config(text="1500")
        self.away_rating_value.config(text="1500")
        self.home_rating_bar.config(value=1500)
        self.away_rating_bar.config(value=1500)
        self.home_win_prob.config(value=33)
        self.home_win_prob_label.config(text="33.3%")
        self.draw_prob.config(value=34)
        self.draw_prob_label.config(text="33.3%")
        self.away_win_prob.config(value=33)
        self.away_win_prob_label.config(text="33.3%")
        self.home_xg_bar.config(value=0)
        self.home_xg_label.config(text="0.00")
        self.away_xg_bar.config(value=0)
        self.away_xg_label.config(text="0.00")
        for item in self.glicko_table.get_children():
            self.glicko_table.delete(item)
        self.glicko_updated_label.config(text="Updated: Not available")
        
    def update_odds_table(self):
        if not self.fixture_data:
            return
        
        try:
            status = self.fixture_data.get("status", "").upper()
            if status not in ["SUCCESS", "OK"]:
                return
            
            data = self.fixture_data.get("data", {})
            if "game" in data:
                fixture = data.get("game", {})
            elif "fixture" in data:
                fixture = data.get("fixture", {})
            else:
                return
            
            odds_list = fixture.get("odds", [])
            
            print(f"[DEBUG] Found {len(odds_list)} odds markets")
            
            for item in self.odds_table.get_children():
                self.odds_table.delete(item)
            
            for market in odds_list:
                market_name = market.get("marketName", "Unknown Market")
                if not market_name:
                    market_name = f"Market {market.get('marketId', 'Unknown')}"
                
                market_id = str(market.get("marketId", ""))
                
                odds_items = market.get("odds", [])
                current_text = ""
                opening_text = ""
                
                for odd in odds_items:
                    name = odd.get("name", "")
                    value = odd.get("value")
                    opening = odd.get("openingValue")
                    
                    if value is not None:
                        current_text += f"{name}: {value:.2f}\n"
                    if opening is not None:
                        opening_text += f"{name}: {opening:.2f}\n"
                
                self.odds_table.insert("", tk.END, values=(market_name, market_id, current_text.strip() or "-", opening_text.strip() or "-"))
            
        except Exception as e:
            print(f"[ERROR] Error updating odds: {e}")
            for item in self.odds_table.get_children():
                self.odds_table.delete(item)
                
    def update_periods_table(self):
        if not self.fixture_data:
            return
        
        try:
            status = self.fixture_data.get("status", "").upper()
            if status not in ["SUCCESS", "OK"]:
                return
            
            data = self.fixture_data.get("data", {})
            
            if "game" in data:
                fixture = data.get("game", {})
                events_data = data
            elif "fixture" in data:
                fixture = data.get("fixture", {})
                events_data = data
            else:
                return
            
            periods = fixture.get("periods", [])
            events = events_data.get("events", [])
            
            all_items = []
            
            for i, period in enumerate(periods[:2]):
                try:
                    if isinstance(period, str):
                        dt = datetime.fromisoformat(period.replace('Z', '+00:00'))
                        time_str = dt.strftime("%H:%M")
                    else:
                        time_str = str(period)
                    
                    period_name = "1st Half" if i == 0 else "2nd Half"
                    all_items.append((period_name, time_str, ""))
                except:
                    all_items.append((f"Period {i + 1}", str(period), ""))
            
            for event in events[:15]:
                event_type = event.get("name", "Event")
                minute = event.get("elapsed", 0)
                player = event.get("player", {}).get("name", "")
                
                all_items.append((event_type, f"{minute}'", player))
            
            for item in self.periods_table.get_children():
                self.periods_table.delete(item)
            
            for item in all_items:
                self.periods_table.insert("", tk.END, values=item)
            
        except Exception as e:
            print(f"[ERROR] Error updating periods: {e}")
            for item in self.periods_table.get_children():
                self.periods_table.delete(item)
