"""Database management tab for loading games into database"""
import json
import os
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
from services.game_loader_service import GameLoaderService
from services.auto_loader_service import AutoLoaderService
from ui.league_import_dialog import open_league_import_dialog


class DatabaseTab(tk.Frame):
    """Tab for managing database and loading games"""
    
    def __init__(self, parent, services):
        super().__init__(parent)
        self.services = services
        self.db_manager = None
        self.loader_service = None
        self.auto_loader_service = None
        self._init_ui()
        self._init_database()
    
    def _init_database(self):
        """Initialize database manager"""
        try:
            from database import DatabaseManager
            self.db_manager = DatabaseManager("data/flashscore.db")
            self.loader_service = GameLoaderService(
                self.services["client"],
                self.db_manager,
                rate_limit_ms=1000  # Increased to 1 second to avoid rate limits
            )
            self.auto_loader_service = AutoLoaderService(
                self.services["client"],
                self.db_manager,
                rate_limit_ms=1000
            )
            # Set status callback for auto-loader
            self.auto_loader_service.set_status_callback(self._auto_loader_status)
        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to initialize database: {e}")
    
    def _init_ui(self):
        """Initialize UI components"""
        # Title
        title_label = tk.Label(self, text="Database Management", font=("Arial", 16, "bold"))
        title_label.pack(pady=10)
        
        # Database Info Frame
        info_frame = ttk.LabelFrame(self, text="Database Information", padding=10)
        info_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.info_text = tk.Text(info_frame, height=6, width=60)
        self.info_text.pack(fill=tk.X)
        self.info_text.insert("1.0", "Click 'Refresh Info' to see database statistics")
        self.info_text.config(state=tk.DISABLED)
        
        refresh_btn = tk.Button(info_frame, text="Refresh Info", command=self._refresh_info)
        refresh_btn.pack(pady=5)

        xl_frame = tk.Frame(info_frame)
        xl_frame.pack(fill=tk.X, pady=(8, 0))
        tk.Label(
            xl_frame,
            text="Ligen-Katalog Excel (data/league.xlsx oder Projekt/league.xlsx):",
            font=("Arial", 9),
            anchor="w",
        ).pack(anchor="w")
        xl_btn_row = tk.Frame(xl_frame)
        xl_btn_row.pack(fill=tk.X, pady=4)
        tk.Button(
            xl_btn_row,
            text="Ligen aus Excel importieren …",
            command=self._open_league_import,
            bg="#2196F3",
            fg="white",
            font=("Arial", 10, "bold"),
        ).pack(side=tk.LEFT)
        
        # Load Games Frame
        load_frame = ttk.LabelFrame(self, text="Load Finished Games", padding=10)
        load_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # League selection with dropdown
        selection_frame = tk.Frame(load_frame)
        selection_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(selection_frame, text="Select League:", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=5)
        
        # Get leagues from League Tab
        self.leagues_list = self._get_leagues_list()
        
        # League dropdown
        league_dropdown_frame = tk.Frame(selection_frame)
        league_dropdown_frame.pack(side=tk.LEFT, padx=5)
        
        self.selected_league_var = tk.StringVar()
        self.league_combo = ttk.Combobox(league_dropdown_frame, textvariable=self.selected_league_var, 
                                         width=40, state="readonly")
        self.league_combo['values'] = [f"{l['name']} ({l['country']}) - ID: {l['id']}" for l in self.leagues_list]
        if self.leagues_list:
            self.league_combo.current(0)  # Select first league
        self.league_combo.pack(side=tk.LEFT, padx=5)
        self.league_combo.bind("<<ComboboxSelected>>", self._on_league_selected)
        
        # Year selection
        year_frame = tk.Frame(selection_frame)
        year_frame.pack(side=tk.LEFT, padx=10)
        
        tk.Label(year_frame, text="Year:").pack(side=tk.LEFT, padx=2)
        self.year_var = tk.StringVar(value="2026")
        # Include current year and next year (some leagues start early)
        from datetime import datetime
        current_year = datetime.now().year
        year_values = [str(y) for y in range(2022, current_year + 3)]  # 2022 to current+2
        year_combo = ttk.Combobox(year_frame, textvariable=self.year_var, width=8, state="readonly")
        year_combo['values'] = year_values
        # Default: Saison 26/27 = API-Jahr 2026
        try:
            year_combo.current(year_values.index("2026"))
        except ValueError:
            try:
                year_combo.current(year_values.index(str(current_year)))
            except ValueError:
                year_combo.current(len(year_values) - 1)
        year_combo.pack(side=tk.LEFT, padx=2)
        
        # Selected league info
        self.league_info_label = tk.Label(selection_frame, text="", font=("Arial", 8), fg="gray")
        self.league_info_label.pack(side=tk.LEFT, padx=10)
        
        # Update info on selection
        self._on_league_selected()
        
        # Options
        options_frame = tk.Frame(load_frame)
        options_frame.pack(fill=tk.X, pady=5)
        
        self.load_details_var = tk.BooleanVar(value=True)
        details_check = tk.Checkbutton(options_frame, text="Load full game details (slower, more data)", 
                                      variable=self.load_details_var)
        details_check.pack(side=tk.LEFT, padx=5)
        
        # Load buttons frame
        buttons_frame = tk.Frame(load_frame)
        buttons_frame.pack(fill=tk.X, pady=10)
        
        # Load Games button
        self.load_btn = tk.Button(buttons_frame, text="Load Games (Selected Year)", command=self._load_games, 
                                  bg="#4CAF50", fg="white", font=("Arial", 10, "bold"))
        self.load_btn.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Load Latest Games button
        self.load_latest_btn = tk.Button(buttons_frame, text="🔄 Load Latest Games", command=self._load_latest_games, 
                                         bg="#FF9800", fg="white", font=("Arial", 10, "bold"))
        self.load_latest_btn.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Progress
        progress_frame = tk.Frame(load_frame)
        progress_frame.pack(fill=tk.X, pady=5)
        
        self.progress_label = tk.Label(progress_frame, text="", wraplength=500)
        self.progress_label.pack()
        
        self.progress_bar = ttk.Progressbar(progress_frame, mode='determinate')
        self.progress_bar.pack(fill=tk.X, pady=5)
        
        # Results
        results_frame = ttk.LabelFrame(load_frame, text="Results", padding=10)
        results_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.results_text = tk.Text(results_frame, height=10, width=60)
        self.results_text.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(results_frame, orient="vertical", command=self.results_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.results_text.config(yscrollcommand=scrollbar.set)
        
        # Load Multiple Leagues Button
        multi_frame = tk.Frame(load_frame)
        multi_frame.pack(fill=tk.X, pady=10)
        
        self.load_multi_btn = tk.Button(multi_frame, text="Load Multiple Leagues (2022-2026)", 
                                        command=self._load_multiple_leagues,
                                        bg="#2196F3", fg="white")
        self.load_multi_btn.pack()
        
        tk.Label(multi_frame, text="This will load all finished games for all leagues in League Tab", 
                font=("Arial", 8)).pack(pady=2)
        
        # Load Latest Games for All Existing Leagues Button
        all_leagues_frame = tk.Frame(load_frame)
        all_leagues_frame.pack(fill=tk.X, pady=10)
        
        self.load_all_latest_btn = tk.Button(all_leagues_frame, text="Load Latest Games for All Existing Leagues", 
                                             command=self._load_latest_for_all_leagues,
                                             bg="#9C27B0", fg="white", font=("Arial", 10, "bold"))
        self.load_all_latest_btn.pack()
        
        tk.Label(all_leagues_frame, text="This will load latest games for all leagues that already exist in database", 
                font=("Arial", 8)).pack(pady=2)
        
        # Auto-Loader Section
        auto_frame = ttk.LabelFrame(self, text="Automatic Game Loader", padding=10)
        auto_frame.pack(fill=tk.X, padx=10, pady=5)
        
        auto_info = tk.Label(auto_frame, 
                            text="Automatically loads new finished games every few minutes",
                            font=("Arial", 9))
        auto_info.pack(pady=5)
        
        auto_controls = tk.Frame(auto_frame)
        auto_controls.pack(fill=tk.X, pady=5)
        
        self.auto_loader_status_label = tk.Label(auto_controls, text="Status: Stopped", 
                                                 fg="gray", font=("Arial", 9))
        self.auto_loader_status_label.pack(side=tk.LEFT, padx=5)
        
        self.auto_loader_btn = tk.Button(auto_controls, text="Start Auto-Loader", 
                                         command=self._toggle_auto_loader,
                                         bg="#FF9800", fg="white")
        self.auto_loader_btn.pack(side=tk.LEFT, padx=5)
        
        # Auto-loader status text
        self.auto_status_text = tk.Text(auto_frame, height=4, width=60, font=("Arial", 8))
        self.auto_status_text.pack(fill=tk.X, pady=5)
        self.auto_status_text.insert("1.0", "Auto-loader is stopped. Click 'Start Auto-Loader' to begin monitoring.")
        self.auto_status_text.config(state=tk.DISABLED)
        
        # Configure monitored leagues
        config_frame = tk.Frame(auto_frame)
        config_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(config_frame, text="Monitored Leagues:", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=5)
        self.monitored_leagues_label = tk.Label(config_frame, text="None", font=("Arial", 9))
        self.monitored_leagues_label.pack(side=tk.LEFT, padx=5)
        
        config_btn = tk.Button(config_frame, text="Configure", command=self._configure_auto_loader)
        config_btn.pack(side=tk.LEFT, padx=5)
    
    def _refresh_info(self):
        """Refresh database information"""
        if not self.db_manager:
            messagebox.showerror("Error", "Database not initialized")
            return
        
        try:
            size_info = self.db_manager.get_database_size()
            info = f"""Database Size: {size_info['file_size_mb']} MB
Total Games: {size_info['games']}
Games with Statistics: {size_info['statistics']}
Total Events: {size_info['events']}
Average Size per Game: {size_info['avg_size_per_game_mb']} MB"""
            
            self.info_text.config(state=tk.NORMAL)
            self.info_text.delete("1.0", tk.END)
            self.info_text.insert("1.0", info)
            self.info_text.config(state=tk.DISABLED)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to get database info: {e}")

    def _after_league_import_refresh(self):
        lt = self.services.get("league_tab")
        l128 = self.services.get("league_128_tab")
        if lt and hasattr(lt, "reload_league_list_from_database"):
            lt.reload_league_list_from_database()
        if l128 and hasattr(l128, "reload_league_list_from_database"):
            l128.reload_league_list_from_database()
        self._refresh_league_combo()

    def _refresh_league_combo(self):
        self.leagues_list = self._get_leagues_list()
        labels = [f"{l['name']} ({l['country']}) - ID: {l['id']}" for l in self.leagues_list]
        self.league_combo["values"] = labels
        if not labels:
            return
        sel = self.selected_league_var.get()
        if sel in labels:
            self.league_combo.current(labels.index(sel))
        else:
            self.league_combo.current(0)
        self._on_league_selected()

    def _open_league_import(self):
        top = self.winfo_toplevel()
        open_league_import_dialog(
            top,
            db_path="data/flashscore.db",
            on_finished=self._after_league_import_refresh,
        )
    
    def _get_leagues_list(self):
        """Get list of leagues from League Tab"""
        # Use the leagues list from LeagueTab (static list)
        # This matches the leagues defined in league_tab.py
        # Serie A and Serie B (Italy) are included
        leagues = [
            {"id": 1, "name": "World Cup", "country": "World"},
            {"id": 2, "name": "UEFA Champions League", "country": "World"},
            {"id": 3, "name": "UEFA Europa League", "country": "World"},
            {"id": 848, "name": "UEFA Europa Conference League", "country": "World"},
            {"id": 128, "name": "Liga Profesional Argentina", "country": "Argentina"},
            {"id": 186, "name": "Ligue 1", "country": "Algeria"},
            {"id": 188, "name": "A-League", "country": "Australia"},
            {"id": 190, "name": "A-League Women", "country": "Australia"},
            {"id": 218, "name": "Bundesliga", "country": "Austria"},
            {"id": 219, "name": "2. Liga", "country": "Austria"},
            {"id": 144, "name": "Jupiler Pro League", "country": "Belgium"},
            {"id": 145, "name": "Challenger Pro League", "country": "Belgium"},
            {"id": 116, "name": "Premier League", "country": "Belarus"},
            {"id": 117, "name": "1. Division", "country": "Belarus"},
            {"id": 71, "name": "Serie A", "country": "Brazil"},
            {"id": 72, "name": "Serie B", "country": "Brazil"},
            {"id": 172, "name": "First League", "country": "Bulgaria"},
            {"id": 265, "name": "Primera División", "country": "Chile"},
            {"id": 169, "name": "Super League", "country": "China"},
            {"id": 239, "name": "Primera A", "country": "Colombia"},
            {"id": 345, "name": "Czech Liga", "country": "Czech-Republic"},
            {"id": 210, "name": "HNL", "country": "Croatia"},
            {"id": 119, "name": "Superliga", "country": "Denmark"},
            {"id": 233, "name": "Premier League", "country": "Egypt"},
            {"id": 39, "name": "Premier League", "country": "England"},
            {"id": 40, "name": "Championship", "country": "England"},
            {"id": 41, "name": "League One", "country": "Great Britain"},
            {"id": 42, "name": "League Two", "country": "Great Britain"},
            {"id": 244, "name": "Veikkausliiga", "country": "Finland"},
            {"id": 245, "name": "Ykkönen", "country": "Finland"},
            {"id": 366, "name": "1. Deild", "country": "Faroe-Islands"},
            {"id": 367, "name": "Meistaradeildin", "country": "Faroe-Islands"},
            {"id": 61, "name": "Ligue 1", "country": "France"},
            {"id": 62, "name": "Ligue 2", "country": "France"},
            {"id": 197, "name": "Super League 1", "country": "Greece"},
            {"id": 78, "name": "Bundesliga", "country": "Germany"},
            {"id": 79, "name": "2. Bundesliga", "country": "Germany"},
            {"id": 80, "name": "3. Liga", "country": "Germany"},
            {"id": 271, "name": "NB I", "country": "Hungary"},
            {"id": 274, "name": "Liga 1", "country": "Indonesia"},
            {"id": 275, "name": "Liga 2", "country": "Indonesia"},
            {"id": 383, "name": "Ligat Ha'al", "country": "Israel"},
            {"id": 135, "name": "Serie A", "country": "Italy"},
            {"id": 136, "name": "Serie B", "country": "Italy"},
            {"id": 98, "name": "J1 League", "country": "Japan"},
            {"id": 99, "name": "J2 League", "country": "Japan"},
            {"id": 262, "name": "Liga MX", "country": "Mexico"},
            {"id": 200, "name": "Botola Pro", "country": "Morocco"},
            {"id": 88, "name": "Eredivisie", "country": "Netherlands"},
            {"id": 89, "name": "Eerste Divisie", "country": "Netherlands"},
            {"id": 103, "name": "Eliteserien", "country": "Norway"},
            {"id": 104, "name": "1. Division", "country": "Norway"},
            {"id": 106, "name": "Ekstraklasa", "country": "Poland"},
            {"id": 94, "name": "Primeira Liga", "country": "Portugal"},
            {"id": 95, "name": "Segunda Liga", "country": "Portugal"},
            {"id": 305, "name": "Stars League", "country": "Qatar"},
            {"id": 283, "name": "Liga I", "country": "Romania"},
            {"id": 235, "name": "Premier League", "country": "Russia"},
            {"id": 236, "name": "First League", "country": "Russia"},
            {"id": 307, "name": "Pro League", "country": "Saudi Arabia"},
            {"id": 286, "name": "Super Liga", "country": "Serbia"},
            {"id": 287, "name": "Prva Liga", "country": "Serbia"},
            {"id": 179, "name": "Premiership", "country": "Scotland"},
            {"id": 180, "name": "Championship", "country": "Scotland"},
            {"id": 332, "name": "Super Liga", "country": "Slovakia"},
            {"id": 373, "name": "1. SNL", "country": "Slovenia"},
            {"id": 292, "name": "K League 1", "country": "South Korea"},
            {"id": 293, "name": "K League 2", "country": "South Korea"},
            {"id": 288, "name": "Premier Soccer League", "country": "South-Africa"},
            {"id": 140, "name": "La Liga", "country": "Spain"},
            {"id": 141, "name": "Segunda División", "country": "Spain"},
            {"id": 113, "name": "Allsvenskan", "country": "Sweden"},
            {"id": 114, "name": "Superettan", "country": "Sweden"},
            {"id": 207, "name": "Super League", "country": "Switzerland"},
            {"id": 208, "name": "Challenge League", "country": "Switzerland"},
            {"id": 203, "name": "Süper Lig", "country": "Turkey"},
            {"id": 204, "name": "1. Lig", "country": "Turkey"},
            {"id": 301, "name": "Pro League", "country": "UAE"},
            {"id": 303, "name": "Division 1", "country": "UAE"},
            {"id": 268, "name": "Primera División - Apertura", "country": "Uruguay"},
            {"id": 253, "name": "Major League Soccer", "country": "USA"},
            {"id": 110, "name": "Premier League", "country": "Wales"},
            {"id": 111, "name": "FAW Championship", "country": "Wales"},
        ]
        leagues = self._merge_liga128_ids_for_dropdown(leagues)
        leagues = self._merge_db_leagues_for_dropdown(leagues)
        # Sort by country name, then by league name for easier finding
        leagues.sort(key=lambda x: (x["country"], x["name"]))
        return leagues

    def _merge_db_leagues_for_dropdown(self, leagues):
        """Ergänze Dropdown um alle Ligen aus der DB (Tabelle leagues + games), die noch fehlen.

        So tauchen Ligen wie Morocco 200 automatisch im Auswahl-Dropdown auf,
        sobald sie in der Datenbank vorhanden sind (per Excel-Import oder geladene Spiele).
        """
        try:
            from database import DatabaseManager

            dm = DatabaseManager("data/flashscore.db")
            conn = dm.get_connection()
            have = {entry["id"] for entry in leagues}

            rows = conn.execute(
                """
                SELECT league_id,
                       COALESCE(league_name, 'Unknown League') AS league_name,
                       COALESCE(country_name, 'Unknown')       AS country_name
                FROM leagues
                WHERE league_id IS NOT NULL
                UNION
                SELECT DISTINCT league_id,
                       COALESCE(league_name, 'Unknown League') AS league_name,
                       COALESCE(country_name, 'Unknown')       AS country_name
                FROM games
                WHERE league_id IS NOT NULL
                """
            ).fetchall()

            seen_added = set()
            for row in rows:
                lid = row[0]
                if lid in have or lid in seen_added:
                    continue
                seen_added.add(lid)
                leagues.append(
                    {
                        "id": int(lid),
                        "name": row[1] or f"League {lid}",
                        "country": row[2] or "Unknown",
                    }
                )
        except Exception as e:
            print(f"[WARNING] _merge_db_leagues_for_dropdown: {e}")
        return leagues
    
    def _merge_liga128_ids_for_dropdown(self, leagues):
        """Ensure every ID in Liga-128-Konfiguration wählbar ist (Lädt Namen aus DB wenn nötig)."""
        path = os.path.join("data", "liga128_leagues.json")
        try:
            if not os.path.exists(path):
                return leagues
            with open(path, "r", encoding="utf-8") as f:
                wanted_ids = json.load(f)
            if not isinstance(wanted_ids, list):
                return leagues
            have = {entry["id"] for entry in leagues}
            missing = [int(i) for i in wanted_ids if isinstance(i, int) and i not in have]
            if not missing:
                return leagues
            try:
                from database import DatabaseManager
                dm = DatabaseManager("data/flashscore.db")
                conn = dm.get_connection()
                for lid in missing:
                    row = conn.execute(
                        "SELECT league_name, country_name FROM leagues WHERE league_id = ?",
                        (lid,),
                    ).fetchone()
                    if row and row[0]:
                        leagues.append(
                            {"id": lid, "name": row[0], "country": row[1] or "Unknown"}
                        )
                    else:
                        leagues.append({"id": lid, "name": f"League {lid}", "country": "Unknown"})
            except Exception as e:
                print(f"[WARNING] Could not enrich Liga-128 IDs for dropdown: {e}")
                for lid in missing:
                    leagues.append({"id": lid, "name": f"League {lid}", "country": "Unknown"})
        except Exception as e:
            print(f"[WARNING] _merge_liga128_ids_for_dropdown: {e}")
        return leagues
    
    def _on_league_selected(self, event=None):
        """Update league info when league is selected"""
        selection = self.selected_league_var.get()
        if selection and self.leagues_list:
            # Extract league ID from selection
            for league in self.leagues_list:
                display = f"{league['name']} ({league['country']}) - ID: {league['id']}"
                if display == selection:
                    self.league_info_label.config(
                        text=f"Selected: {league['name']} (ID: {league['id']})"
                    )
                    break
    
    def _load_games(self):
        """Load games for selected league and year"""
        if not self.loader_service:
            messagebox.showerror("Error", "Database service not initialized")
            return
        
        # Get selected league
        selection = self.selected_league_var.get()
        if not selection:
            messagebox.showerror("Error", "Please select a league")
            return
        
        # Extract league ID from selection
        league_id = None
        for league in self.leagues_list:
            display = f"{league['name']} ({league['country']}) - ID: {league['id']}"
            if display == selection:
                league_id = league['id']
                break
        
        if not league_id:
            messagebox.showerror("Error", "Invalid league selection")
            return
        
        try:
            year = int(self.year_var.get())
            load_details = self.load_details_var.get()
        except ValueError:
            messagebox.showerror("Error", "Please select a valid Year")
            return
        
        # Disable buttons during loading
        self.load_btn.config(state=tk.DISABLED)
        self.load_latest_btn.config(state=tk.DISABLED)
        self.load_multi_btn.config(state=tk.DISABLED)
        
        # Start loading in thread
        thread = threading.Thread(
            target=self._load_games_thread,
            args=(league_id, year, load_details),
            daemon=True
        )
        thread.start()
    
    def _load_latest_games(self):
        """Load latest games for selected league (auto-detect current season)"""
        if not self.loader_service:
            messagebox.showerror("Error", "Database service not initialized")
            return
        
        # Get selected league
        selection = self.selected_league_var.get()
        if not selection:
            messagebox.showerror("Error", "Please select a league")
            return
        
        # Extract league ID from selection
        league_id = None
        league_name = None
        for league in self.leagues_list:
            display = f"{league['name']} ({league['country']}) - ID: {league['id']}"
            if display == selection:
                league_id = league['id']
                league_name = league['name']
                break
        
        if not league_id:
            messagebox.showerror("Error", "Invalid league selection")
            return
        
        # Show progress dialog
        progress_window = tk.Toplevel(self)
        progress_window.title("Erkenne aktuelle Saison...")
        progress_window.geometry("400x100")
        progress_window.transient(self)
        progress_window.grab_set()
        
        progress_label = tk.Label(progress_window, text=f"Erkenne aktuelle Saison für {league_name}...")
        progress_label.pack(pady=20)
        
        progress_window.update()
        
        # Auto-detect current season year
        try:
            target_year = self.loader_service.detect_current_season_year(league_id)
            
            progress_window.destroy()
            
            if target_year is None:
                # Fallback to current year if detection fails
                from datetime import datetime
                target_year = datetime.now().year
                messagebox.showwarning(
                    "Saison-Erkennung",
                    f"Konnte aktuelle Saison nicht automatisch erkennen.\n"
                    f"Verwende {target_year} als Standard.\n\n"
                    f"Sie können auch manuell ein Jahr auswählen."
                )
            else:
                messagebox.showinfo(
                    "Saison erkannt",
                    f"Aktuelle Saison für {league_name}: {target_year}"
                )
        except Exception as e:
            progress_window.destroy()
            from datetime import datetime
            target_year = datetime.now().year
            messagebox.showwarning(
                "Saison-Erkennung",
                f"Fehler bei der automatischen Erkennung: {e}\n"
                f"Verwende {target_year} als Standard."
            )
        
        # Confirm action
        result = messagebox.askyesno(
            "Load Latest Games",
            f"Load latest games for {selection}?\n"
            f"This will load finished games for year {target_year} (current season).\n"
            f"Already existing games will be skipped."
        )
        
        if not result:
            return
        
        load_details = self.load_details_var.get()
        
        # Clear progress
        self.progress_label.config(text=f"Loading latest games for {target_year}...")
        self.progress_bar['value'] = 0
        self.results_text.delete("1.0", tk.END)
        self.results_text.insert("1.0", f"Loading latest games for league {league_id}, year {target_year}...\n")
        
        # Disable buttons during loading
        self.load_btn.config(state=tk.DISABLED)
        self.load_latest_btn.config(state=tk.DISABLED)
        self.load_multi_btn.config(state=tk.DISABLED)
        
        # Mark as "Load Latest Games" to skip all existing games
        if not hasattr(self, '_is_latest_load'):
            self._is_latest_load = False
        self._is_latest_load = True
        
        # Start loading in thread
        thread = threading.Thread(
            target=self._load_games_thread,
            args=(league_id, target_year, load_details),
            daemon=True
        )
        thread.start()
    
    def _load_games_thread(self, league_id: int, year: int, load_details: bool):
        """Thread function for loading games"""
        try:
            def progress_callback(current, total, message):
                self.after(0, self._update_progress, current, total, message)
            
            # For "Load Latest Games", skip all existing games (don't reload even if missing xG)
            # For normal "Load Games", reload existing games that are missing xG
            is_latest_load = hasattr(self, '_is_latest_load') and getattr(self, '_is_latest_load', False)
            stats = self.loader_service.load_games_for_league(
                league_id, year, 
                progress_callback=progress_callback,
                load_details=load_details,
                skip_existing=is_latest_load  # Skip all existing for "Load Latest Games"
            )
            
            # Reset flag after loading
            if hasattr(self, '_is_latest_load'):
                self._is_latest_load = False
            
            # Show results
            self.after(0, self._show_results, stats, league_id, year)
            
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Error", f"Failed to load games: {e}"))
            # Re-enable buttons on error
            self.after(0, lambda: self.load_btn.config(state=tk.NORMAL))
            self.after(0, lambda: self.load_latest_btn.config(state=tk.NORMAL))
            self.after(0, lambda: self.load_multi_btn.config(state=tk.NORMAL))
        finally:
            self.after(0, self._enable_buttons)
    
    def _update_progress(self, current: int, total: int, message: str):
        """Update progress bar and label"""
        if total > 0:
            self.progress_bar['maximum'] = total
            self.progress_bar['value'] = current
            percentage = (current / total) * 100
            self.progress_label.config(text=f"{message} ({current}/{total} - {percentage:.1f}%)")
        else:
            self.progress_label.config(text=message)
        self.update_idletasks()
    
    def _show_results(self, stats: dict, league_id: int, year: int):
        # Re-enable buttons
        self.load_btn.config(state=tk.NORMAL)
        self.load_latest_btn.config(state=tk.NORMAL)
        self.load_multi_btn.config(state=tk.NORMAL)
        """Show loading results"""
        results = f"""Loading completed for League {league_id}, Year {year}:

Total Games Found: {stats['total_found']}
Successfully Loaded: {stats['loaded']}
Already Existed: {stats['already_exists']}
Errors: {stats['errors']}

"""
        self.results_text.insert(tk.END, results)
        self.results_text.see(tk.END)
        
        # Refresh database info
        self._refresh_info()
        
        # Reset progress
        self.progress_bar['value'] = 0
        self.progress_label.config(text="")
        
        messagebox.showinfo("Loading Complete", 
                          f"Loaded {stats['loaded']} games\n"
                          f"Already existed: {stats['already_exists']}\n"
                          f"Errors: {stats['errors']}")
    
    def _load_latest_for_all_leagues(self):
        """Load latest games for all leagues that exist in database"""
        if not self.loader_service or not self.db_manager:
            messagebox.showerror("Error", "Database service not initialized")
            return
        
        # Confirm action
        result = messagebox.askyesno(
            "Load Latest Games for All Leagues",
            "This will load latest games (current year) for all leagues that already exist in the database.\n\n"
            "This may take a while. Continue?"
        )
        
        if not result:
            return
        
        # Get all unique leagues from database
        try:
            import sqlite3
            conn = self.db_manager.get_connection()
            conn.row_factory = sqlite3.Row
            
            leagues = conn.execute("""
                SELECT DISTINCT league_id, league_name, country_name, MAX(season_year) as latest_year
                FROM games
                GROUP BY league_id, league_name, country_name
                ORDER BY league_id
            """).fetchall()
            
            if not leagues:
                messagebox.showinfo("Info", "No leagues found in database.")
                return
            
            # Saison 26/27 = API-Jahr 2026
            target_year = 2026
            
            # Prepare leagues with 2026 for all
            leagues_with_years = []
            for league_row in leagues:
                league_id = league_row['league_id']
                latest_year_in_db = league_row['latest_year']
                
                leagues_with_years.append({
                    'league_id': league_id,
                    'league_name': league_row['league_name'],
                    'country_name': league_row['country_name'],
                    'target_year': target_year,
                    'latest_year_in_db': latest_year_in_db
                })
            
            # Clear progress
            self.progress_label.config(text=f"Loading latest games for {len(leagues_with_years)} leagues...")
            self.progress_bar['value'] = 0
            self.progress_bar['maximum'] = len(leagues_with_years)
            self.results_text.delete("1.0", tk.END)
            self.results_text.insert("1.0", f"Loading latest games for {len(leagues_with_years)} leagues...\n\n")
            
            # Disable buttons
            self.load_btn.config(state=tk.DISABLED)
            self.load_latest_btn.config(state=tk.DISABLED)
            self.load_all_latest_btn.config(state=tk.DISABLED)
            self.load_multi_btn.config(state=tk.DISABLED)
            
            # Start loading in thread
            thread = threading.Thread(target=self._load_all_leagues_thread, 
                                     args=(leagues_with_years,), daemon=True)
            thread.start()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to get leagues: {e}")
            self._enable_buttons()
    
    def _load_all_leagues_thread(self, leagues_with_years):
        """Thread function for loading latest games for all leagues"""
        total_loaded = 0
        total_existed = 0
        total_errors = 0
        load_details = self.load_details_var.get()
        
        try:
            for idx, league_info in enumerate(leagues_with_years):
                league_id = league_info['league_id']
                league_name = league_info['league_name']
                country = league_info['country_name']
                target_year = league_info['target_year']
                latest_year_in_db = league_info['latest_year_in_db']
                
                # Update progress - show which league we're processing
                progress_msg = f"Processing {idx + 1}/{len(leagues_with_years)}: {league_name} ({country}) - Year {target_year}..."
                self.after(0, self._update_progress, idx + 1, len(leagues_with_years), progress_msg)
                
                # Update results text to show we're starting this league
                year_info = f" (DB: {latest_year_in_db}, loading: {target_year})" if latest_year_in_db else f" (loading: {target_year})"
                start_text = f"[{idx + 1}/{len(leagues_with_years)}] Starting League {league_id} ({league_name}){year_info}...\n"
                self.after(0, lambda t=start_text: self.results_text.insert(tk.END, t))
                self.after(0, lambda: self.results_text.see(tk.END))
                self.after(0, self.update_idletasks)
                
                try:
                    # Use a progress callback that updates the message
                    def progress_callback(current, total, message):
                        # Update progress with more details
                        if total > 0:
                            detail_msg = f"{league_name} ({target_year}): {current}/{total} games"
                            self.after(0, self._update_progress, idx + 1, len(leagues_with_years), detail_msg)
                    
                    print(f"[INFO] Loading games for league {league_id} ({league_name}), year {target_year}...")
                    stats = self.loader_service.load_games_for_league(
                        league_id, target_year,
                        progress_callback=progress_callback,
                        load_details=load_details
                    )
                    
                    total_loaded += stats.get('loaded', 0)
                    total_existed += stats.get('already_exists', 0)
                    total_errors += stats.get('errors', 0)
                    
                    # Update results
                    result_text = f"  ✓ League {league_id} ({league_name}): Loaded {stats.get('loaded', 0)}, Existed {stats.get('already_exists', 0)}, Errors {stats.get('errors', 0)}\n"
                    self.after(0, lambda t=result_text: self.results_text.insert(tk.END, t))
                    self.after(0, lambda: self.results_text.see(tk.END))
                    self.after(0, self.update_idletasks)
                    
                    print(f"[INFO] Completed league {league_id}: {stats}")
                    
                except Exception as e:
                    total_errors += 1
                    error_text = f"  ✗ League {league_id} ({league_name}): Error - {str(e)}\n"
                    self.after(0, lambda t=error_text: self.results_text.insert(tk.END, t))
                    self.after(0, lambda: self.results_text.see(tk.END))
                    self.after(0, self.update_idletasks)
                    print(f"[ERROR] Failed to load games for league {league_id}: {e}")
                    import traceback
                    traceback.print_exc()
                    
                    # Continue with next league even if this one failed
                    continue
            
            # Show final results
            nl = len(leagues_with_years)
            final_text = f"\n{'='*60}\n"
            final_text += f"Total Leagues Processed: {nl}\n"
            final_text += f"Total Games Loaded: {total_loaded}\n"
            final_text += f"Total Games Already Existed: {total_existed}\n"
            final_text += f"Total Errors: {total_errors}\n"
            final_text += f"{'='*60}\n"
            
            self.after(0, lambda t=final_text: self.results_text.insert(tk.END, t))
            self.after(0, lambda: self.results_text.see(tk.END))
            
            # Tabs League + Liga 128 neu aus DB berechnen
            self.after(0, self._after_league_import_refresh)

            # Show message
            self.after(0, lambda: messagebox.showinfo(
                "Loading Complete",
                f"Processed {nl} leagues\n\n"
                f"Loaded: {total_loaded} games\n"
                f"Already existed: {total_existed} games\n"
                f"Errors: {total_errors}"
            ))
            
            # Refresh database info
            self.after(0, self._refresh_info)
            
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Error", f"Failed to load games: {e}"))
        finally:
            self.after(0, self._enable_buttons)
            self.after(0, lambda: self.progress_bar.config(value=0))
            self.after(0, lambda: self.progress_label.config(text=""))
    
    def _load_multiple_leagues(self):
        """Load games for selected leagues"""
        if not self.loader_service:
            messagebox.showerror("Error", "Database service not initialized")
            return
        
        # Create selection dialog
        select_window = tk.Toplevel(self)
        select_window.title("Select Leagues to Load")
        select_window.geometry("500x400")
        
        tk.Label(select_window, text="Select which leagues to load:", 
                font=("Arial", 10, "bold")).pack(pady=10)
        
        # League checkboxes
        leagues_frame = tk.Frame(select_window)
        leagues_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        scrollbar_leagues = ttk.Scrollbar(leagues_frame)
        scrollbar_leagues.pack(side=tk.RIGHT, fill=tk.Y)
        
        leagues_listbox = tk.Listbox(leagues_frame, selectmode=tk.MULTIPLE, 
                                     yscrollcommand=scrollbar_leagues.set)
        leagues_listbox.pack(fill=tk.BOTH, expand=True)
        scrollbar_leagues.config(command=leagues_listbox.yview)
        
        # Populate listbox
        league_vars = {}
        for league in self.leagues_list:
            display = f"{league['name']} ({league['country']}) - ID: {league['id']}"
            leagues_listbox.insert(tk.END, display)
            league_vars[display] = league
        
        # Year selection
        year_frame = tk.Frame(select_window)
        year_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(year_frame, text="Years to load:", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=5)
        
        year_vars = {}
        for year in [2022, 2023, 2024, 2025, 2026]:
            var = tk.BooleanVar(value=(year >= 2025))  # Default: 2025 and 2026
            year_vars[year] = var
            tk.Checkbutton(year_frame, text=str(year), variable=var).pack(side=tk.LEFT, padx=5)
        
        # Buttons
        button_frame = tk.Frame(select_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        def start_loading():
            selected_indices = leagues_listbox.curselection()
            if not selected_indices:
                messagebox.showwarning("Warning", "Please select at least one league")
                return
            
            selected_leagues = []
            for idx in selected_indices:
                display = leagues_listbox.get(idx)
                selected_leagues.append(league_vars[display])
            
            selected_years = [year for year, var in year_vars.items() if var.get()]
            if not selected_years:
                messagebox.showwarning("Warning", "Please select at least one year")
                return
            
            select_window.destroy()
            
            # Confirm
            total_combinations = len(selected_leagues) * len(selected_years)
            response = messagebox.askyesno(
                "Confirm", 
                f"This will load games for {len(selected_leagues)} leagues and {len(selected_years)} years.\n"
                f"Total: {total_combinations} combinations.\n\n"
                f"This may take a very long time due to rate limiting.\n"
                f"Estimated: ~{total_combinations * 2 // 60} minutes\n\n"
                f"Continue?"
            )
            
            if not response:
                return
            
            # Start loading
            self._load_selected_leagues(selected_leagues, selected_years)
        
        tk.Button(button_frame, text="Start Loading", command=start_loading,
                 bg="#4CAF50", fg="white", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Cancel", command=select_window.destroy).pack(side=tk.LEFT, padx=5)
        
        # Select all by default
        leagues_listbox.selection_set(0, tk.END)
    
    def _load_selected_leagues(self, leagues, years):
        """Load games for selected leagues and years"""
        # Disable buttons
        self.load_btn.config(state=tk.DISABLED)
        self.load_multi_btn.config(state=tk.DISABLED)
        
        # Start loading in thread
        thread = threading.Thread(
            target=self._load_selected_leagues_thread,
            args=(leagues, years),
            daemon=True
        )
        thread.start()
    
    def _load_selected_leagues_thread(self, leagues, years):
        """Thread function for loading selected leagues"""
        try:
            total_combinations = len(leagues) * len(years)
            current = 0
            
            overall_stats = {
                "total_loaded": 0,
                "total_skipped": 0,
                "total_errors": 0,
                "total_already_exists": 0,
                "league_stats": {}
            }
            
            for league in leagues:
                for year in years:
                    current += 1
                    league_name = league['name']
                    
                    def progress_callback(cur, tot, msg):
                        self.after(0, self._update_progress, 
                                  current, total_combinations, 
                                  f"{league_name} {year}: {msg}")
                    
                    stats = self.loader_service.load_games_for_league(
                        league['id'], year,
                        progress_callback=progress_callback,
                        load_details=self.load_details_var.get()
                    )
                    
                    overall_stats["total_loaded"] += stats['loaded']
                    overall_stats["total_skipped"] += stats['skipped']
                    overall_stats["total_errors"] += stats['errors']
                    overall_stats["total_already_exists"] += stats['already_exists']
                    
                    key = f"{league_name} {year}"
                    overall_stats["league_stats"][key] = stats
            
            # Show results
            self.after(0, self._show_multiple_results, overall_stats)
            
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Error", f"Failed to load games: {e}"))
            # Re-enable buttons on error
            self.after(0, lambda: self.load_btn.config(state=tk.NORMAL))
            self.after(0, lambda: self.load_latest_btn.config(state=tk.NORMAL))
            self.after(0, lambda: self.load_multi_btn.config(state=tk.NORMAL))
    
    def _show_multiple_results(self, stats: dict):
        """Show results for multiple leagues loading"""
        results = f"""Multiple Leagues Loading Completed:

Total Games Loaded: {stats['total_loaded']}
Total Already Existed: {stats['total_already_exists']}
Total Errors: {stats['total_errors']}

League-by-League Results:
"""
        for key, league_stats in stats['league_stats'].items():
            results += f"\n{key}:\n"
            results += f"  Loaded: {league_stats['loaded']}, "
            results += f"Already Existed: {league_stats['already_exists']}, "
            results += f"Errors: {league_stats['errors']}\n"
        
        self.results_text.insert(tk.END, results)
        self.results_text.see(tk.END)
        
        # Refresh database info
        self._refresh_info()

        self._after_league_import_refresh()
        
        # Reset progress
        self.progress_bar['value'] = 0
        self.progress_label.config(text="")
        
        messagebox.showinfo("Loading Complete", 
                          f"Total loaded: {stats['total_loaded']} games\n"
                          f"Already existed: {stats['total_already_exists']}\n"
                          f"Errors: {stats['total_errors']}")
    
    def _enable_buttons(self):
        """Re-enable buttons after loading"""
        self.load_btn.config(state=tk.NORMAL)
        self.load_latest_btn.config(state=tk.NORMAL)
        self.load_multi_btn.config(state=tk.NORMAL)
        self.load_all_latest_btn.config(state=tk.NORMAL)
    
    def _toggle_auto_loader(self):
        """Start or stop the auto-loader"""
        if not self.auto_loader_service:
            messagebox.showerror("Error", "Auto-loader service not initialized")
            return
        
        if self.auto_loader_service.is_running():
            self.auto_loader_service.stop()
            self.auto_loader_btn.config(text="Start Auto-Loader", bg="#FF9800")
            self.auto_loader_status_label.config(text="Status: Stopped", fg="gray")
        else:
            # Check if any leagues are configured
            if not self.auto_loader_service.leagues_to_monitor:
                messagebox.showwarning("No Leagues Configured", 
                                      "Please configure at least one league to monitor.\n"
                                      "Click 'Configure' to set up monitored leagues.")
                return
            
            # Start auto-loader (check every 5 minutes)
            self.auto_loader_service.start(check_interval_seconds=300)
            self.auto_loader_btn.config(text="Stop Auto-Loader", bg="#F44336")
            self.auto_loader_status_label.config(text="Status: Running", fg="green")
    
    def _auto_loader_status(self, message: str):
        """Callback for auto-loader status updates"""
        self.after(0, self._update_auto_status, message)
    
    def _update_auto_status(self, message: str):
        """Update auto-loader status text (called from main thread)"""
        self.auto_status_text.config(state=tk.NORMAL)
        timestamp = time.strftime("%H:%M:%S")
        self.auto_status_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.auto_status_text.see(tk.END)
        # Keep only last 50 lines
        lines = self.auto_status_text.get("1.0", tk.END).split('\n')
        if len(lines) > 50:
            self.auto_status_text.delete("1.0", f"{len(lines) - 50}.0")
        self.auto_status_text.config(state=tk.DISABLED)
    
    def _configure_auto_loader(self):
        """Open dialog to configure which leagues to monitor"""
        if not self.auto_loader_service:
            messagebox.showerror("Error", "Auto-loader service not initialized")
            return
        
        # Create configuration window
        config_window = tk.Toplevel(self)
        config_window.title("Configure Auto-Loader")
        config_window.geometry("400x300")
        
        tk.Label(config_window, text="Select leagues and years to monitor:", 
                font=("Arial", 10, "bold")).pack(pady=10)
        
        # League selection
        league_frame = tk.Frame(config_window)
        league_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(league_frame, text="League ID:").pack(side=tk.LEFT, padx=5)
        league_id_var = tk.StringVar(value="188")
        tk.Entry(league_frame, textvariable=league_id_var, width=10).pack(side=tk.LEFT, padx=5)
        
        # Year selection
        year_frame = tk.Frame(config_window)
        year_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(year_frame, text="Years (comma-separated):").pack(side=tk.LEFT, padx=5)
        years_var = tk.StringVar(value="2022,2023,2024,2025,2026")
        tk.Entry(year_frame, textvariable=years_var, width=20).pack(side=tk.LEFT, padx=5)
        
        # Current monitored leagues
        current_frame = tk.Frame(config_window)
        current_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        tk.Label(current_frame, text="Currently Monitored:", font=("Arial", 9, "bold")).pack(anchor=tk.W)
        current_list = tk.Text(current_frame, height=8, width=40)
        current_list.pack(fill=tk.BOTH, expand=True)
        
        # Update current list
        def update_list():
            current_list.delete("1.0", tk.END)
            if self.auto_loader_service.leagues_to_monitor:
                for league_id, year in self.auto_loader_service.leagues_to_monitor:
                    current_list.insert(tk.END, f"League {league_id}, Year {year}\n")
            else:
                current_list.insert(tk.END, "None")
            current_list.config(state=tk.DISABLED)
        
        update_list()
        
        # Buttons
        button_frame = tk.Frame(config_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        def add_league():
            try:
                league_id = int(league_id_var.get())
                years_str = years_var.get()
                years = [int(y.strip()) for y in years_str.split(',')]
                
                self.auto_loader_service.add_league_to_monitor(league_id, years)
                update_list()
                current_list.config(state=tk.NORMAL)
                current_list.insert(tk.END, f"Added: League {league_id}, Years {years}\n")
                current_list.config(state=tk.DISABLED)
                
                # Update displayed leagues
                leagues_str = ", ".join([f"L{lid}" for lid, _ in set(self.auto_loader_service.leagues_to_monitor)])
                self.monitored_leagues_label.config(text=leagues_str or "None")
            except ValueError:
                messagebox.showerror("Error", "Please enter valid League ID and Years")
        
        def clear_all():
            self.auto_loader_service.leagues_to_monitor = []
            update_list()
            self.monitored_leagues_label.config(text="None")
        
        tk.Button(button_frame, text="Add League", command=add_league, 
                 bg="#4CAF50", fg="white").pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Clear All", command=clear_all, 
                 bg="#F44336", fg="white").pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Close", command=config_window.destroy).pack(side=tk.LEFT, padx=5)
        
        # Update displayed leagues
        leagues_str = ", ".join([f"L{lid}" for lid, _ in set(self.auto_loader_service.leagues_to_monitor)])
        self.monitored_leagues_label.config(text=leagues_str or "None")

