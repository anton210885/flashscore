"""Strategy Builder Tab - Build and test betting strategies based on database data"""
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import sqlite3
import json
import os
import csv
from typing import Dict, List, Optional, Tuple
from datetime import datetime
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
try:
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

from services import strategy_service as strat


class StrategyTab(tk.Frame):
    """Tab for building and testing betting strategies"""
    
    def __init__(self, parent, services):
        super().__init__(parent)
        self.services = services
        self.db_path = "data/flashscore.db"
        self.strategies_path = "data/strategies.json"
        self.strategy_results = []
        self.metric_ranking_report = None
        self.bucket_report = None
        self.saved_strategies = {}
        self.current_strategy_name = None
        self.load_strategies()
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the modern redesigned UI for strategy building"""
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        header_frame = tk.Frame(main_frame, bg="#2c3e50", height=50)
        header_frame.pack(fill=tk.X, pady=(0, 5))
        header_frame.pack_propagate(False)
        
        title_label = tk.Label(header_frame, text="🎯 Strategie Builder", 
                               font=("Segoe UI", 18, "bold"), 
                               bg="#2c3e50", fg="white")
        title_label.pack(pady=12)

        # Feste Aktionsleiste ganz unten — sichtbar in jedem Unter-Tab
        self._setup_fixed_action_bar(main_frame)
        
        self.main_paned = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        self.main_paned.pack(fill=tk.BOTH, expand=True)
        
        left_frame = ttk.Frame(self.main_paned)
        self.main_paned.add(left_frame)
        
        right_frame = ttk.Frame(self.main_paned, width=300)
        right_frame.pack_propagate(False)
        self.main_paned.add(right_frame)
        
        def set_sash_position():
            try:
                self.update_idletasks()
                paned_width = self.main_paned.winfo_width()
                if paned_width > 100:
                    sash_position = int(paned_width * 0.80)
                    self.main_paned.sashpos(0, sash_position)
            except Exception:
                pass
        
        self.after(100, set_sash_position)
        
        self.setup_filter_panel(left_frame)
        self.setup_results_panel(right_frame)

    def _setup_fixed_action_bar(self, parent):
        """Aktionsbuttons fix am unteren Rand des Strategien-Tabs."""
        bar = tk.Frame(parent, bg="#1e293b", padx=8, pady=8)
        bar.pack(side=tk.BOTTOM, fill=tk.X)

        ttk.Button(
            bar, text="📊 Strategie Analysieren",
            command=self.analyze_strategy,
        ).pack(side=tk.LEFT, padx=(0, 6), fill=tk.X, expand=True)

        ttk.Button(
            bar, text="📈 Metric Ranking",
            command=self.run_metric_ranking,
        ).pack(side=tk.LEFT, padx=(0, 6), fill=tk.X, expand=True)

        ttk.Button(
            bar, text="📦 Bucket Analyse",
            command=self.run_bucket_analysis,
        ).pack(side=tk.LEFT, padx=(0, 6), fill=tk.X, expand=True)

        ttk.Button(
            bar, text="🔍 Zukünftige Matches",
            command=self.check_matches_against_strategies,
        ).pack(side=tk.LEFT, padx=(0, 6), fill=tk.X, expand=True)

        ttk.Button(bar, text="📤 CSV", command=self.export_results_csv).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(
            bar, text="📥 Opening Odds", command=self.load_opening_odds_for_strategies
        ).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(bar, text="🔄 Reset", command=self.reset_filters).pack(side=tk.LEFT)
    
    def setup_filter_panel(self, parent):
        """Setup the modern redesigned filter configuration panel"""
        container = ttk.Frame(parent)
        container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        filter_notebook = ttk.Notebook(container)
        filter_notebook.pack(fill=tk.BOTH, expand=True)

        basic_tab = ttk.Frame(filter_notebook)
        filter_notebook.add(basic_tab, text="📊 Basis Filter")
        self.setup_basic_filters(basic_tab)

        advanced_tab = ttk.Frame(filter_notebook)
        filter_notebook.add(advanced_tab, text="🔧 Erweiterte Filter")
        self.setup_advanced_filters(advanced_tab)

        strategy_tab = ttk.Frame(filter_notebook)
        filter_notebook.add(strategy_tab, text="💾 Strategien")
        self.setup_strategy_management(strategy_tab)

        actions_tab = ttk.Frame(filter_notebook)
        filter_notebook.add(actions_tab, text="🚀 Mehr")
        self.setup_actions(actions_tab)
    
    def setup_basic_filters(self, parent):
        """Setup basic filter options"""
        # Create scrollable canvas
        canvas = tk.Canvas(parent, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        def update_scroll_region(event=None):
            canvas.update_idletasks()
            bbox = canvas.bbox("all")
            if bbox:
                canvas.configure(scrollregion=bbox)
        
        scrollable_frame.bind("<Configure>", update_scroll_region)
        
        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        def configure_canvas_window(event):
            canvas_width = event.width
            canvas.itemconfig(canvas_window, width=canvas_width)
            canvas.configure(scrollregion=canvas.bbox("all"))
        canvas.bind('<Configure>', configure_canvas_window)
        
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        filter_content = scrollable_frame
        
        # Initialize market variables
        self.market_home = tk.BooleanVar(value=False)
        self.market_draw = tk.BooleanVar(value=False)
        self.market_away = tk.BooleanVar(value=False)
        self.market_over = tk.BooleanVar(value=False)
        self.market_under = tk.BooleanVar(value=False)
        self.market_over_35 = tk.BooleanVar(value=False)
        self.market_under_35 = tk.BooleanVar(value=False)
        self.market_over_45 = tk.BooleanVar(value=False)
        self.market_under_45 = tk.BooleanVar(value=False)
        
        # Initialize odds variables
        self.odds_home_min = tk.StringVar(value="")
        self.odds_home_max = tk.StringVar(value="")
        self.odds_draw_min = tk.StringVar(value="")
        self.odds_draw_max = tk.StringVar(value="")
        self.odds_away_min = tk.StringVar(value="")
        self.odds_away_max = tk.StringVar(value="")
        self.odds_over_min = tk.StringVar(value="")
        self.odds_over_max = tk.StringVar(value="")
        self.odds_under_min = tk.StringVar(value="")
        self.odds_under_max = tk.StringVar(value="")
        self.odds_over35_min = tk.StringVar(value="")
        self.odds_over35_max = tk.StringVar(value="")
        self.odds_under35_min = tk.StringVar(value="")
        self.odds_under35_max = tk.StringVar(value="")
        self.odds_over45_min = tk.StringVar(value="")
        self.odds_over45_max = tk.StringVar(value="")
        self.odds_under45_min = tk.StringVar(value="")
        self.odds_under45_max = tk.StringVar(value="")
        self.odds_type = tk.StringVar(value="closing")
        self.date_from = tk.StringVar(value="")
        self.date_to = tk.StringVar(value="")
        
        # Initialize other variables
        self.glicko_home_min = tk.StringVar(value="")
        self.glicko_home_max = tk.StringVar(value="")
        self.glicko_away_min = tk.StringVar(value="")
        self.glicko_away_max = tk.StringVar(value="")
        self.glicko_rd_home_min = tk.StringVar(value="")
        self.glicko_rd_home_max = tk.StringVar(value="")
        self.glicko_rd_away_min = tk.StringVar(value="")
        self.glicko_rd_away_max = tk.StringVar(value="")
        self.glicko_vol_home_min = tk.StringVar(value="")
        self.glicko_vol_home_max = tk.StringVar(value="")
        self.glicko_vol_away_min = tk.StringVar(value="")
        self.glicko_vol_away_max = tk.StringVar(value="")
        self.glicko_p_home_min = tk.StringVar(value="")
        self.glicko_p_home_max = tk.StringVar(value="")
        self.glicko_p_draw_min = tk.StringVar(value="")
        self.glicko_p_draw_max = tk.StringVar(value="")
        self.glicko_p_away_min = tk.StringVar(value="")
        self.glicko_p_away_max = tk.StringVar(value="")
        self.xg_glicko_home_min = tk.StringVar(value="")
        self.xg_glicko_home_max = tk.StringVar(value="")
        self.xg_glicko_away_min = tk.StringVar(value="")
        self.xg_glicko_away_max = tk.StringVar(value="")
        self.season_games_home_min = tk.StringVar(value="")
        self.season_games_home_max = tk.StringVar(value="")
        self.season_games_away_min = tk.StringVar(value="")
        self.season_games_away_max = tk.StringVar(value="")
        self.chance_min = tk.StringVar(value="")
        self.chance_max = tk.StringVar(value="")
        self.country_filter = tk.StringVar(value="")
        self.league_filter = tk.StringVar(value="")
        self.gender_filter = tk.StringVar(value="men")  # all | men | women
        self.min_games_count = tk.StringVar(value="5")
        
        # ---------- MARKET SELECTION ----------
        market_frame = ttk.LabelFrame(filter_content, text="📊 Markt Auswahl", padding=15)
        market_frame.pack(fill=tk.X, pady=(10, 15))
        
        market_grid = ttk.Frame(market_frame)
        market_grid.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Checkbutton(market_grid, text="Home", variable=self.market_home).grid(row=0, column=0, padx=12, pady=4, sticky="w")
        ttk.Checkbutton(market_grid, text="Draw", variable=self.market_draw).grid(row=0, column=1, padx=12, pady=4, sticky="w")
        ttk.Checkbutton(market_grid, text="Away", variable=self.market_away).grid(row=0, column=2, padx=12, pady=4, sticky="w")
        ttk.Checkbutton(market_grid, text="Over 2.5", variable=self.market_over).grid(row=1, column=0, padx=12, pady=4, sticky="w")
        ttk.Checkbutton(market_grid, text="Under 2.5", variable=self.market_under).grid(row=1, column=1, padx=12, pady=4, sticky="w")
        ttk.Checkbutton(market_grid, text="Over 3.5", variable=self.market_over_35).grid(row=2, column=0, padx=12, pady=4, sticky="w")
        ttk.Checkbutton(market_grid, text="Under 3.5", variable=self.market_under_35).grid(row=2, column=1, padx=12, pady=4, sticky="w")
        ttk.Checkbutton(market_grid, text="Over 4.5", variable=self.market_over_45).grid(row=3, column=0, padx=12, pady=4, sticky="w")
        ttk.Checkbutton(market_grid, text="Under 4.5", variable=self.market_under_45).grid(row=3, column=1, padx=12, pady=4, sticky="w")
        
        for col in range(3):
            market_grid.columnconfigure(col, weight=1)
        
        # ---------- GLICKO RATING ----------
        glicko_frame = ttk.LabelFrame(filter_content, text="⭐ Glicko Rating", padding=15)
        glicko_frame.pack(fill=tk.X, pady=(0, 15))
        
        glicko_home_row = ttk.Frame(glicko_frame)
        glicko_home_row.pack(fill=tk.X, pady=8, padx=10)
        ttk.Label(glicko_home_row, text="Home Rating:", width=12, anchor="w").pack(side=tk.LEFT, padx=5)
        ttk.Entry(glicko_home_row, textvariable=self.glicko_home_min, width=12).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        ttk.Label(glicko_home_row, text="bis", anchor="w").pack(side=tk.LEFT, padx=5)
        ttk.Entry(glicko_home_row, textvariable=self.glicko_home_max, width=12).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        
        glicko_away_row = ttk.Frame(glicko_frame)
        glicko_away_row.pack(fill=tk.X, pady=8, padx=10)
        ttk.Label(glicko_away_row, text="Away Rating:", width=12, anchor="w").pack(side=tk.LEFT, padx=5)
        ttk.Entry(glicko_away_row, textvariable=self.glicko_away_min, width=12).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        ttk.Label(glicko_away_row, text="bis", anchor="w").pack(side=tk.LEFT, padx=5)
        ttk.Entry(glicko_away_row, textvariable=self.glicko_away_max, width=12).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)

        glicko_rd_h = ttk.Frame(glicko_frame)
        glicko_rd_h.pack(fill=tk.X, pady=4, padx=10)
        ttk.Label(glicko_rd_h, text="Home RD:", width=12, anchor="w").pack(side=tk.LEFT, padx=5)
        ttk.Entry(glicko_rd_h, textvariable=self.glicko_rd_home_min, width=12).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        ttk.Label(glicko_rd_h, text="bis", anchor="w").pack(side=tk.LEFT, padx=5)
        ttk.Entry(glicko_rd_h, textvariable=self.glicko_rd_home_max, width=12).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)

        glicko_rd_a = ttk.Frame(glicko_frame)
        glicko_rd_a.pack(fill=tk.X, pady=4, padx=10)
        ttk.Label(glicko_rd_a, text="Away RD:", width=12, anchor="w").pack(side=tk.LEFT, padx=5)
        ttk.Entry(glicko_rd_a, textvariable=self.glicko_rd_away_min, width=12).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        ttk.Label(glicko_rd_a, text="bis", anchor="w").pack(side=tk.LEFT, padx=5)
        ttk.Entry(glicko_rd_a, textvariable=self.glicko_rd_away_max, width=12).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)

        glicko_vol_h = ttk.Frame(glicko_frame)
        glicko_vol_h.pack(fill=tk.X, pady=4, padx=10)
        ttk.Label(glicko_vol_h, text="Home Vol:", width=12, anchor="w").pack(side=tk.LEFT, padx=5)
        ttk.Entry(glicko_vol_h, textvariable=self.glicko_vol_home_min, width=12).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        ttk.Label(glicko_vol_h, text="bis", anchor="w").pack(side=tk.LEFT, padx=5)
        ttk.Entry(glicko_vol_h, textvariable=self.glicko_vol_home_max, width=12).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)

        glicko_vol_a = ttk.Frame(glicko_frame)
        glicko_vol_a.pack(fill=tk.X, pady=4, padx=10)
        ttk.Label(glicko_vol_a, text="Away Vol:", width=12, anchor="w").pack(side=tk.LEFT, padx=5)
        ttk.Entry(glicko_vol_a, textvariable=self.glicko_vol_away_min, width=12).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        ttk.Label(glicko_vol_a, text="bis", anchor="w").pack(side=tk.LEFT, padx=5)
        ttk.Entry(glicko_vol_a, textvariable=self.glicko_vol_away_max, width=12).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)

        glicko_p_h = ttk.Frame(glicko_frame)
        glicko_p_h.pack(fill=tk.X, pady=4, padx=10)
        ttk.Label(glicko_p_h, text="P(Home) %:", width=12, anchor="w").pack(side=tk.LEFT, padx=5)
        ttk.Entry(glicko_p_h, textvariable=self.glicko_p_home_min, width=12).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        ttk.Label(glicko_p_h, text="bis", anchor="w").pack(side=tk.LEFT, padx=5)
        ttk.Entry(glicko_p_h, textvariable=self.glicko_p_home_max, width=12).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)

        glicko_p_d = ttk.Frame(glicko_frame)
        glicko_p_d.pack(fill=tk.X, pady=4, padx=10)
        ttk.Label(glicko_p_d, text="P(Draw) %:", width=12, anchor="w").pack(side=tk.LEFT, padx=5)
        ttk.Entry(glicko_p_d, textvariable=self.glicko_p_draw_min, width=12).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        ttk.Label(glicko_p_d, text="bis", anchor="w").pack(side=tk.LEFT, padx=5)
        ttk.Entry(glicko_p_d, textvariable=self.glicko_p_draw_max, width=12).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)

        glicko_p_a = ttk.Frame(glicko_frame)
        glicko_p_a.pack(fill=tk.X, pady=4, padx=10)
        ttk.Label(glicko_p_a, text="P(Away) %:", width=12, anchor="w").pack(side=tk.LEFT, padx=5)
        ttk.Entry(glicko_p_a, textvariable=self.glicko_p_away_min, width=12).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        ttk.Label(glicko_p_a, text="bis", anchor="w").pack(side=tk.LEFT, padx=5)
        ttk.Entry(glicko_p_a, textvariable=self.glicko_p_away_max, width=12).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)

        # ---------- GLICKO xG ----------
        xg_frame = ttk.LabelFrame(filter_content, text="⚡ Glicko xG (dieses Spiel)", padding=15)
        xg_frame.pack(fill=tk.X, pady=(0, 15))

        xg_home_row = ttk.Frame(xg_frame)
        xg_home_row.pack(fill=tk.X, pady=8, padx=10)
        ttk.Label(xg_home_row, text="Home xG:", width=12, anchor="w").pack(side=tk.LEFT, padx=5)
        ttk.Entry(xg_home_row, textvariable=self.xg_glicko_home_min, width=12).pack(
            side=tk.LEFT, padx=2, fill=tk.X, expand=True
        )
        ttk.Label(xg_home_row, text="bis", anchor="w").pack(side=tk.LEFT, padx=5)
        ttk.Entry(xg_home_row, textvariable=self.xg_glicko_home_max, width=12).pack(
            side=tk.LEFT, padx=2, fill=tk.X, expand=True
        )

        xg_away_row = ttk.Frame(xg_frame)
        xg_away_row.pack(fill=tk.X, pady=8, padx=10)
        ttk.Label(xg_away_row, text="Away xG:", width=12, anchor="w").pack(side=tk.LEFT, padx=5)
        ttk.Entry(xg_away_row, textvariable=self.xg_glicko_away_min, width=12).pack(
            side=tk.LEFT, padx=2, fill=tk.X, expand=True
        )
        ttk.Label(xg_away_row, text="bis", anchor="w").pack(side=tk.LEFT, padx=5)
        ttk.Entry(xg_away_row, textvariable=self.xg_glicko_away_max, width=12).pack(
            side=tk.LEFT, padx=2, fill=tk.X, expand=True
        )
        ttk.Label(
            xg_frame,
            text="Beispiel: Home 1.0–1.5 und Away 0.8–1.0",
            foreground="#666",
        ).pack(anchor=tk.W, padx=15, pady=(0, 4))

        # ---------- SAISON-SPIELNUMMER ----------
        season_n_frame = ttk.LabelFrame(
            filter_content,
            text="📅 Saison-Spielnummer (pro Team, gleiche Liga + Season)",
            padding=15,
        )
        season_n_frame.pack(fill=tk.X, pady=(0, 15))

        sn_home = ttk.Frame(season_n_frame)
        sn_home.pack(fill=tk.X, pady=8, padx=10)
        ttk.Label(sn_home, text="Home Spiel-Nr:", width=14, anchor="w").pack(side=tk.LEFT, padx=5)
        ttk.Entry(sn_home, textvariable=self.season_games_home_min, width=10).pack(side=tk.LEFT, padx=2)
        ttk.Label(sn_home, text="bis", anchor="w").pack(side=tk.LEFT, padx=5)
        ttk.Entry(sn_home, textvariable=self.season_games_home_max, width=10).pack(side=tk.LEFT, padx=2)

        sn_away = ttk.Frame(season_n_frame)
        sn_away.pack(fill=tk.X, pady=8, padx=10)
        ttk.Label(sn_away, text="Away Spiel-Nr:", width=14, anchor="w").pack(side=tk.LEFT, padx=5)
        ttk.Entry(sn_away, textvariable=self.season_games_away_min, width=10).pack(side=tk.LEFT, padx=2)
        ttk.Label(sn_away, text="bis", anchor="w").pack(side=tk.LEFT, padx=5)
        ttk.Entry(sn_away, textvariable=self.season_games_away_max, width=10).pack(side=tk.LEFT, padx=2)

        ttk.Label(
            season_n_frame,
            text=(
                "1 = erstes Meisterschaftsspiel der Saison. "
                "Bei Spiel-Nr. 5 siehst du das Glicko-xG genau in diesem 5. Saisonspiel "
                "(kann später bei Spiel 20 anders sein)."
            ),
            foreground="#666",
            wraplength=480,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, padx=15, pady=(0, 4))
        
        # ---------- ODDS FILTER (Hauptkriterium) ----------
        odds_frame = ttk.LabelFrame(filter_content, text="💰 Quote Filter (Hauptkriterium)", padding=15)
        odds_frame.pack(fill=tk.X, pady=(0, 15))
        
        def create_odds_row(parent, label, min_var, max_var):
            row = ttk.Frame(parent)
            row.pack(fill=tk.X, pady=5, padx=10)
            ttk.Label(row, text=f"{label}:", width=15, anchor="w").pack(side=tk.LEFT, padx=5)
            ttk.Label(row, text="Von:", anchor="w").pack(side=tk.LEFT, padx=5)
            ttk.Entry(row, textvariable=min_var, width=12).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
            ttk.Label(row, text="Bis:", anchor="w").pack(side=tk.LEFT, padx=5)
            ttk.Entry(row, textvariable=max_var, width=12).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        
        create_odds_row(odds_frame, "Home Quote", self.odds_home_min, self.odds_home_max)
        create_odds_row(odds_frame, "Draw Quote", self.odds_draw_min, self.odds_draw_max)
        create_odds_row(odds_frame, "Away Quote", self.odds_away_min, self.odds_away_max)
        create_odds_row(odds_frame, "Over 2.5 Quote", self.odds_over_min, self.odds_over_max)
        create_odds_row(odds_frame, "Under 2.5 Quote", self.odds_under_min, self.odds_under_max)
        create_odds_row(odds_frame, "Over 3.5 Quote", self.odds_over35_min, self.odds_over35_max)
        create_odds_row(odds_frame, "Under 3.5 Quote", self.odds_under35_min, self.odds_under35_max)
        create_odds_row(odds_frame, "Over 4.5 Quote", self.odds_over45_min, self.odds_over45_max)
        create_odds_row(odds_frame, "Under 4.5 Quote", self.odds_under45_min, self.odds_under45_max)
        
        odds_type_row = ttk.Frame(odds_frame)
        odds_type_row.pack(fill=tk.X, pady=8, padx=10)
        ttk.Label(odds_type_row, text="Quoten-Typ:", width=15, anchor="w").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(
            odds_type_row, text="Closing (vor Anpfiff)", variable=self.odds_type, value="closing"
        ).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(
            odds_type_row, text="Opening (Eröffnung)", variable=self.odds_type, value="opening"
        ).pack(side=tk.LEFT, padx=5)

        odds_load_row = ttk.Frame(odds_frame)
        odds_load_row.pack(fill=tk.X, pady=(0, 8), padx=10)
        ttk.Button(
            odds_load_row,
            text="Opening-Odds laden (Pinnacle)",
            command=self.load_opening_odds_for_strategies,
        ).pack(side=tk.LEFT)
        ttk.Label(
            odds_load_row,
            text="API: opening=true → Spalte opening_value (nur Strategien)",
            foreground="#666",
        ).pack(side=tk.LEFT, padx=8)
        
        # ---------- CHANCE FILTER ----------
        chance_frame = ttk.LabelFrame(filter_content, text="🎯 Gewinnwahrscheinlichkeit", padding=15)
        chance_frame.pack(fill=tk.X, pady=(0, 15))
        
        chance_row = ttk.Frame(chance_frame)
        chance_row.pack(fill=tk.X, pady=8, padx=10)
        ttk.Label(chance_row, text="Min Chance:", width=12, anchor="w").pack(side=tk.LEFT, padx=5)
        ttk.Entry(chance_row, textvariable=self.chance_min, width=15).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        ttk.Label(chance_row, text="Max Chance:", width=12, anchor="w").pack(side=tk.LEFT, padx=5)
        ttk.Entry(chance_row, textvariable=self.chance_max, width=15).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        
        # ---------- LOCATION FILTER ----------
        location_frame = ttk.LabelFrame(filter_content, text="🌍 Land & Liga & Geschlecht", padding=15)
        location_frame.pack(fill=tk.X, pady=(0, 15))

        gender_row = ttk.Frame(location_frame)
        gender_row.pack(fill=tk.X, pady=5, padx=10)
        ttk.Label(gender_row, text="Geschlecht:", width=12, anchor="w").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(gender_row, text="Männer", variable=self.gender_filter, value="men").pack(side=tk.LEFT, padx=4)
        ttk.Radiobutton(gender_row, text="Frauen", variable=self.gender_filter, value="women").pack(side=tk.LEFT, padx=4)
        ttk.Radiobutton(gender_row, text="Beide", variable=self.gender_filter, value="all").pack(side=tk.LEFT, padx=4)
        ttk.Label(
            gender_row,
            text="(Hauptkriterium · über Liga-Name)",
            foreground="#666",
        ).pack(side=tk.LEFT, padx=6)
        
        country_row = ttk.Frame(location_frame)
        country_row.pack(fill=tk.X, pady=5, padx=10)
        ttk.Label(country_row, text="Land:", width=12, anchor="w").pack(side=tk.LEFT, padx=5)
        ttk.Entry(country_row, textvariable=self.country_filter).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        
        league_row = ttk.Frame(location_frame)
        league_row.pack(fill=tk.X, pady=5, padx=10)
        ttk.Label(league_row, text="Liga:", width=12, anchor="w").pack(side=tk.LEFT, padx=5)
        ttk.Entry(league_row, textvariable=self.league_filter).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        
        date_row = ttk.Frame(location_frame)
        date_row.pack(fill=tk.X, pady=5, padx=10)
        ttk.Label(date_row, text="Datum von:", width=12, anchor="w").pack(side=tk.LEFT, padx=5)
        ttk.Entry(date_row, textvariable=self.date_from, width=12).pack(side=tk.LEFT, padx=2)
        ttk.Label(date_row, text="bis:", anchor="w").pack(side=tk.LEFT, padx=5)
        ttk.Entry(date_row, textvariable=self.date_to, width=12).pack(side=tk.LEFT, padx=2)
        ttk.Label(date_row, text="(YYYY-MM-DD)", foreground="gray").pack(side=tk.LEFT, padx=5)
        
        # ---------- SETTINGS ----------
        games_frame = ttk.LabelFrame(filter_content, text="⚙️ Einstellungen", padding=15)
        games_frame.pack(fill=tk.X, pady=(0, 10))
        
        games_row = ttk.Frame(games_frame)
        games_row.pack(fill=tk.X, pady=8, padx=10)
        ttk.Label(games_row, text="Min. Sample:", width=12, anchor="w").pack(side=tk.LEFT, padx=5)
        ttk.Entry(games_row, textvariable=self.min_games_count, width=15).pack(side=tk.LEFT, padx=2)
        ttk.Label(
            games_row,
            text="(Profits-Stichprobe, nicht Saison-Spielnr.)",
            foreground="#666",
        ).pack(side=tk.LEFT, padx=6)
    
    def setup_advanced_filters(self, parent):
        """Setup advanced filter options"""
        canvas = tk.Canvas(parent, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        def update_scroll_region(event=None):
            canvas.update_idletasks()
            bbox = canvas.bbox("all")
            if bbox:
                canvas.configure(scrollregion=bbox)
        
        scrollable_frame.bind("<Configure>", update_scroll_region)
        
        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        def configure_canvas_window(event):
            canvas_width = event.width
            canvas.itemconfig(canvas_window, width=canvas_width)
            canvas.configure(scrollregion=canvas.bbox("all"))
        canvas.bind('<Configure>', configure_canvas_window)
        
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        filter_content = scrollable_frame
        
        # Initialize advanced variables
        self.use_xg_comparison = tk.BooleanVar(value=False)
        self.xg_attr1 = tk.StringVar(value="rating_home")
        self.xg_operation = tk.StringVar(value="-")
        self.xg_attr2 = tk.StringVar(value="rating_away")
        self.xg_comparison_operator = tk.StringVar(value=">=")
        self.xg_comparison_value = tk.StringVar(value="")
        self.use_percentile = tk.BooleanVar(value=False)
        self.percentile_value = tk.StringVar(value="10")
        self.percentile_metric = tk.StringVar(value="chance")
        
        # ---------- ADVANCED xG/RATING COMPARISON ----------
        _cmp_attrs = (
            "rating_home", "rating_away",
            "xg_home_glicko", "xg_away_glicko",
            "rd_home", "rd_away",
            "vol_home", "vol_away",
            "p_home", "p_draw", "p_away",
            "xg_form2_home", "xg_form2_away",
            "form2_avg_xg_home", "form2_avg_xg_away",
            "form2_avg_xga_home", "form2_avg_xga_away",
            "form2_avg_gf_home", "form2_avg_gf_away",
            "form2_avg_ga_home", "form2_avg_ga_away",
            "hometeam_home_xg", "hometeam_home_xga",
            "hometeam_away_xg", "hometeam_away_xga",
            "awayteam_home_xg", "awayteam_home_xga",
            "awayteam_away_xg", "awayteam_away_xga",
            "hometeam_pred_xg", "awayteam_pred_xg",
        )
        xg_comparison_frame = ttk.LabelFrame(
            filter_content, text="🔢 Vergleich / Differenz (Backtest + Upcoming)", padding=15
        )
        xg_comparison_frame.pack(fill=tk.X, pady=(10, 15))
        
        ttk.Checkbutton(
            xg_comparison_frame, text="Vergleichsfilter aktivieren", variable=self.use_xg_comparison
        ).pack(anchor=tk.W, pady=5, padx=10)
        
        attr1_row = ttk.Frame(xg_comparison_frame)
        attr1_row.pack(fill=tk.X, pady=5, padx=10)
        ttk.Label(attr1_row, text="Attribut 1:", width=15, anchor="w").pack(side=tk.LEFT, padx=5)
        attr1_combo = ttk.Combobox(attr1_row, textvariable=self.xg_attr1, state="readonly")
        attr1_combo['values'] = _cmp_attrs
        attr1_combo.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        
        operation_row = ttk.Frame(xg_comparison_frame)
        operation_row.pack(fill=tk.X, pady=5, padx=10)
        ttk.Label(operation_row, text="Operation:", width=15, anchor="w").pack(side=tk.LEFT, padx=5)
        operation_combo = ttk.Combobox(operation_row, textvariable=self.xg_operation, width=10, state="readonly")
        operation_combo['values'] = ("vs", "-", "+", "*", "/")
        operation_combo.pack(side=tk.LEFT, padx=2)
        ttk.Label(
            operation_row,
            text="vs = direkt · sonst Rechnung (Wert optional → 0)",
            foreground="#666",
        ).pack(side=tk.LEFT, padx=8)
        
        attr2_row = ttk.Frame(xg_comparison_frame)
        attr2_row.pack(fill=tk.X, pady=5, padx=10)
        ttk.Label(attr2_row, text="Attribut 2:", width=15, anchor="w").pack(side=tk.LEFT, padx=5)
        attr2_combo = ttk.Combobox(attr2_row, textvariable=self.xg_attr2, state="readonly")
        attr2_combo['values'] = _cmp_attrs
        attr2_combo.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        
        comparison_row = ttk.Frame(xg_comparison_frame)
        comparison_row.pack(fill=tk.X, pady=5, padx=10)
        ttk.Label(comparison_row, text="Vergleich:", width=15, anchor="w").pack(side=tk.LEFT, padx=5)
        comparison_combo = ttk.Combobox(comparison_row, textvariable=self.xg_comparison_operator, width=10, state="readonly")
        comparison_combo['values'] = (">=", "<=", ">", "<", "=", "!=")
        comparison_combo.pack(side=tk.LEFT, padx=2)
        ttk.Label(comparison_row, text="Wert:", width=10, anchor="w").pack(side=tk.LEFT, padx=5)
        ttk.Entry(comparison_row, textvariable=self.xg_comparison_value).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        ttk.Label(
            xg_comparison_frame,
            text="Beispiel: rating_home − rating_away ≥ 50  ·  oder rating_home vs rating_away >",
            foreground="#666",
        ).pack(anchor=tk.W, padx=15, pady=(0, 4))
        
        # ---------- PERCENTILE FILTER ----------
        percentile_frame = ttk.LabelFrame(filter_content, text="📈 Percentile Filter (Top X%)", padding=15)
        percentile_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Checkbutton(percentile_frame, text="Percentile Filter aktivieren", variable=self.use_percentile).pack(anchor=tk.W, pady=5, padx=10)
        
        percentile_row = ttk.Frame(percentile_frame)
        percentile_row.pack(fill=tk.X, pady=5, padx=10)
        ttk.Label(percentile_row, text="Percentile:", width=12, anchor="w").pack(side=tk.LEFT, padx=5)
        percentile_combo = ttk.Combobox(percentile_row, textvariable=self.percentile_value, width=8, state="readonly")
        percentile_combo['values'] = ("1", "5", "10", "15", "20", "25", "30", "50", "75", "90", "95", "99")
        percentile_combo.current(2)
        percentile_combo.pack(side=tk.LEFT, padx=2)

        metric_row = ttk.Frame(percentile_frame)
        metric_row.pack(fill=tk.X, pady=5, padx=10)
        ttk.Label(metric_row, text="Metrik:", width=12, anchor="w").pack(side=tk.LEFT, padx=5)
        percentile_metric_combo = ttk.Combobox(
            metric_row,
            textvariable=self.percentile_metric,
            state="readonly",
            width=24,
        )
        percentile_metric_combo['values'] = (
            "chance", "glicko_rating", "rating_diff", "glicko_diff", "glicko_xg",
            "xg_glicko_home", "xg_glicko_away", "xg_glicko_diff", "xg_glicko_ratio",
            "xg_form2_home", "xg_form2_away", "xg_form2_sum", "xg_form2_diff", "xg_form2_ratio",
            "form2_avg_xg_home", "form2_avg_xg_away",
            "form2_avg_xga_home", "form2_avg_xga_away",
            "hometeam_home_xg", "hometeam_home_xga",
            "awayteam_away_xg", "awayteam_away_xga",
            "hometeam_pred_xg", "awayteam_pred_xg",
            "odds", "xroi_pct", "profit",
        )
        percentile_metric_combo.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        self._make_combobox_dropdown_wide(percentile_metric_combo, min_width=24)

        ttk.Label(
            percentile_frame,
            text="Hinweis: 'profit' ist Look-ahead (nach Ergebnis) — für echte Strategien chance/odds/xg nutzen.",
            foreground="#a05a00",
            wraplength=480,
        ).pack(anchor=tk.W, padx=10, pady=(0, 5))

        # Reihenfolge: Markt → Quoten/Geschlecht → Vergleich → Rest
        for _frm in (
            glicko_frame,
            xg_frame,
            season_n_frame,
            odds_frame,
            chance_frame,
            location_frame,
            games_frame,
            xg_comparison_frame,
            percentile_frame,
        ):
            _frm.pack_forget()
        for _frm in (
            odds_frame,
            location_frame,
            xg_comparison_frame,
            glicko_frame,
            xg_frame,
            season_n_frame,
            chance_frame,
            games_frame,
            percentile_frame,
        ):
            _frm.pack(fill=tk.X, pady=(0, 15) if _frm is not percentile_frame else (0, 10))
    
    def _make_combobox_dropdown_wide(self, combo: ttk.Combobox, min_width: int = 24):
        """Dropdown-Liste mindestens so breit wie die längsten Einträge."""
        try:
            longest = max((len(str(v)) for v in combo.cget("values")), default=min_width)
        except Exception:
            longest = min_width
        width = max(min_width, longest + 2)

        def _on_open(_event=None):
            def _apply():
                try:
                    combo.tk.call("ttk::combobox::PopdownWindow", str(combo))
                    popdown = combo.tk.eval(f"ttk::combobox::PopdownWindow {combo}")
                    combo.tk.call(f"{popdown}.f.l", "configure", "-width", width)
                except Exception:
                    try:
                        # Alternative Pfade je nach Tk-Theme
                        combo.tk.eval(
                            f"set _pd [ttk::combobox::PopdownWindow {combo}]; "
                            f"$_pd.f.l configure -width {width}"
                        )
                    except Exception:
                        pass
            combo.after(1, _apply)

        combo.bind("<ButtonPress-1>", _on_open, add="+")
        combo.bind("<Down>", _on_open, add="+")
    
    def setup_strategy_management(self, parent):
        """Setup strategy management section"""
        # Create scrollable canvas
        canvas = tk.Canvas(parent, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        def update_scroll_region(event=None):
            canvas.update_idletasks()
            bbox = canvas.bbox("all")
            if bbox:
                canvas.configure(scrollregion=bbox)
        
        scrollable_frame.bind("<Configure>", update_scroll_region)
        
        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        def configure_canvas_window(event):
            canvas_width = event.width
            canvas.itemconfig(canvas_window, width=canvas_width)
            canvas.configure(scrollregion=canvas.bbox("all"))
        canvas.bind('<Configure>', configure_canvas_window)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        content = scrollable_frame
        
        # Strategy management frame
        strategy_frame = ttk.LabelFrame(content, text="💾 Strategie Verwaltung", padding=20)
        strategy_frame.pack(fill=tk.X, pady=20, padx=10)
        
        buttons_row = ttk.Frame(strategy_frame)
        buttons_row.pack(fill=tk.X, pady=10, padx=10)
        
        ttk.Button(buttons_row, text="💾 Speichern", command=self.save_strategy).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(buttons_row, text="📂 Laden", command=self.load_strategy_dialog).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(buttons_row, text="⚙️ Verwalten", command=self.manage_strategies).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        self.current_strategy_label = tk.Label(strategy_frame, text="Aktuelle Strategie: Keine", fg="gray", font=("TkDefaultFont", 10))
        self.current_strategy_label.pack(pady=10)
    
    def setup_actions(self, parent):
        """Zusätzliche Aktionen (Hauptbuttons liegen in der Sticky-Leiste)."""
        action_frame = ttk.LabelFrame(parent, text="🚀 Weitere Aktionen", padding=20)
        action_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        ttk.Button(action_frame, text="📊 Strategie Analysieren", command=self.analyze_strategy).pack(fill=tk.X, pady=8, padx=10)
        ttk.Button(action_frame, text="📈 Metric Ranking", command=self.run_metric_ranking).pack(fill=tk.X, pady=8, padx=10)
        ttk.Button(action_frame, text="📦 Bucket Analyse", command=self.run_bucket_analysis).pack(fill=tk.X, pady=8, padx=10)
        ttk.Button(action_frame, text="🔍 Zukünftige Matches prüfen", command=self.check_matches_against_strategies).pack(fill=tk.X, pady=8, padx=10)
        ttk.Button(action_frame, text="📤 CSV Export", command=self.export_results_csv).pack(fill=tk.X, pady=8, padx=10)
        ttk.Button(action_frame, text="📥 Excel Spiele Importieren", command=self.import_excel_games).pack(fill=tk.X, pady=8, padx=10)
        ttk.Button(action_frame, text="🔄 Filter Zurücksetzen", command=self.reset_filters).pack(fill=tk.X, pady=8, padx=10)
        
    
    def setup_results_panel(self, parent):
        """Setup the modern redesigned results and statistics panel"""
        # Modern results frame
        results_frame = ttk.LabelFrame(parent, text="📊 Ergebnisse & Statistiken", padding=5)
        results_frame.pack(fill=tk.BOTH, expand=True, pady=5, padx=5)
        
        # Create modern style for tabs
        style = ttk.Style()
        style.configure("Modern.TNotebook.Tab", padding=[12, 6], font=("Segoe UI", 9))
        
        # Create notebook for tabs (Summary, Chart, Table, Metric Ranking)
        results_notebook = ttk.Notebook(results_frame, style="Modern.TNotebook")
        results_notebook.pack(fill=tk.BOTH, expand=True, pady=5)
        self.results_notebook = results_notebook
        
        # Tab 1: Summary Statistics
        summary_frame = ttk.Frame(results_notebook)
        results_notebook.add(summary_frame, text="Zusammenfassung")
        self.summary_text = tk.Text(summary_frame, height=8, wrap=tk.WORD, font=("Consolas", 10))
        self.summary_text.pack(fill=tk.BOTH, expand=True, pady=1)
        self.summary_text.tag_configure("header", font=("Consolas", 11, "bold"), foreground="#1a365d")
        self.summary_text.tag_configure("section", font=("Consolas", 10, "bold"), foreground="#2c5282")
        self.summary_text.tag_configure("profit_pos", foreground="#166534", font=("Consolas", 10, "bold"))
        self.summary_text.tag_configure("profit_neg", foreground="#991b1b", font=("Consolas", 10, "bold"))
        self.summary_text.tag_configure("muted", foreground="#64748b")
        self.summary_text.tag_configure("warn", foreground="#9a3412")
        self.summary_text.configure(state=tk.DISABLED)
        
        # Tab 2: Profit Chart
        chart_frame = ttk.Frame(results_notebook)
        results_notebook.add(chart_frame, text="Profit Verlauf")
        self.chart_frame = chart_frame  # Store reference for updating chart
        
        # Tab 3: Results table
        table_frame = ttk.Frame(results_notebook)
        results_notebook.add(table_frame, text="Spiele Tabelle")
        
        # Tab 4: Metric Ranking
        ranking_frame = ttk.Frame(results_notebook)
        results_notebook.add(ranking_frame, text="Metric Ranking")
        rank_hint = tk.Label(
            ranking_frame,
            text="Welche Metrics/Schwellen den ROI vs. Baseline am stärksten verbessern.",
            fg="#475569",
            wraplength=420,
            justify=tk.LEFT,
        )
        rank_hint.grid(row=0, column=0, columnspan=2, sticky="w", padx=4, pady=(2, 2))
        self.ranking_baseline_label = tk.Label(ranking_frame, text="Baseline: —", fg="#334155", anchor="w")
        self.ranking_baseline_label.grid(row=1, column=0, columnspan=2, sticky="ew", padx=4, pady=(0, 4))
        rank_scroll_y = ttk.Scrollbar(ranking_frame, orient="vertical")
        rank_scroll_x = ttk.Scrollbar(ranking_frame, orient="horizontal")
        rank_cols = (
            "rank", "metric", "rule", "condition", "n", "wr", "profit", "roi",
            "roi_delta", "profit_delta", "max_lose", "coverage",
        )
        self.ranking_tree = ttk.Treeview(
            ranking_frame,
            columns=rank_cols,
            show="headings",
            yscrollcommand=rank_scroll_y.set,
            xscrollcommand=rank_scroll_x.set,
            height=12,
        )
        headings = {
            "rank": "#",
            "metric": "Metric",
            "rule": "Regel",
            "condition": "Bedingung",
            "n": "n",
            "wr": "WR% (Trefferquote)",
            "profit": "Profit",
            "roi": "ROI%",
            "roi_delta": "Δ ROI",
            "profit_delta": "Δ Profit",
            "max_lose": "MaxLose",
            "coverage": "Anteil%",
        }
        widths = {
            "rank": 36, "metric": 110, "rule": 130, "condition": 140, "n": 50,
            "wr": 110, "profit": 70, "roi": 65, "roi_delta": 70, "profit_delta": 75,
            "max_lose": 65, "coverage": 65,
        }
        for col in rank_cols:
            self.ranking_tree.heading(col, text=headings[col])
            self.ranking_tree.column(col, width=widths[col], anchor="center" if col != "condition" else "w")
        self.ranking_tree.tag_configure("pos", background="#dcfce7")
        self.ranking_tree.tag_configure("neg", background="#fee2e2")
        rank_scroll_y.config(command=self.ranking_tree.yview)
        rank_scroll_x.config(command=self.ranking_tree.xview)
        self.ranking_tree.grid(row=2, column=0, sticky="nsew")
        rank_scroll_y.grid(row=2, column=1, sticky="ns")
        rank_scroll_x.grid(row=3, column=0, sticky="ew")
        ranking_frame.grid_rowconfigure(2, weight=1)
        ranking_frame.grid_columnconfigure(0, weight=1)
        self._setup_ranking_tooltips()

        # Tab 5: Bucket Analyse (Range in Steps zerlegen)
        bucket_frame = ttk.Frame(results_notebook)
        results_notebook.add(bucket_frame, text="Bucket Analyse")
        self._setup_bucket_panel(bucket_frame)
        
        # Scrollbars
        scrollbar_y = ttk.Scrollbar(table_frame, orient='vertical')
        scrollbar_x = ttk.Scrollbar(table_frame, orient='horizontal')
        
        # Treeview for results with larger font - Glicko-Daten nach vorne verschoben
        columns = (
            "game_id", "match_date", "date", "home", "away",
            "season_n_h", "season_n_a",
            "rating_h", "rating_a", "xg_glicko_home", "xg_glicko_away",
            "home_score", "away_score", "result", "market", "profit",
            "home_quote", "draw_quote", "away_quote", "over_25_quote", "under_25_quote",
            "home_profit", "draw_profit", "away_profit", "over_25_profit", "under_25_profit",
            "chance_home", "chance_draw", "chance_away", "chance_over", "chance_under",
            "xg_home", "xg_away",
        )
        
        # Configure style for larger font
        style = ttk.Style()
        style.configure("Treeview", font=("Segoe UI", 10), rowheight=25)
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
        
        self.results_tree = ttk.Treeview(table_frame, columns=columns, show='headings', 
                                         yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)
        
        # Configure tags for profit coloring
        self.results_tree.tag_configure('profit_positive', background='#90EE90')  # Hellgrün
        self.results_tree.tag_configure('profit_negative', background='#FFB6C1')  # Hellrot
        
        # Configure columns - Glicko-Daten nach vorne verschoben
        self.results_tree.heading('game_id', text='ID')
        self.results_tree.heading('match_date', text='Spieldatum')
        self.results_tree.heading('date', text='Datum')
        self.results_tree.heading('home', text='Home')
        self.results_tree.heading('away', text='Away')
        self.results_tree.heading('season_n_h', text='Saison# H')
        self.results_tree.heading('season_n_a', text='Saison# A')
        self.results_tree.heading('rating_h', text='Rating H')
        self.results_tree.heading('rating_a', text='Rating A')
        self.results_tree.heading('xg_glicko_home', text='xG Glicko H')
        self.results_tree.heading('xg_glicko_away', text='xG Glicko A')
        self.results_tree.heading('home_score', text='Home Score')
        self.results_tree.heading('away_score', text='Away Score')
        self.results_tree.heading('result', text='Ergebnis')
        self.results_tree.heading('market', text='Markt')
        self.results_tree.heading('profit', text='Profit')
        self.results_tree.heading('home_quote', text='Quote H')
        self.results_tree.heading('draw_quote', text='Quote D')
        self.results_tree.heading('away_quote', text='Quote A')
        self.results_tree.heading('over_25_quote', text='Quote O2.5')
        self.results_tree.heading('under_25_quote', text='Quote U2.5')
        self.results_tree.heading('home_profit', text='Home Profit')
        self.results_tree.heading('draw_profit', text='Draw Profit')
        self.results_tree.heading('away_profit', text='Away Profit')
        self.results_tree.heading('over_25_profit', text='Over 2.5 Profit')
        self.results_tree.heading('under_25_profit', text='Under 2.5 Profit')
        self.results_tree.heading('chance_home', text='Ch. Home')
        self.results_tree.heading('chance_draw', text='Ch. Draw')
        self.results_tree.heading('chance_away', text='Ch. Away')
        self.results_tree.heading('chance_over', text='Ch. Over')
        self.results_tree.heading('chance_under', text='Ch. Under')
        self.results_tree.heading('xg_home', text='xG Home')
        self.results_tree.heading('xg_away', text='xG Away')
        
        # Spaltenbreiten angepasst für größere Schrift - Glicko-Daten nach vorne
        self.results_tree.column('game_id', width=60)
        self.results_tree.column('match_date', width=120)
        self.results_tree.column('date', width=100)
        self.results_tree.column('home', width=80)
        self.results_tree.column('away', width=80)
        self.results_tree.column('season_n_h', width=70)
        self.results_tree.column('season_n_a', width=70)
        self.results_tree.column('rating_h', width=70)
        self.results_tree.column('rating_a', width=70)
        self.results_tree.column('xg_glicko_home', width=80)
        self.results_tree.column('xg_glicko_away', width=80)
        self.results_tree.column('home_score', width=60)
        self.results_tree.column('away_score', width=60)
        self.results_tree.column('result', width=70)
        self.results_tree.column('market', width=60)
        self.results_tree.column('profit', width=60)
        self.results_tree.column('home_quote', width=60)
        self.results_tree.column('draw_quote', width=60)
        self.results_tree.column('away_quote', width=60)
        self.results_tree.column('over_25_quote', width=70)
        self.results_tree.column('under_25_quote', width=70)
        self.results_tree.column('home_profit', width=70)
        self.results_tree.column('draw_profit', width=70)
        self.results_tree.column('away_profit', width=70)
        self.results_tree.column('over_25_profit', width=75)
        self.results_tree.column('under_25_profit', width=75)
        self.results_tree.column('chance_home', width=50)
        self.results_tree.column('chance_draw', width=50)
        self.results_tree.column('chance_away', width=50)
        self.results_tree.column('chance_over', width=50)
        self.results_tree.column('chance_under', width=50)
        self.results_tree.column('xg_home', width=60)
        self.results_tree.column('xg_away', width=60)
        
        scrollbar_y.config(command=self.results_tree.yview)
        scrollbar_x.config(command=self.results_tree.xview)
        
        # Use grid layout for proper scrollbar positioning
        self.results_tree.grid(row=0, column=0, sticky='nsew')
        scrollbar_y.grid(row=0, column=1, sticky='ns')
        scrollbar_x.grid(row=1, column=0, sticky='ew')
        
        # Configure grid weights for proper resizing
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)
        
        # Bind double-click to show analysis
        self.results_tree.bind("<Double-1>", self._on_result_double_click)
        
        # Tag configuration for positive/negative profits
        # Configure tags for profit coloring - only green for positive profits
        self.results_tree.tag_configure('profit_positive', background='#90EE90')  # Light green for positive
        self.results_tree.tag_configure('profit_negative', background='')  # Default background for negative
    
    def reset_filters(self):
        """Reset all filters to default values"""
        self.market_home.set(False)
        self.market_draw.set(False)
        self.market_away.set(False)
        self.market_over.set(False)
        self.market_under.set(False)
        self.market_over_35.set(False)
        self.market_under_35.set(False)
        self.market_over_45.set(False)
        self.market_under_45.set(False)
        self.glicko_home_min.set("")
        self.glicko_home_max.set("")
        self.glicko_away_min.set("")
        self.glicko_away_max.set("")
        self.glicko_rd_home_min.set("")
        self.glicko_rd_home_max.set("")
        self.glicko_rd_away_min.set("")
        self.glicko_rd_away_max.set("")
        self.glicko_vol_home_min.set("")
        self.glicko_vol_home_max.set("")
        self.glicko_vol_away_min.set("")
        self.glicko_vol_away_max.set("")
        self.glicko_p_home_min.set("")
        self.glicko_p_home_max.set("")
        self.glicko_p_draw_min.set("")
        self.glicko_p_draw_max.set("")
        self.glicko_p_away_min.set("")
        self.glicko_p_away_max.set("")
        self.xg_glicko_home_min.set("")
        self.xg_glicko_home_max.set("")
        self.xg_glicko_away_min.set("")
        self.xg_glicko_away_max.set("")
        self.season_games_home_min.set("")
        self.season_games_home_max.set("")
        self.season_games_away_min.set("")
        self.season_games_away_max.set("")
        self.use_xg_comparison.set(False)
        self.xg_attr1.set("rating_home")
        self.xg_operation.set("-")
        self.xg_attr2.set("rating_away")
        self.xg_comparison_operator.set(">=")
        self.xg_comparison_value.set("")
        self.odds_home_min.set("")
        self.odds_home_max.set("")
        self.odds_draw_min.set("")
        self.odds_draw_max.set("")
        self.odds_away_min.set("")
        self.odds_away_max.set("")
        self.odds_over_min.set("")
        self.odds_over_max.set("")
        self.odds_under_min.set("")
        self.odds_under_max.set("")
        self.odds_over35_min.set("")
        self.odds_over35_max.set("")
        self.odds_under35_min.set("")
        self.odds_under35_max.set("")
        self.odds_over45_min.set("")
        self.odds_over45_max.set("")
        self.odds_under45_min.set("")
        self.odds_under45_max.set("")
        self.odds_type.set("closing")
        self.date_from.set("")
        self.date_to.set("")
        self.chance_min.set("")
        self.chance_max.set("")
        self.country_filter.set("")
        self.league_filter.set("")
        self.gender_filter.set("men")
        self.min_games_count.set("5")
        self.use_percentile.set(False)
        self.percentile_value.set("10")
        self.percentile_metric.set("chance")
    
    def get_percentile_threshold(self, values: List[float], percentile: float) -> float:
        """Calculate percentile threshold"""
        if not values or len(values) == 0:
            return 0.0
        filtered_values = [v for v in values if v is not None]
        if len(filtered_values) == 0:
            return 0.0
        
        if HAS_NUMPY:
            values_array = np.array(filtered_values)
            return float(np.percentile(values_array, 100 - percentile))
        else:
            # Manual percentile calculation without numpy
            sorted_values = sorted(filtered_values, reverse=True)
            index = int(len(sorted_values) * (percentile / 100.0))
            if index >= len(sorted_values):
                index = len(sorted_values) - 1
            return sorted_values[index] if index >= 0 else sorted_values[0]
    
    def _on_result_double_click(self, event):
        """Handle double-click on results tree to show analysis"""
        # Get item at click position
        item = self.results_tree.identify_row(event.y)
        if not item:
            return
        
        # Select the item
        self.results_tree.selection_set(item)
        
        # Get values from the item
        values = self.results_tree.item(item, 'values')
        
        if not values or len(values) == 0:
            print(f"[DEBUG] Keine Werte für Item: {item}")
            return
        
        # Extract game_id (first column)
        try:
            game_id = int(values[0])
            print(f"[DEBUG] Doppelklick auf Game ID: {game_id}")
        except (ValueError, IndexError, TypeError) as e:
            print(f"[DEBUG] Fehler beim Extrahieren der Game ID: {e}, Werte: {values}")
            return
        
        # Show analysis window
        self._show_match_analysis(game_id)
    
    def _show_match_analysis(self, game_id):
        """Show match analysis - Analytics-Tab wie bei Today's Matches."""
        print(f"[DEBUG] Zeige Analyse für Game ID: {game_id}")
        try:
            analytics = self.services.get('analytics_tab') if isinstance(self.services, dict) else None
            notebook = self.services.get('main_notebook') if isinstance(self.services, dict) else None

            if analytics is None or notebook is None:
                # Fallback: Ancestors / Geschwister-Tabs suchen
                parent = self.master
                while parent is not None:
                    if hasattr(parent, 'analytics_tab') and hasattr(parent, 'notebook'):
                        analytics = parent.analytics_tab
                        notebook = parent.notebook
                        break
                    # Notebook selbst: Geschwister-Tabs prüfen
                    if hasattr(parent, 'tabs') and hasattr(parent, 'nametowidget'):
                        try:
                            for tab_id in parent.tabs():
                                w = parent.nametowidget(tab_id)
                                if hasattr(w, 'load_match_by_id'):
                                    analytics = w
                                    notebook = parent
                                    break
                        except Exception:
                            pass
                        if analytics is not None:
                            break
                    parent = getattr(parent, 'master', None)

            if analytics is not None and hasattr(analytics, 'load_match_by_id'):
                if notebook is not None:
                    try:
                        notebook.select(analytics)
                    except Exception:
                        pass
                # Upcoming oft nur in upcoming_games → DB zuerst, sonst API
                analytics.load_match_by_id(game_id, use_database=True)
                return

            print(f"[DEBUG] Analytics Tab nicht gefunden, zeige Dialog für Game ID: {game_id}")
            self._show_simple_analysis(game_id)
        except Exception as e:
            print(f"[ERROR] Fehler beim Anzeigen der Analyse: {e}")
            import traceback
            traceback.print_exc()
            self._show_simple_analysis(game_id)
    
    def _show_simple_analysis(self, game_id):
        """Show simple analysis in a dialog window"""
        import sqlite3
        from tkinter import Toplevel, scrolledtext
        
        dialog = Toplevel(self)
        dialog.title(f"Match Analyse - ID: {game_id}")
        dialog.geometry("1100x750")
        dialog.minsize(800, 500)
        dialog.resizable(True, True)
        
        # Header with game ID prominently displayed
        header_frame = tk.Frame(dialog, bg="#2c3e50", height=50)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        header_frame.pack_propagate(False)
        
        header_label = tk.Label(header_frame, 
                               text=f"🎯 MATCH ANALYSE - GAME ID: {game_id}", 
                               font=("Segoe UI", 14, "bold"),
                               bg="#2c3e50", fg="white")
        header_label.pack(pady=12)
        
        # Create text widget with scrollbar
        text_widget = scrolledtext.ScrolledText(dialog, wrap=tk.WORD, font=("Courier", 10))
        text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        try:
            # Load match data from database
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get match details
            query = """
                SELECT 
                    g.game_id, g.date, g.country_name, g.league_name,
                    g.home_team_name, g.away_team_name,
                    g.home_ft_result, g.away_ft_result,
                    g.home_rating, g.away_rating,
                    g.xg_home, g.xg_away, g.xg_glicko_home, g.xg_glicko_away,
                    g.chance_home_win, g.chance_home_draw, g.chance_home_lose,
                    g.chance_home_over_25, g.chance_home_under_25,
                    o.odd_home, o.odd_draw, o.odd_away, o.odd_over_25, o.odd_under_25
                FROM game_details_view g
                LEFT JOIN game_odds_pivoted o ON g.game_id = o.game_id
                WHERE g.game_id = ?
            """
            
            cursor.execute(query, (game_id,))
            row = cursor.fetchone()
            # Upcoming-Spiele liegen oft nicht in game_details_view
            if not row:
                cursor.execute(
                    """
                    SELECT u.id AS game_id, u.date, u.country_name, u.league_name,
                           u.home_team_name, u.away_team_name,
                           u.home_ft_result, u.away_ft_result,
                           g.home_rating, g.away_rating,
                           g.home_xg AS xg_glicko_home, g.away_xg AS xg_glicko_away,
                           NULL AS xg_home, NULL AS xg_away,
                           NULL AS chance_home_win, NULL AS chance_home_draw, NULL AS chance_home_lose,
                           NULL AS chance_home_over_25, NULL AS chance_home_under_25,
                           o.odd_home, o.odd_draw, o.odd_away, o.odd_over_25, o.odd_under_25
                    FROM upcoming_games u
                    LEFT JOIN game_glicko g ON g.game_id = u.id
                    LEFT JOIN game_odds_pivoted o ON o.game_id = u.id
                    WHERE u.id = ?
                    """,
                    (game_id,),
                )
                row = cursor.fetchone()

            if row:
                row = dict(row)
                # Format analysis text with safe value handling
                def safe_format(value, format_str, default='N/A'):
                    try:
                        if value is None:
                            return default
                        return format_str.format(value)
                    except (ValueError, TypeError):
                        return default
                
                analysis = f"""
═══════════════════════════════════════════════════════
MATCH ANALYSE - GAME ID: {game_id}
═══════════════════════════════════════════════════════

GAME ID: {game_id}

SPIEL INFORMATIONEN:
  Datum: {row.get('date', 'N/A')}
  Land: {row.get('country_name', 'N/A')}
  Liga: {row.get('league_name', 'N/A')}
  Home: {row.get('home_team_name', 'N/A')}
  Away: {row.get('away_team_name', 'N/A')}
  Ergebnis: {row.get('home_ft_result') or '-'} - {row.get('away_ft_result') or '-'}

GLICKO RATINGS:
  Home Rating: {safe_format(row.get('home_rating'), '{:.2f}')}
  Away Rating: {safe_format(row.get('away_rating'), '{:.2f}')}

xG STATISTIKEN:
  xG Home: {safe_format(row.get('xg_home'), '{:.2f}')}
  xG Away: {safe_format(row.get('xg_away'), '{:.2f}')}
  xG Glicko Home: {safe_format(row.get('xg_glicko_home'), '{:.2f}')}
  xG Glicko Away: {safe_format(row.get('xg_glicko_away'), '{:.2f}')}

GEWINNWAHRSCHEINLICHKEITEN:
  Home Win: {safe_format(row.get('chance_home_win'), '{:.2%}')}
  Draw: {safe_format(row.get('chance_home_draw'), '{:.2%}')}
  Away Win: {safe_format(row.get('chance_home_lose'), '{:.2%}')}
  Over 2.5: {safe_format(row.get('chance_home_over_25'), '{:.2%}')}
  Under 2.5: {safe_format(row.get('chance_home_under_25'), '{:.2%}')}

QUOTEN:
  Home: {safe_format(row.get('odd_home'), '{:.2f}')}
  Draw: {safe_format(row.get('odd_draw'), '{:.2f}')}
  Away: {safe_format(row.get('odd_away'), '{:.2f}')}
  Over 2.5: {safe_format(row.get('odd_over_25'), '{:.2f}')}
  Under 2.5: {safe_format(row.get('odd_under_25'), '{:.2f}')}

═══════════════════════════════════════════════════════
"""
                text_widget.insert(1.0, analysis)
                text_widget.config(state=tk.DISABLED)  # Make read-only
            else:
                text_widget.insert(1.0, f"Keine Daten für Match ID {game_id} gefunden.")
            
            conn.close()
        except Exception as e:
            text_widget.insert(1.0, f"Fehler beim Laden der Daten: {e}")
    
    def analyze_strategy(self):
        """Analyze strategy based on filters"""
        try:
            filters = self.get_current_filters()
            markets = strat.selected_markets_from_filters(filters)
            if not markets:
                messagebox.showwarning("Warnung", "Bitte wähle mindestens einen Markt aus!")
                return

            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Saison-Spielnr. = 1 + Anzahl früherer fertiger Spiele des Teams in Liga+Season
            home_season_n_sql = """
                (1 + (
                    SELECT COUNT(*) FROM games prev
                    WHERE prev.league_id = g.league_id
                      AND prev.season_year = g.season_year
                      AND prev.home_ft_result IS NOT NULL
                      AND prev.away_ft_result IS NOT NULL
                      AND prev.date < g.date
                      AND (
                        (g.home_team_id IS NOT NULL AND (prev.home_team_id = g.home_team_id OR prev.away_team_id = g.home_team_id))
                        OR (g.home_team_id IS NULL AND (prev.home_team_name = g.home_team_name OR prev.away_team_name = g.home_team_name))
                      )
                ))
            """
            away_season_n_sql = """
                (1 + (
                    SELECT COUNT(*) FROM games prev
                    WHERE prev.league_id = g.league_id
                      AND prev.season_year = g.season_year
                      AND prev.home_ft_result IS NOT NULL
                      AND prev.away_ft_result IS NOT NULL
                      AND prev.date < g.date
                      AND (
                        (g.away_team_id IS NOT NULL AND (prev.home_team_id = g.away_team_id OR prev.away_team_id = g.away_team_id))
                        OR (g.away_team_id IS NULL AND (prev.home_team_name = g.away_team_name OR prev.away_team_name = g.away_team_name))
                      )
                ))
            """

            query = f"""
                SELECT
                    g.game_id, g.date, g.country_name, g.league_name,
                    g.home_team_name, g.away_team_name,
                    g.home_ft_result, g.away_ft_result,
                    g.home_rating, g.away_rating,
                    g.home_rd, g.away_rd,
                    g.home_volatility, g.away_volatility,
                    g.home_win_probability, g.away_win_probability, g.draw_probability,
                    g.xg_home, g.xg_away, g.xg_glicko_home, g.xg_glicko_away,
                    g.chance_home_win, g.chance_home_draw, g.chance_home_lose,
                    g.chance_home_over_25, g.chance_home_under_25,
                    g.chance_home_over_35, g.chance_home_under_35,
                    g.chance_home_over_45, g.chance_home_under_45,
                    g.games_count_home_win,
                    {home_season_n_sql} AS home_season_n,
                    {away_season_n_sql} AS away_season_n,
                    o.odd_home, o.odd_draw, o.odd_away,
                    o.odd_over_25, o.odd_under_25,
                    o.odd_over_35, o.odd_under_35,
                    o.odd_over_45, o.odd_under_45,
                    o.odd_open_home, o.odd_open_draw, o.odd_open_away,
                    o.odd_open_over_25, o.odd_open_under_25,
                    o.odd_open_over_35, o.odd_open_under_35,
                    o.odd_open_over_45, o.odd_open_under_45
                FROM game_details_view g
                LEFT JOIN game_odds_pivoted o ON g.game_id = o.game_id
                WHERE g.home_ft_result IS NOT NULL AND g.away_ft_result IS NOT NULL
            """
            params = []

            if filters.get('glicko_home_min') or filters.get('glicko_home_max') or filters.get('glicko_away_min') or filters.get('glicko_away_max'):
                query += " AND home_rating IS NOT NULL AND away_rating IS NOT NULL"
            if filters.get('glicko_home_min'):
                query += " AND home_rating >= ?"
                params.append(float(filters['glicko_home_min']))
            if filters.get('glicko_home_max'):
                query += " AND home_rating <= ?"
                params.append(float(filters['glicko_home_max']))
            if filters.get('glicko_away_min'):
                query += " AND away_rating >= ?"
                params.append(float(filters['glicko_away_min']))
            if filters.get('glicko_away_max'):
                query += " AND away_rating <= ?"
                params.append(float(filters['glicko_away_max']))

            rd_keys = (
                'glicko_rd_home_min', 'glicko_rd_home_max',
                'glicko_rd_away_min', 'glicko_rd_away_max',
            )
            if any(filters.get(k) for k in rd_keys):
                query += " AND home_rd IS NOT NULL AND away_rd IS NOT NULL"
            for col, kmin, kmax in (
                ('home_rd', 'glicko_rd_home_min', 'glicko_rd_home_max'),
                ('away_rd', 'glicko_rd_away_min', 'glicko_rd_away_max'),
            ):
                if filters.get(kmin):
                    query += f" AND {col} >= ?"
                    params.append(float(filters[kmin]))
                if filters.get(kmax):
                    query += f" AND {col} <= ?"
                    params.append(float(filters[kmax]))

            vol_keys = (
                'glicko_vol_home_min', 'glicko_vol_home_max',
                'glicko_vol_away_min', 'glicko_vol_away_max',
            )
            if any(filters.get(k) for k in vol_keys):
                query += " AND home_volatility IS NOT NULL AND away_volatility IS NOT NULL"
            for col, kmin, kmax in (
                ('home_volatility', 'glicko_vol_home_min', 'glicko_vol_home_max'),
                ('away_volatility', 'glicko_vol_away_min', 'glicko_vol_away_max'),
            ):
                if filters.get(kmin):
                    query += f" AND {col} >= ?"
                    params.append(float(filters[kmin]))
                if filters.get(kmax):
                    query += f" AND {col} <= ?"
                    params.append(float(filters[kmax]))

            def _prob_bound(col, kmin, kmax):
                nonlocal query, params
                if filters.get(kmin):
                    v = float(filters[kmin])
                    if v > 1.0:
                        v = v / 100.0
                    query += f" AND {col} IS NOT NULL AND {col} >= ?"
                    params.append(v)
                if filters.get(kmax):
                    v = float(filters[kmax])
                    if v > 1.0:
                        v = v / 100.0
                    query += f" AND {col} IS NOT NULL AND {col} <= ?"
                    params.append(v)

            _prob_bound('home_win_probability', 'glicko_p_home_min', 'glicko_p_home_max')
            _prob_bound('draw_probability', 'glicko_p_draw_min', 'glicko_p_draw_max')
            _prob_bound('away_win_probability', 'glicko_p_away_min', 'glicko_p_away_max')

            xg_keys = (
                'xg_glicko_home_min', 'xg_glicko_home_max',
                'xg_glicko_away_min', 'xg_glicko_away_max',
            )
            if any(filters.get(k) for k in xg_keys) or filters.get('use_xg_comparison'):
                query += " AND xg_glicko_home IS NOT NULL AND xg_glicko_away IS NOT NULL"
            if filters.get('xg_glicko_home_min'):
                query += " AND xg_glicko_home >= ?"
                params.append(float(filters['xg_glicko_home_min']))
            if filters.get('xg_glicko_home_max'):
                query += " AND xg_glicko_home <= ?"
                params.append(float(filters['xg_glicko_home_max']))
            if filters.get('xg_glicko_away_min'):
                query += " AND xg_glicko_away >= ?"
                params.append(float(filters['xg_glicko_away_min']))
            if filters.get('xg_glicko_away_max'):
                query += " AND xg_glicko_away <= ?"
                params.append(float(filters['xg_glicko_away_max']))

            if filters.get('use_xg_comparison'):
                query += " AND home_rating IS NOT NULL AND away_rating IS NOT NULL"
            if filters.get('country_filter'):
                query += " AND country_name LIKE ?"
                params.append(f"%{filters['country_filter']}%")
            if filters.get('league_filter'):
                query += " AND league_name LIKE ?"
                params.append(f"%{filters['league_filter']}%")
            if filters.get('date_from'):
                query += " AND date(g.date) >= date(?)"
                params.append(filters['date_from'])
            if filters.get('date_to'):
                query += " AND date(g.date) <= date(?)"
                params.append(filters['date_to'])
            if filters.get('min_games_count'):
                try:
                    mg = float(filters['min_games_count'])
                    if mg > 0:
                        query += " AND games_count_home_win >= ?"
                        params.append(mg)
                except (TypeError, ValueError):
                    pass

            def _add_season_bound(sql_expr, key_min, key_max):
                nonlocal query, params
                if filters.get(key_min):
                    query += f" AND {sql_expr} >= ?"
                    params.append(float(filters[key_min]))
                if filters.get(key_max):
                    query += f" AND {sql_expr} <= ?"
                    params.append(float(filters[key_max]))

            _add_season_bound(home_season_n_sql, 'season_games_home_min', 'season_games_home_max')
            _add_season_bound(away_season_n_sql, 'season_games_away_min', 'season_games_away_max')

            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()

            if not rows:
                messagebox.showinfo("Info", "Keine Spiele gefunden, die den Filtern entsprechen.")
                return

            def get_row_value(row, key, default=None):
                try:
                    return row[key] if key in row.keys() else default
                except (KeyError, TypeError):
                    return default

            def get_result_text(home_score, away_score):
                if home_score is None or away_score is None:
                    return "-"
                try:
                    h, a = int(home_score), int(away_score)
                    if h > a:
                        return "Home Win"
                    if a > h:
                        return "Away Win"
                    return "Draw"
                except (ValueError, TypeError):
                    return "-"

            def fmt_date(match_date):
                if not match_date:
                    return match_date
                try:
                    if isinstance(match_date, str):
                        raw = match_date.split()[0] if ' ' in match_date else match_date
                        for fmt in ('%Y-%m-%d', '%d.%m.%Y'):
                            try:
                                return datetime.strptime(raw[:10], fmt).strftime('%d.%m.%Y')
                            except Exception:
                                continue
                except Exception:
                    pass
                return match_date

            odds_type = filters.get('odds_type') or 'closing'
            chance_by_market = {
                'Home': 'chance_home_win',
                'Draw': 'chance_home_draw',
                'Away': 'chance_home_lose',
                'Over 2.5': 'chance_home_over_25',
                'Under 2.5': 'chance_home_under_25',
                'Over 3.5': 'chance_home_over_35',
                'Under 3.5': 'chance_home_under_35',
                'Over 4.5': 'chance_home_over_45',
                'Under 4.5': 'chance_home_under_45',
            }

            results = []
            for row in rows:
                row_dict = {k: get_row_value(row, k) for k in row.keys()}
                home_score = row_dict.get('home_ft_result')
                away_score = row_dict.get('away_ft_result')
                odd_home = strat.pick_odds(row_dict, 'Home', odds_type)
                odd_draw = strat.pick_odds(row_dict, 'Draw', odds_type)
                odd_away = strat.pick_odds(row_dict, 'Away', odds_type)
                odd_over_25 = strat.pick_odds(row_dict, 'Over 2.5', odds_type)
                odd_under_25 = strat.pick_odds(row_dict, 'Under 2.5', odds_type)

                base_result = {
                    'game_id': row_dict.get('game_id'),
                    'date': row_dict.get('date'),
                    'match_date': fmt_date(row_dict.get('date')) or row_dict.get('date'),
                    'home': row_dict.get('home_team_name'),
                    'away': row_dict.get('away_team_name'),
                    'country': row_dict.get('country_name'),
                    'league': row_dict.get('league_name'),
                    'home_score': home_score if home_score is not None else 0,
                    'away_score': away_score if away_score is not None else 0,
                    'result': get_result_text(home_score, away_score),
                    'home_quote': odd_home,
                    'draw_quote': odd_draw,
                    'away_quote': odd_away,
                    'over_25_quote': odd_over_25,
                    'under_25_quote': odd_under_25,
                    'home_profit': strat.settle_market('Home', home_score, away_score, odd_home),
                    'draw_profit': strat.settle_market('Draw', home_score, away_score, odd_draw),
                    'away_profit': strat.settle_market('Away', home_score, away_score, odd_away),
                    'over_25_profit': strat.settle_market('Over 2.5', home_score, away_score, odd_over_25),
                    'under_25_profit': strat.settle_market('Under 2.5', home_score, away_score, odd_under_25),
                    'chance_home': row_dict.get('chance_home_win'),
                    'chance_draw': row_dict.get('chance_home_draw'),
                    'chance_away': row_dict.get('chance_home_lose'),
                    'chance_over': row_dict.get('chance_home_over_25'),
                    'chance_under': row_dict.get('chance_home_under_25'),
                    'rating_h': row_dict.get('home_rating'),
                    'rating_a': row_dict.get('away_rating'),
                    'rd_h': row_dict.get('home_rd'),
                    'rd_a': row_dict.get('away_rd'),
                    'vol_h': row_dict.get('home_volatility'),
                    'vol_a': row_dict.get('away_volatility'),
                    'p_home': row_dict.get('home_win_probability'),
                    'p_draw': row_dict.get('draw_probability'),
                    'p_away': row_dict.get('away_win_probability'),
                    'xg_h': row_dict.get('xg_home') or row_dict.get('xg_glicko_home'),
                    'xg_a': row_dict.get('xg_away') or row_dict.get('xg_glicko_away'),
                    'xg_glicko_h': row_dict.get('xg_glicko_home'),
                    'xg_glicko_a': row_dict.get('xg_glicko_away'),
                    'games_count': row_dict.get('games_count_home_win'),
                    'home_season_n': row_dict.get('home_season_n'),
                    'away_season_n': row_dict.get('away_season_n'),
                }

                xg_ctx = {
                    'xg_h': base_result['xg_h'],
                    'xg_a': base_result['xg_a'],
                    'xg_glicko_h': base_result['xg_glicko_h'],
                    'xg_glicko_a': base_result['xg_glicko_a'],
                    'rating_h': base_result['rating_h'],
                    'rating_a': base_result['rating_a'],
                    'rd_h': base_result['rd_h'],
                    'rd_a': base_result['rd_a'],
                    'vol_h': base_result['vol_h'],
                    'vol_a': base_result['vol_a'],
                    'p_home': base_result['p_home'],
                    'p_draw': base_result['p_draw'],
                    'p_away': base_result['p_away'],
                }

                for market in markets:
                    odds = strat.pick_odds(row_dict, market, odds_type)
                    if odds is None or odds <= 1.0:
                        continue
                    profit = strat.settle_market(market, home_score, away_score, odds)
                    if profit is None:
                        continue
                    chance = row_dict.get(chance_by_market.get(market, ''), None)
                    opening = strat.pick_odds(row_dict, market, 'opening')
                    closing = strat.pick_odds(row_dict, market, 'closing')
                    if not strat.match_prematch_filters(
                        filters,
                        market=market,
                        odds=odds,
                        chance=chance,
                        rating_h=base_result['rating_h'],
                        rating_a=base_result['rating_a'],
                        country=base_result['country'],
                        league=base_result['league'],
                        games_count=base_result['games_count'],
                        xg_ctx=xg_ctx,
                        home_season_n=base_result['home_season_n'],
                        away_season_n=base_result['away_season_n'],
                    ):
                        continue
                    results.append({
                        **base_result,
                        'market': market,
                        'profit': profit,
                        'chance': chance,
                        'odds': odds,
                        'odds_opening': opening,
                        'odds_closing': closing,
                        'xroi_pct': strat.compute_xroi_pct(opening, closing),
                    })

            if filters.get('use_percentile') and results:
                try:
                    pct = float(filters.get('percentile_value') or 10)
                except (TypeError, ValueError):
                    pct = 10.0
                metric = filters.get('percentile_metric') or 'chance'
                results = strat.apply_percentile_filter(results, pct, metric)
                self._percentile_lookahead = (metric == 'profit')
            else:
                self._percentile_lookahead = False

            self.strategy_results = results
            self.display_results(results)
            self.update_profit_chart(results)

            if (filters.get("odds_type") or "closing") == "opening" and not results:
                messagebox.showinfo(
                    "Opening-Odds fehlen",
                    "Keine Treffer mit Opening-Quoten.\n\n"
                    "In der DB sind Opening-Werte oft noch leer.\n"
                    "Bitte zuerst „Opening-Odds laden (Pinnacle)“ nutzen,\n"
                    "danach die Analyse erneut starten.",
                )
            elif results:
                # Nach Backtest automatisch passende bevorstehende Spiele
                try:
                    self.after(200, self.check_matches_against_strategies)
                except Exception as e2:
                    print(f"[WARNING] Upcoming nach Analyse: {e2}")

        except Exception as e:
            messagebox.showerror("Fehler", f"Fehler bei der Strategie-Analyse: {e}")
            import traceback
            traceback.print_exc()

    def load_opening_odds_for_strategies(self):
        """Opening-Odds von der API nachladen und in opening_value speichern (Strategien)."""
        try:
            from database import DatabaseManager
            from api.sstats_client import SStatsClient
            from config import config as cfg
            import threading

            limit = simpledialog.askinteger(
                "Opening-Odds laden",
                "Wie viele Spiele maximal nachladen?\n"
                "(fehlen Opening, haben aber Closing; Pinnacle)",
                initialvalue=200,
                minvalue=1,
                maxvalue=5000,
                parent=self,
            )
            if not limit:
                return

            db = DatabaseManager(self.db_path)
            conn = db.get_connection()
            # View aktualisieren (inkl. Open 3.5/4.5)
            try:
                from pathlib import Path
                view_sql = Path(__file__).resolve().parents[2] / "database" / "create_odds_view.sql"
                if view_sql.exists():
                    conn.executescript(view_sql.read_text(encoding="utf-8"))
                    conn.commit()
            except Exception:
                pass

            game_ids = strat.games_missing_opening_odds(conn, limit=limit)
            if not game_ids:
                messagebox.showinfo("Info", "Alle vorhandenen Closing-Quoten haben bereits Opening — oder keine Odds in DB.")
                return

            client = SStatsClient(base_url=cfg.BASE_URL, api_key=getattr(cfg, "API_KEY", None))
            est_min = len(game_ids) * 0.35 / 60.0
            if not messagebox.askyesno(
                "Opening-Odds laden",
                f"{len(game_ids)} Spiele nachladen (Pinnacle, opening=true).\n"
                f"Geschätzte Dauer: ~{est_min:.0f} Min.\n\nStarten?",
            ):
                return

            progress = {"text": "Starte…"}

            def _run():
                def cb(idx, total, loaded, empty, errors):
                    progress["text"] = (
                        f"Opening {idx}/{total} · ok={loaded} leer={empty} err={errors}"
                    )

                try:
                    stats = strat.backfill_opening_odds(
                        client, db, game_ids, bookmaker_id=4, delay=0.35, progress_cb=cb
                    )
                    progress["done"] = stats
                except Exception as e:
                    progress["error"] = str(e)

            t = threading.Thread(target=_run, daemon=True)
            t.start()

            def _set_status(msg: str):
                try:
                    self.current_strategy_label.config(text=msg, fg="#2c5282")
                except Exception:
                    print(msg)

            def _poll():
                if t.is_alive():
                    _set_status(progress.get("text", "Opening-Odds…"))
                    self.after(500, _poll)
                    return
                if progress.get("error"):
                    messagebox.showerror("Fehler", progress["error"])
                    return
                s = progress.get("done") or {}
                messagebox.showinfo(
                    "Fertig",
                    f"Opening geladen: {s.get('loaded', 0)}\n"
                    f"Keine Daten: {s.get('empty', 0)}\n"
                    f"Fehler: {s.get('errors', 0)}\n\n"
                    f"Danach Strategie mit „Opening (Eröffnung)“ analysieren.",
                )
                _set_status(
                    f"Opening-Odds: {s.get('loaded', 0)}/{s.get('total', 0)} geladen"
                )

            self.after(400, _poll)
        except Exception as e:
            messagebox.showerror("Fehler", f"Opening-Odds laden fehlgeschlagen: {e}")
            import traceback
            traceback.print_exc()

    def display_results(self, results: List[Dict]):
        """Display results in the UI"""
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)

        self.summary_text.configure(state=tk.NORMAL)
        self.summary_text.delete(1.0, tk.END)

        if len(results) == 0:
            self.summary_text.insert(1.0, "Keine Ergebnisse gefunden.", "muted")
            self.summary_text.configure(state=tk.DISABLED)
            return

        metrics = strat.compute_strategy_metrics(results)
        total_profit = metrics['total_profit']
        avg_profit = metrics['avg_profit']
        win_rate = metrics['win_rate']
        roi = metrics['roi_pct']
        avg_odds = metrics['avg_odds']
        max_dd = metrics['max_drawdown']
        avg_clv = metrics.get('avg_clv')
        avg_xroi = metrics.get('avg_xroi_pct')
        if avg_xroi is None and avg_clv is not None:
            avg_xroi = avg_clv * 100.0

        home_scores = [r.get('home_score', 0) for r in results if r.get('home_score') is not None]
        away_scores = [r.get('away_score', 0) for r in results if r.get('away_score') is not None]
        avg_goals_home = sum(home_scores) / len(home_scores) if home_scores else 0
        avg_goals_away = sum(away_scores) / len(away_scores) if away_scores else 0

        xg_home_values = []
        xg_away_values = []
        for r in results:
            try:
                if r.get('xg_h') is not None:
                    xg_home_values.append(float(r['xg_h']))
                if r.get('xg_a') is not None:
                    xg_away_values.append(float(r['xg_a']))
            except (ValueError, TypeError):
                pass
        avg_xg_home = sum(xg_home_values) / len(xg_home_values) if xg_home_values else 0
        avg_xg_away = sum(xg_away_values) / len(xg_away_values) if xg_away_values else 0

        markets = strat.selected_markets_from_filters(self.get_current_filters())
        market_summaries = []
        for market_name in markets:
            market_results = [r for r in results if r.get('market') == market_name]
            if not market_results:
                continue
            m = strat.compute_strategy_metrics(market_results)
            market_summaries.append({
                'market': market_name,
                'total': m['n'],
                'won': m['wins'],
                'total_profit': m['total_profit'],
                'avg_profit': m['avg_profit'],
                'win_rate': m['win_rate'],
                'roi': m['roi_pct'],
                'max_losing_streak': m['max_losing_streak'],
                'max_winning_streak': m['max_winning_streak'],
            })

        def insert_line(text, tag=None):
            if tag:
                self.summary_text.insert(tk.END, text + "\n", tag)
            else:
                self.summary_text.insert(tk.END, text + "\n")

        def insert_profit_line(label, value, suffix=""):
            self.summary_text.insert(tk.END, f"  {label}")
            tag = "profit_pos" if value >= 0 else "profit_neg"
            self.summary_text.insert(tk.END, f"{value:+.2f}{suffix}\n", tag)

        insert_line("STRATEGIE-ZUSAMMENFASSUNG", "header")
        insert_line("-" * 42, "muted")
        insert_line("")
        insert_line("GESAMT", "section")
        insert_line(f"  Wetten:     {metrics['n']}")
        insert_line(f"  Gewonnen:   {metrics['wins']}  ({win_rate:.1f}%)")
        insert_profit_line("Profit:     ", total_profit)
        insert_profit_line("Ø Profit:   ", avg_profit)
        insert_profit_line("ROI:        ", roi, " %")
        insert_line(f"  Ø Quote:    {avg_odds:.2f}")
        insert_profit_line("Max DD:     ", max_dd)
        insert_line("")
        insert_line("STREAKS (chronologisch)", "section")
        self.summary_text.insert(tk.END, "  Max ohne Gewinn: ")
        self.summary_text.insert(tk.END, f"{metrics['max_losing_streak']}\n", "profit_neg")
        self.summary_text.insert(tk.END, "  Max Gewinnserie: ")
        self.summary_text.insert(tk.END, f"{metrics['max_winning_streak']}\n", "profit_pos")
        cur_lose = metrics['current_losing_streak']
        if cur_lose > 0:
            self.summary_text.insert(tk.END, "  Aktuell ohne Gewinn: ")
            self.summary_text.insert(tk.END, f"{cur_lose}\n", "profit_neg")
        else:
            insert_line(f"  Aktuell Gewinnserie: {metrics['current_winning_streak']}", "profit_pos")
        xroi_n = int(metrics.get("xroi_n") or 0)
        if avg_xroi is not None:
            insert_profit_line("Ø xROI:     ", avg_xroi, " %")
        else:
            insert_line("  Ø xROI:     —", "muted")
        insert_line(f"  xROI n:     {xroi_n}  (nur Spiele mit Open+Close)", "muted")
        insert_line("            (Open−Close)/Close×100", "muted")
        insert_line("")
        insert_line("TORE / xG", "section")
        insert_line(f"  Ø Tore:     {avg_goals_home:.2f} – {avg_goals_away:.2f}  (Σ {avg_goals_home + avg_goals_away:.2f})")
        insert_line(f"  Ø xG:       {avg_xg_home:.2f} – {avg_xg_away:.2f}  (Σ {avg_xg_home + avg_xg_away:.2f})")
        insert_line("")
        insert_line("PRO MARKT", "section")
        if not market_summaries:
            insert_line("  (keine Marktdaten)", "muted")
        for ms in market_summaries:
            self.summary_text.insert(tk.END, f"  {ms['market']:<12}  n={ms['total']:<4}  WR={ms['win_rate']:5.1f}%  ")
            tag = "profit_pos" if ms['total_profit'] >= 0 else "profit_neg"
            self.summary_text.insert(tk.END, f"P={ms['total_profit']:+.2f}", tag)
            self.summary_text.insert(tk.END, "  ")
            tag2 = "profit_pos" if ms['roi'] >= 0 else "profit_neg"
            self.summary_text.insert(tk.END, f"ROI={ms['roi']:+.1f}%", tag2)
            self.summary_text.insert(tk.END, "  MaxLose=")
            self.summary_text.insert(tk.END, f"{ms['max_losing_streak']}\n", "profit_neg")

        if getattr(self, '_percentile_lookahead', False):
            insert_line("")
            insert_line("⚠ Percentile auf 'profit' = Look-ahead Bias", "warn")

        insert_line("")
        insert_line("Tipp: CSV exportieren für externe Analyse.", "muted")
        self.summary_text.configure(state=tk.DISABLED)

        # Display in treeview
        for result in results:
            profit = result['profit'] if result['profit'] is not None else 0
            rating_h = result['rating_h'] if result['rating_h'] is not None else 0
            rating_a = result['rating_a'] if result['rating_a'] is not None else 0

            chance_home = result.get('chance_home')
            chance_draw = result.get('chance_draw')
            chance_away = result.get('chance_away')
            chance_over = result.get('chance_over')
            chance_under = result.get('chance_under')

            tag = 'profit_positive' if profit > 0 else 'profit_negative'

            xg_home = result.get('xg_h')
            xg_away = result.get('xg_a')
            xg_glicko_home = result.get('xg_glicko_h')
            xg_glicko_away = result.get('xg_glicko_a')

            home_score = result.get('home_score', 0)
            away_score = result.get('away_score', 0)
            result_str = result.get('result', '-')

            home_quote = result.get('home_quote')
            draw_quote = result.get('draw_quote')
            away_quote = result.get('away_quote')
            over_25_quote = result.get('over_25_quote')
            under_25_quote = result.get('under_25_quote')

            home_profit = result.get('home_profit')
            draw_profit = result.get('draw_profit')
            away_profit = result.get('away_profit')
            over_25_profit = result.get('over_25_profit')
            under_25_profit = result.get('under_25_profit')

            sn_h = result.get('home_season_n')
            sn_a = result.get('away_season_n')
            self.results_tree.insert('', 'end',
                values=(
                    result['game_id'],
                    result.get('match_date', result['date']),
                    result['date'],
                    result['home'],
                    result['away'],
                    int(sn_h) if sn_h is not None else "-",
                    int(sn_a) if sn_a is not None else "-",
                    f"{rating_h:.0f}" if rating_h and rating_h > 0 else "-",
                    f"{rating_a:.0f}" if rating_a and rating_a > 0 else "-",
                    f"{xg_glicko_home:.2f}" if xg_glicko_home is not None else "-",
                    f"{xg_glicko_away:.2f}" if xg_glicko_away is not None else "-",
                    home_score if home_score is not None else 0,
                    away_score if away_score is not None else 0,
                    result_str,
                    result['market'],
                    f"{profit:+.2f}",
                    f"{home_quote:.2f}" if home_quote is not None and home_quote > 0 else "-",
                    f"{draw_quote:.2f}" if draw_quote is not None and draw_quote > 0 else "-",
                    f"{away_quote:.2f}" if away_quote is not None and away_quote > 0 else "-",
                    f"{over_25_quote:.2f}" if over_25_quote is not None and over_25_quote > 0 else "-",
                    f"{under_25_quote:.2f}" if under_25_quote is not None and under_25_quote > 0 else "-",
                    f"{home_profit:+.2f}" if home_profit is not None else "-",
                    f"{draw_profit:+.2f}" if draw_profit is not None else "-",
                    f"{away_profit:+.2f}" if away_profit is not None else "-",
                    f"{over_25_profit:+.2f}" if over_25_profit is not None else "-",
                    f"{under_25_profit:+.2f}" if under_25_profit is not None else "-",
                    f"{chance_home:.1%}" if chance_home is not None else "-",
                    f"{chance_draw:.1%}" if chance_draw is not None else "-",
                    f"{chance_away:.1%}" if chance_away is not None else "-",
                    f"{chance_over:.1%}" if chance_over is not None else "-",
                    f"{chance_under:.1%}" if chance_under is not None else "-",
                    f"{xg_home:.2f}" if xg_home is not None else "-",
                    f"{xg_away:.2f}" if xg_away is not None else "-",
                ),
                tags=(tag,)
            )

    def run_metric_ranking(self):
        """Analysiert welche Metrics den ROI vs. Baseline am stärksten beeinflussen."""
        results = getattr(self, "strategy_results", None) or []
        if len(results) < 40:
            # Erst analysieren, falls noch keine/zu wenige Ergebnisse
            markets = strat.selected_markets_from_filters(self.get_current_filters())
            if not markets:
                messagebox.showwarning(
                    "Warnung",
                    "Bitte wähle mindestens einen Markt und starte zuerst „Strategie Analysieren“ "
                    "(oder direkt Metric Ranking mit gesetzten Märkten).",
                )
                return
            self.analyze_strategy()
            results = getattr(self, "strategy_results", None) or []
        if len(results) < 40:
            messagebox.showinfo(
                "Info",
                f"Zu wenige Ergebnisse für Ranking (n={len(results)}). "
                "Mind. ~40 Wetten nötig — Filter lockern.",
            )
            return
        try:
            report = strat.rank_metrics_influence(results, min_n=max(40, min(80, len(results) // 10)))
            self.metric_ranking_report = report
            self.display_metric_ranking(report)
            # Tab öffnen
            if hasattr(self, "results_notebook"):
                for i in range(self.results_notebook.index("end")):
                    if "Metric Ranking" in self.results_notebook.tab(i, "text"):
                        self.results_notebook.select(i)
                        break
        except Exception as e:
            messagebox.showerror("Fehler", f"Metric Ranking fehlgeschlagen: {e}")
            import traceback
            traceback.print_exc()

    def _setup_ranking_tooltips(self):
        """Hover-Beschreibung für Metric-/Regel-Spalten im Ranking."""
        self._ranking_tooltip = None
        self._ranking_tooltip_job = None
        self._ranking_tooltip_key = None

        def hide_tip(_event=None):
            if self._ranking_tooltip_job:
                try:
                    self.after_cancel(self._ranking_tooltip_job)
                except Exception:
                    pass
                self._ranking_tooltip_job = None
            self._ranking_tooltip_key = None
            tip = self._ranking_tooltip
            self._ranking_tooltip = None
            if tip is not None:
                try:
                    tip.destroy()
                except Exception:
                    pass

        def show_tip(text, x, y, key=None):
            tip_old = self._ranking_tooltip
            self._ranking_tooltip = None
            if tip_old is not None:
                try:
                    tip_old.destroy()
                except Exception:
                    pass
            tip = tk.Toplevel(self)
            tip.wm_overrideredirect(True)
            tip.wm_geometry(f"+{x + 12}+{y + 12}")
            try:
                tip.attributes("-topmost", True)
            except Exception:
                pass
            lbl = tk.Label(
                tip,
                text=text,
                justify=tk.LEFT,
                background="#0f172a",
                foreground="#f8fafc",
                relief=tk.SOLID,
                borderwidth=1,
                font=("Segoe UI", 9),
                padx=8,
                pady=6,
                wraplength=340,
            )
            lbl.pack()
            self._ranking_tooltip = tip
            if key is not None:
                self._ranking_tooltip_key = key

        def on_motion(event):
            row_id = self.ranking_tree.identify_row(event.y)
            col_id = self.ranking_tree.identify_column(event.x)
            if not row_id or col_id not in ("#2", "#3"):  # metric, rule
                hide_tip()
                return
            values = self.ranking_tree.item(row_id, "values")
            if not values or len(values) < 3:
                hide_tip()
                return
            metric, rule = values[1], values[2]
            if col_id == "#2":
                text = f"{metric}\n\n{strat.metric_description(str(metric))}"
                key = f"m:{metric}"
            else:
                text = f"{rule}\n\n{strat.rule_description(str(rule))}"
                key = f"r:{rule}"
            if key == self._ranking_tooltip_key and self._ranking_tooltip is not None:
                return
            if self._ranking_tooltip_job:
                try:
                    self.after_cancel(self._ranking_tooltip_job)
                except Exception:
                    pass
            self._ranking_tooltip_key = key
            xr, yr = event.x_root, event.y_root
            self._ranking_tooltip_job = self.after(
                350,
                lambda t=text, x=xr, y=yr, k=key: show_tip(t, x, y, k),
            )

        self.ranking_tree.bind("<Motion>", on_motion)
        self.ranking_tree.bind("<Leave>", hide_tip)
        self.ranking_tree.bind("<ButtonPress>", hide_tip)

    def display_metric_ranking(self, report: Dict):
        """Füllt die Metric-Ranking-Tabelle."""
        for item in self.ranking_tree.get_children():
            self.ranking_tree.delete(item)
        baseline = report.get("baseline") or {}
        ranked = report.get("ranked") or []
        self.ranking_baseline_label.config(
            text=(
                f"Baseline: n={baseline.get('n', 0)}  |  "
                f"Profit={baseline.get('total_profit', 0):+.2f}  |  "
                f"ROI={baseline.get('roi_pct', 0):+.1f}%  |  "
                f"WR={baseline.get('win_rate', 0):.1f}%  |  "
                f"min_n={report.get('min_n', 40)}"
            )
        )
        if not ranked:
            self.ranking_tree.insert(
                "", "end",
                values=("-", "—", "keine gültigen Schwellen", "—", "", "", "", "", "", "", "", ""),
            )
            return
        # Top 50 anzeigen
        for i, row in enumerate(ranked[:50], start=1):
            tag = "pos" if row.get("roi_delta", 0) >= 0 else "neg"
            self.ranking_tree.insert(
                "", "end",
                values=(
                    i,
                    row.get("metric", ""),
                    row.get("rule", ""),
                    row.get("condition", ""),
                    row.get("n", 0),
                    f"{row.get('win_rate', 0):.1f}",
                    f"{row.get('total_profit', 0):+.2f}",
                    f"{row.get('roi_pct', 0):+.1f}",
                    f"{row.get('roi_delta', 0):+.1f}",
                    f"{row.get('profit_delta', 0):+.2f}",
                    row.get("max_losing_streak", 0),
                    f"{row.get('coverage_pct', 0):.0f}",
                ),
                tags=(tag,),
            )

    def _setup_bucket_panel(self, parent):
        """UI für Bucket-Analyse: Range → Steps, Tabelle + Charts."""
        parent.grid_rowconfigure(2, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        hint = tk.Label(
            parent,
            text=(
                "Bereich (z.B. Away-Quote 3.0–3.5) in Schritte (0.1) teilen → "
                "Profit/ROI je Bin + Grafiken."
            ),
            fg="#475569",
            wraplength=480,
            justify=tk.LEFT,
        )
        hint.grid(row=0, column=0, sticky="ew", padx=4, pady=(2, 2))

        ctrl = ttk.Frame(parent)
        ctrl.grid(row=1, column=0, sticky="ew", padx=4, pady=(0, 4))

        ttk.Label(ctrl, text="Metric:").pack(side=tk.LEFT, padx=(0, 4))
        metric_labels = {
            "away_quote": "Away-Quote",
            "home_quote": "Home-Quote",
            "draw_quote": "Draw-Quote",
            "odds": "Markt-Quote (odds)",
            "chance": "Chance",
            "rating_diff": "Rating Diff",
            "glicko_diff": "glicko_diff",
            "rating_avg": "Rating Avg",
            "xg_glicko_sum": "xG Glicko Sum",
            "xg_glicko_diff": "xG Glicko Diff",
            "over_25_quote": "Over 2.5 Quote",
            "under_25_quote": "Under 2.5 Quote",
        }
        self._bucket_metric_keys = list(strat.BUCKET_METRICS)
        self._bucket_metric_display = [metric_labels.get(k, k) for k in self._bucket_metric_keys]
        self.bucket_metric_var = tk.StringVar(value=self._bucket_metric_display[0])
        self.bucket_metric_combo = ttk.Combobox(
            ctrl,
            textvariable=self.bucket_metric_var,
            values=self._bucket_metric_display,
            state="readonly",
            width=18,
        )
        self.bucket_metric_combo.pack(side=tk.LEFT, padx=(0, 8))

        ttk.Label(ctrl, text="Min:").pack(side=tk.LEFT)
        self.bucket_min_var = tk.StringVar(value="3.0")
        ttk.Entry(ctrl, textvariable=self.bucket_min_var, width=6).pack(side=tk.LEFT, padx=(2, 6))

        ttk.Label(ctrl, text="Max:").pack(side=tk.LEFT)
        self.bucket_max_var = tk.StringVar(value="3.5")
        ttk.Entry(ctrl, textvariable=self.bucket_max_var, width=6).pack(side=tk.LEFT, padx=(2, 6))

        ttk.Label(ctrl, text="Step:").pack(side=tk.LEFT)
        self.bucket_step_var = tk.StringVar(value="0.1")
        ttk.Entry(ctrl, textvariable=self.bucket_step_var, width=5).pack(side=tk.LEFT, padx=(2, 8))

        ttk.Button(ctrl, text="Berechnen", command=self.run_bucket_analysis).pack(side=tk.LEFT, padx=(0, 6))

        self.bucket_summary_label = tk.Label(ctrl, text="Gesamt: —", fg="#334155", anchor="w")
        self.bucket_summary_label.pack(side=tk.LEFT, padx=(8, 0), fill=tk.X, expand=True)

        body = ttk.PanedWindow(parent, orient=tk.VERTICAL)
        body.grid(row=2, column=0, sticky="nsew", padx=2, pady=2)

        table_wrap = ttk.Frame(body)
        body.add(table_wrap, weight=2)

        cols = (
            "bin", "n", "wins", "wr", "profit", "roi", "avg_odds",
            "xg_h", "xg_a", "xg_sum", "xg_diff", "max_lose",
        )
        scroll_y = ttk.Scrollbar(table_wrap, orient="vertical")
        scroll_x = ttk.Scrollbar(table_wrap, orient="horizontal")
        self.bucket_tree = ttk.Treeview(
            table_wrap,
            columns=cols,
            show="headings",
            yscrollcommand=scroll_y.set,
            xscrollcommand=scroll_x.set,
            height=8,
        )
        headings = {
            "bin": "Bin",
            "n": "n",
            "wins": "Wins",
            "wr": "WR%",
            "profit": "Profit",
            "roi": "ROI%",
            "avg_odds": "Ø Quote",
            "xg_h": "Ø xG H",
            "xg_a": "Ø xG A",
            "xg_sum": "Ø xG Sum",
            "xg_diff": "Ø xG Diff",
            "max_lose": "MaxLose",
        }
        widths = {
            "bin": 95, "n": 42, "wins": 45, "wr": 52,
            "profit": 65, "roi": 58, "avg_odds": 60,
            "xg_h": 62, "xg_a": 62, "xg_sum": 70, "xg_diff": 70,
            "max_lose": 58,
        }
        for c in cols:
            self.bucket_tree.heading(c, text=headings[c])
            self.bucket_tree.column(c, width=widths[c], anchor="center")
        self.bucket_tree.tag_configure("pos", background="#dcfce7")
        self.bucket_tree.tag_configure("neg", background="#fee2e2")
        self.bucket_tree.tag_configure("empty", foreground="#94a3b8")
        scroll_y.config(command=self.bucket_tree.yview)
        scroll_x.config(command=self.bucket_tree.xview)
        self.bucket_tree.grid(row=0, column=0, sticky="nsew")
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x.grid(row=1, column=0, sticky="ew")
        table_wrap.grid_rowconfigure(0, weight=1)
        table_wrap.grid_columnconfigure(0, weight=1)

        self.bucket_chart_frame = ttk.Frame(body)
        body.add(self.bucket_chart_frame, weight=3)
        tk.Label(
            self.bucket_chart_frame,
            text="Charts erscheinen nach „Berechnen“.",
            fg="#94a3b8",
        ).pack(expand=True)

    def _bucket_selected_metric_key(self) -> str:
        display = self.bucket_metric_var.get()
        try:
            idx = self._bucket_metric_display.index(display)
            return self._bucket_metric_keys[idx]
        except (ValueError, AttributeError):
            return "away_quote"

    def run_bucket_analysis(self):
        """Zerlegt eine Metric-Range in Bins und zeigt Profit/ROI + Charts."""
        results = getattr(self, "strategy_results", None) or []
        if not results:
            markets = strat.selected_markets_from_filters(self.get_current_filters())
            if not markets:
                messagebox.showwarning(
                    "Warnung",
                    "Bitte zuerst „Strategie Analysieren“ ausführen "
                    "(oder Märkte setzen und erneut versuchen).",
                )
                return
            self.analyze_strategy()
            results = getattr(self, "strategy_results", None) or []
        if not results:
            messagebox.showinfo("Info", "Keine Strategie-Ergebnisse vorhanden.")
            return

        try:
            vmin = float(str(self.bucket_min_var.get()).replace(",", "."))
            vmax = float(str(self.bucket_max_var.get()).replace(",", "."))
            step = float(str(self.bucket_step_var.get()).replace(",", "."))
        except ValueError:
            messagebox.showerror("Fehler", "Min / Max / Step müssen Zahlen sein (z.B. 3.0, 3.5, 0.1).")
            return
        if step <= 0:
            messagebox.showerror("Fehler", "Step muss größer als 0 sein.")
            return
        if abs(vmax - vmin) / step > 500:
            messagebox.showerror("Fehler", "Zu viele Bins (max. 500). Step vergrößern oder Range verkleinern.")
            return

        metric = self._bucket_selected_metric_key()
        try:
            report = strat.bucket_metric_range(results, metric, vmin, vmax, step)
            self.bucket_report = report
            self.display_bucket_analysis(report)
            if hasattr(self, "results_notebook"):
                for i in range(self.results_notebook.index("end")):
                    if "Bucket" in self.results_notebook.tab(i, "text"):
                        self.results_notebook.select(i)
                        break
        except Exception as e:
            messagebox.showerror("Fehler", f"Bucket-Analyse fehlgeschlagen: {e}")
            import traceback
            traceback.print_exc()

    def display_bucket_analysis(self, report: Dict):
        """Füllt Bucket-Tabelle und Charts."""
        for item in self.bucket_tree.get_children():
            self.bucket_tree.delete(item)

        overall = report.get("overall") or {}
        oxg = report.get("overall_xg") or {}
        xh = oxg.get("avg_xg_glicko_h")
        xa = oxg.get("avg_xg_glicko_a")
        xg_txt = ""
        if xh is not None or xa is not None:
            xg_txt = (
                f"  |  Ø xG H={xh:.2f}" if xh is not None else "  |  Ø xG H=—"
            )
            xg_txt += f" A={xa:.2f}" if xa is not None else " A=—"
        self.bucket_summary_label.config(
            text=(
                f"In Range: n={report.get('n_in_range', 0)}/{report.get('n_total', 0)}  |  "
                f"Profit={overall.get('total_profit', 0):+.2f}  |  "
                f"ROI={overall.get('roi_pct', 0):+.1f}%  |  "
                f"WR={overall.get('win_rate', 0):.1f}%  |  "
                f"step={report.get('step', 0.1)}"
                f"{xg_txt}"
            )
        )

        bins = report.get("bins") or []
        if not bins:
            self.bucket_tree.insert(
                "", "end",
                values=("—", "", "", "", "", "", "", "", "", "", "", ""),
                tags=("empty",),
            )
        else:
            def _fmt_xg(v):
                return f"{v:.2f}" if v is not None else "—"

            for b in bins:
                n = b.get("n") or 0
                profit = b.get("total_profit") or 0.0
                if n == 0:
                    tag = "empty"
                elif profit >= 0:
                    tag = "pos"
                else:
                    tag = "neg"
                self.bucket_tree.insert(
                    "", "end",
                    values=(
                        b.get("label", ""),
                        n,
                        b.get("wins", 0),
                        f"{b.get('win_rate', 0):.1f}" if n else "—",
                        f"{profit:+.2f}" if n else "—",
                        f"{b.get('roi_pct', 0):+.1f}" if n else "—",
                        f"{b.get('avg_odds', 0):.2f}" if n and b.get("avg_odds") else "—",
                        _fmt_xg(b.get("avg_xg_glicko_h")) if n else "—",
                        _fmt_xg(b.get("avg_xg_glicko_a")) if n else "—",
                        _fmt_xg(b.get("avg_xg_glicko_sum")) if n else "—",
                        _fmt_xg(b.get("avg_xg_glicko_diff")) if n else "—",
                        b.get("max_losing_streak", 0) if n else "—",
                    ),
                    tags=(tag,),
                )

        self.update_bucket_charts(report)

    def update_bucket_charts(self, report: Dict):
        """Balken-Charts: Profit und ROI je Bin."""
        frame = getattr(self, "bucket_chart_frame", None)
        if frame is None:
            return
        for widget in frame.winfo_children():
            widget.destroy()

        if not HAS_MATPLOTLIB:
            tk.Label(
                frame,
                text="Matplotlib nicht installiert.\npip install matplotlib",
                fg="red",
                justify=tk.CENTER,
            ).pack(expand=True)
            return

        bins = report.get("bins") or []
        if not bins:
            tk.Label(frame, text="Keine Bins", fg="gray").pack(expand=True)
            return

        labels = [b.get("label", "") for b in bins]
        profits = [b.get("total_profit") or 0.0 for b in bins]
        rois = [b.get("roi_pct") or 0.0 for b in bins]
        ns = [b.get("n") or 0 for b in bins]
        xg_h = [b.get("avg_xg_glicko_h") if (b.get("n") or 0) else None for b in bins]
        xg_a = [b.get("avg_xg_glicko_a") if (b.get("n") or 0) else None for b in bins]
        x = list(range(len(labels)))

        fig = Figure(figsize=(10.5, 4.0), dpi=100)
        ax1 = fig.add_subplot(131)
        ax2 = fig.add_subplot(132)
        ax3 = fig.add_subplot(133)

        colors_p = ["#16a34a" if p >= 0 else "#dc2626" for p in profits]
        ax1.bar(x, profits, color=colors_p, alpha=0.85)
        ax1.axhline(0, color="#64748b", linewidth=0.8, linestyle="--")
        ax1.set_xticks(x)
        ax1.set_xticklabels(labels, rotation=45, ha="right", fontsize=7)
        ax1.set_title("Profit je Bin", fontsize=10, fontweight="bold")
        ax1.set_ylabel("Profit (Units)")
        ax1.grid(True, axis="y", alpha=0.3)

        colors_r = ["#16a34a" if r >= 0 else "#dc2626" for r in rois]
        bar_colors = [c if n > 0 else "#cbd5e1" for c, n in zip(colors_r, ns)]
        ax2.bar(x, rois, color=bar_colors, alpha=0.85)
        ax2.axhline(0, color="#64748b", linewidth=0.8, linestyle="--")
        ax2.set_xticks(x)
        ax2.set_xticklabels(labels, rotation=45, ha="right", fontsize=7)
        ax2.set_title("ROI% je Bin", fontsize=10, fontweight="bold")
        ax2.set_ylabel("ROI %")
        ax2.grid(True, axis="y", alpha=0.3)

        # Ø xG Glicko Home/Away je Bin (Linie, nur wo Daten)
        xh_plot = [v if v is not None else float("nan") for v in xg_h]
        xa_plot = [v if v is not None else float("nan") for v in xg_a]
        ax3.plot(x, xh_plot, "o-", color="#2563eb", linewidth=1.8, markersize=4, label="Ø xG H")
        ax3.plot(x, xa_plot, "s-", color="#ea580c", linewidth=1.8, markersize=4, label="Ø xG A")
        ax3.set_xticks(x)
        ax3.set_xticklabels(labels, rotation=45, ha="right", fontsize=7)
        ax3.set_title("Ø xG Glicko je Bin", fontsize=10, fontweight="bold")
        ax3.set_ylabel("xG Glicko")
        ax3.grid(True, axis="y", alpha=0.3)
        ax3.legend(loc="best", fontsize=8)

        metric = report.get("metric", "")
        fig.suptitle(
            f"Bucket: {metric}  {report.get('vmin')}–{report.get('vmax')}  (step {report.get('step')})",
            fontsize=10,
        )
        fig.tight_layout(rect=[0, 0, 1, 0.94])

        canvas = FigureCanvasTkAgg(fig, frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def export_results_csv(self):
        """Export aktuelle Strategie-Ergebnisse als CSV."""
        results = getattr(self, 'strategy_results', None) or []
        if not results:
            messagebox.showinfo("Info", "Keine Ergebnisse zum Exportieren. Zuerst analysieren.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile="strategy_results.csv",
        )
        if not path:
            return
        try:
            rows = strat.results_to_csv_rows(results)
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f, delimiter=";")
                writer.writerows(rows)
            # Optional Ranking mitexportieren
            report = getattr(self, "metric_ranking_report", None)
            if report and report.get("ranked"):
                rank_path = path.replace(".csv", "_metric_ranking.csv")
                with open(rank_path, "w", newline="", encoding="utf-8-sig") as f:
                    w = csv.writer(f, delimiter=";")
                    w.writerow([
                        "rank", "metric", "rule", "condition", "n", "win_rate",
                        "total_profit", "roi_pct", "roi_delta", "profit_delta",
                        "max_losing_streak", "coverage_pct",
                    ])
                    for i, r in enumerate(report["ranked"], start=1):
                        w.writerow([
                            i, r.get("metric"), r.get("rule"), r.get("condition"),
                            r.get("n"), r.get("win_rate"), r.get("total_profit"),
                            r.get("roi_pct"), r.get("roi_delta"), r.get("profit_delta"),
                            r.get("max_losing_streak"), r.get("coverage_pct"),
                        ])
            bucket = getattr(self, "bucket_report", None)
            if bucket and bucket.get("bins"):
                bucket_path = path.replace(".csv", "_buckets.csv")
                with open(bucket_path, "w", newline="", encoding="utf-8-sig") as f:
                    w = csv.writer(f, delimiter=";")
                    w.writerow([
                        "metric", "bin_from", "bin_to", "label", "n", "wins",
                        "win_rate", "total_profit", "roi_pct", "avg_odds",
                        "avg_xg_glicko_h", "avg_xg_glicko_a", "avg_xg_glicko_sum",
                        "avg_xg_glicko_diff", "max_losing_streak",
                    ])
                    for b in bucket["bins"]:
                        w.writerow([
                            bucket.get("metric"), b.get("bin_from"), b.get("bin_to"),
                            b.get("label"), b.get("n"), b.get("wins"),
                            b.get("win_rate"), b.get("total_profit"), b.get("roi_pct"),
                            b.get("avg_odds"),
                            b.get("avg_xg_glicko_h"), b.get("avg_xg_glicko_a"),
                            b.get("avg_xg_glicko_sum"), b.get("avg_xg_glicko_diff"),
                            b.get("max_losing_streak"),
                        ])
            messagebox.showinfo("Erfolg", f"{len(results)} Zeilen exportiert:\n{path}")
        except Exception as e:
            messagebox.showerror("Fehler", f"CSV-Export fehlgeschlagen: {e}")


    def update_profit_chart(self, results: List[Dict]):
        """Update the profit chart with cumulative profit over time"""
        if not HAS_MATPLOTLIB:
            # Show message if matplotlib not available
            for widget in self.chart_frame.winfo_children():
                widget.destroy()
            no_matplotlib_label = tk.Label(self.chart_frame, 
                                          text="Matplotlib nicht installiert.\nBitte installieren Sie es mit: pip install matplotlib",
                                          fg="red", justify=tk.CENTER)
            no_matplotlib_label.pack(expand=True)
            return
        
        # Clear previous chart
        for widget in self.chart_frame.winfo_children():
            widget.destroy()
        
        if not results:
            no_data_label = tk.Label(self.chart_frame, text="Keine Daten zum Anzeigen", fg="gray")
            no_data_label.pack(expand=True)
            return
        
        # Sort results by date (oldest first for cumulative calculation)
        sorted_results = sorted(results, key=lambda x: x.get('date', ''))
        
        # Calculate cumulative profit
        cumulative_profit = []
        running_total = 0.0
        game_numbers = []
        
        for idx, result in enumerate(sorted_results):
            profit = result.get('profit', 0) if result.get('profit') is not None else 0
            running_total += profit
            cumulative_profit.append(running_total)
            game_numbers.append(idx)  # 0 = ältestes Spiel
        
        # Create matplotlib figure
        fig = Figure(figsize=(10, 5), dpi=100)
        ax = fig.add_subplot(111)
        
        # Plot cumulative profit
        ax.plot(game_numbers, cumulative_profit, linewidth=2, color='#2E86AB', label='Kumulativer Profit')
        ax.axhline(y=0, color='gray', linestyle='--', linewidth=1, alpha=0.5)
        
        # Fill area above/below zero
        ax.fill_between(game_numbers, cumulative_profit, 0, 
                        where=[p >= 0 for p in cumulative_profit], 
                        color='green', alpha=0.3, label='Profit')
        ax.fill_between(game_numbers, cumulative_profit, 0, 
                        where=[p < 0 for p in cumulative_profit], 
                        color='red', alpha=0.3, label='Verlust')
        
        # Formatting
        ax.set_xlabel('Anzahl Spiele (0 = ältestes Spiel)', fontsize=10)
        ax.set_ylabel('Kumulativer Profit', fontsize=10)
        ax.set_title('Profit-Verlauf über Zeit', fontsize=12, fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.legend(loc='best')
        
        # Add final profit annotation
        if cumulative_profit:
            final_profit = cumulative_profit[-1]
            ax.annotate(f'Gesamt: {final_profit:+.2f}', 
                       xy=(game_numbers[-1], final_profit),
                       xytext=(10, 10), textcoords='offset points',
                       bbox=dict(boxstyle='round,pad=0.5', facecolor='yellow', alpha=0.7),
                       arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0'))
        
        # Embed in tkinter
        canvas = FigureCanvasTkAgg(fig, self.chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    
    def load_strategies(self):
        """Load saved strategies from file"""
        if os.path.exists(self.strategies_path):
            try:
                with open(self.strategies_path, 'r', encoding='utf-8') as f:
                    self.saved_strategies = json.load(f)
            except Exception as e:
                print(f"[WARNING] Error loading strategies: {e}")
                self.saved_strategies = {}
        else:
            self.saved_strategies = {}
    
    def save_strategies(self):
        """Save strategies to file"""
        try:
            os.makedirs(os.path.dirname(self.strategies_path), exist_ok=True)
            with open(self.strategies_path, 'w', encoding='utf-8') as f:
                json.dump(self.saved_strategies, f, indent=2, ensure_ascii=False)
            print(f"[DEBUG] Strategien gespeichert in: {self.strategies_path}")
            print(f"[DEBUG] Anzahl Strategien: {len(self.saved_strategies)}")
        except Exception as e:
            print(f"[ERROR] Fehler beim Speichern: {e}")
            messagebox.showerror("Fehler", f"Fehler beim Speichern der Strategien: {e}")
    
    def get_current_filters(self) -> Dict:
        """Get current filter values as dictionary"""
        return {
            'market_home': self.market_home.get(),
            'market_draw': self.market_draw.get(),
            'market_away': self.market_away.get(),
            'market_over': self.market_over.get(),
            'market_under': self.market_under.get(),
            'market_over_35': self.market_over_35.get(),
            'market_under_35': self.market_under_35.get(),
            'market_over_45': self.market_over_45.get(),
            'market_under_45': self.market_under_45.get(),
            'glicko_home_min': self.glicko_home_min.get(),
            'glicko_home_max': self.glicko_home_max.get(),
            'glicko_away_min': self.glicko_away_min.get(),
            'glicko_away_max': self.glicko_away_max.get(),
            'glicko_rd_home_min': self.glicko_rd_home_min.get(),
            'glicko_rd_home_max': self.glicko_rd_home_max.get(),
            'glicko_rd_away_min': self.glicko_rd_away_min.get(),
            'glicko_rd_away_max': self.glicko_rd_away_max.get(),
            'glicko_vol_home_min': self.glicko_vol_home_min.get(),
            'glicko_vol_home_max': self.glicko_vol_home_max.get(),
            'glicko_vol_away_min': self.glicko_vol_away_min.get(),
            'glicko_vol_away_max': self.glicko_vol_away_max.get(),
            'glicko_p_home_min': self.glicko_p_home_min.get(),
            'glicko_p_home_max': self.glicko_p_home_max.get(),
            'glicko_p_draw_min': self.glicko_p_draw_min.get(),
            'glicko_p_draw_max': self.glicko_p_draw_max.get(),
            'glicko_p_away_min': self.glicko_p_away_min.get(),
            'glicko_p_away_max': self.glicko_p_away_max.get(),
            'xg_glicko_home_min': self.xg_glicko_home_min.get(),
            'xg_glicko_home_max': self.xg_glicko_home_max.get(),
            'xg_glicko_away_min': self.xg_glicko_away_min.get(),
            'xg_glicko_away_max': self.xg_glicko_away_max.get(),
            'season_games_home_min': self.season_games_home_min.get(),
            'season_games_home_max': self.season_games_home_max.get(),
            'season_games_away_min': self.season_games_away_min.get(),
            'season_games_away_max': self.season_games_away_max.get(),
            'use_xg_comparison': self.use_xg_comparison.get(),
            'xg_attr1': self.xg_attr1.get(),
            'xg_operation': self.xg_operation.get(),
            'xg_attr2': self.xg_attr2.get(),
            'xg_comparison_operator': self.xg_comparison_operator.get(),
            'xg_comparison_value': self.xg_comparison_value.get(),
            'odds_home_min': self.odds_home_min.get(),
            'odds_home_max': self.odds_home_max.get(),
            'odds_draw_min': self.odds_draw_min.get(),
            'odds_draw_max': self.odds_draw_max.get(),
            'odds_away_min': self.odds_away_min.get(),
            'odds_away_max': self.odds_away_max.get(),
            'odds_over_min': self.odds_over_min.get(),
            'odds_over_max': self.odds_over_max.get(),
            'odds_under_min': self.odds_under_min.get(),
            'odds_under_max': self.odds_under_max.get(),
            'odds_over35_min': self.odds_over35_min.get(),
            'odds_over35_max': self.odds_over35_max.get(),
            'odds_under35_min': self.odds_under35_min.get(),
            'odds_under35_max': self.odds_under35_max.get(),
            'odds_over45_min': self.odds_over45_min.get(),
            'odds_over45_max': self.odds_over45_max.get(),
            'odds_under45_min': self.odds_under45_min.get(),
            'odds_under45_max': self.odds_under45_max.get(),
            'odds_type': self.odds_type.get(),
            'date_from': self.date_from.get(),
            'date_to': self.date_to.get(),
            'chance_min': self.chance_min.get(),
            'chance_max': self.chance_max.get(),
            'country_filter': self.country_filter.get(),
            'league_filter': self.league_filter.get(),
            'gender_filter': self.gender_filter.get() or 'all',
            'min_games_count': self.min_games_count.get(),
            'use_percentile': self.use_percentile.get(),
            'percentile_value': self.percentile_value.get(),
            'percentile_metric': self.percentile_metric.get()
        }
    
    def apply_filters(self, filters: Dict):
        """Apply filter values from dictionary"""
        self.market_home.set(filters.get('market_home', False))
        self.market_draw.set(filters.get('market_draw', False))
        self.market_away.set(filters.get('market_away', False))
        self.market_over.set(filters.get('market_over', False))
        self.market_under.set(filters.get('market_under', False))
        self.market_over_35.set(filters.get('market_over_35', False))
        self.market_under_35.set(filters.get('market_under_35', False))
        self.market_over_45.set(filters.get('market_over_45', False))
        self.market_under_45.set(filters.get('market_under_45', False))
        self.glicko_home_min.set(filters.get('glicko_home_min', ''))
        self.glicko_home_max.set(filters.get('glicko_home_max', ''))
        self.glicko_away_min.set(filters.get('glicko_away_min', ''))
        self.glicko_away_max.set(filters.get('glicko_away_max', ''))
        self.glicko_rd_home_min.set(filters.get('glicko_rd_home_min', ''))
        self.glicko_rd_home_max.set(filters.get('glicko_rd_home_max', ''))
        self.glicko_rd_away_min.set(filters.get('glicko_rd_away_min', ''))
        self.glicko_rd_away_max.set(filters.get('glicko_rd_away_max', ''))
        self.glicko_vol_home_min.set(filters.get('glicko_vol_home_min', ''))
        self.glicko_vol_home_max.set(filters.get('glicko_vol_home_max', ''))
        self.glicko_vol_away_min.set(filters.get('glicko_vol_away_min', ''))
        self.glicko_vol_away_max.set(filters.get('glicko_vol_away_max', ''))
        self.glicko_p_home_min.set(filters.get('glicko_p_home_min', ''))
        self.glicko_p_home_max.set(filters.get('glicko_p_home_max', ''))
        self.glicko_p_draw_min.set(filters.get('glicko_p_draw_min', ''))
        self.glicko_p_draw_max.set(filters.get('glicko_p_draw_max', ''))
        self.glicko_p_away_min.set(filters.get('glicko_p_away_min', ''))
        self.glicko_p_away_max.set(filters.get('glicko_p_away_max', ''))
        self.xg_glicko_home_min.set(filters.get('xg_glicko_home_min', ''))
        self.xg_glicko_home_max.set(filters.get('xg_glicko_home_max', ''))
        self.xg_glicko_away_min.set(filters.get('xg_glicko_away_min', ''))
        self.xg_glicko_away_max.set(filters.get('xg_glicko_away_max', ''))
        self.season_games_home_min.set(filters.get('season_games_home_min', ''))
        self.season_games_home_max.set(filters.get('season_games_home_max', ''))
        self.season_games_away_min.set(filters.get('season_games_away_min', ''))
        self.season_games_away_max.set(filters.get('season_games_away_max', ''))
        self.use_xg_comparison.set(filters.get('use_xg_comparison', False))
        self.xg_attr1.set(filters.get('xg_attr1', 'rating_home'))
        self.xg_operation.set(filters.get('xg_operation', '-'))
        self.xg_attr2.set(filters.get('xg_attr2', 'rating_away'))
        self.xg_comparison_operator.set(filters.get('xg_comparison_operator', '>='))
        self.xg_comparison_value.set(filters.get('xg_comparison_value', ''))
        self.odds_home_min.set(filters.get('odds_home_min', ''))
        self.odds_home_max.set(filters.get('odds_home_max', ''))
        self.odds_draw_min.set(filters.get('odds_draw_min', ''))
        self.odds_draw_max.set(filters.get('odds_draw_max', ''))
        self.odds_away_min.set(filters.get('odds_away_min', ''))
        self.odds_away_max.set(filters.get('odds_away_max', ''))
        self.odds_over_min.set(filters.get('odds_over_min', ''))
        self.odds_over_max.set(filters.get('odds_over_max', ''))
        self.odds_under_min.set(filters.get('odds_under_min', ''))
        self.odds_under_max.set(filters.get('odds_under_max', ''))
        self.odds_over35_min.set(filters.get('odds_over35_min', ''))
        self.odds_over35_max.set(filters.get('odds_over35_max', ''))
        self.odds_under35_min.set(filters.get('odds_under35_min', ''))
        self.odds_under35_max.set(filters.get('odds_under35_max', ''))
        self.odds_over45_min.set(filters.get('odds_over45_min', ''))
        self.odds_over45_max.set(filters.get('odds_over45_max', ''))
        self.odds_under45_min.set(filters.get('odds_under45_min', ''))
        self.odds_under45_max.set(filters.get('odds_under45_max', ''))
        self.odds_type.set(filters.get('odds_type', 'closing'))
        self.date_from.set(filters.get('date_from', ''))
        self.date_to.set(filters.get('date_to', ''))
        self.chance_min.set(filters.get('chance_min', ''))
        self.chance_max.set(filters.get('chance_max', ''))
        self.country_filter.set(filters.get('country_filter', ''))
        self.league_filter.set(filters.get('league_filter', ''))
        self.gender_filter.set(filters.get('gender_filter') or filters.get('gender') or 'men')
        self.min_games_count.set(filters.get('min_games_count', '5'))
        self.use_percentile.set(filters.get('use_percentile', False))
        self.percentile_value.set(filters.get('percentile_value', '10'))
        self.percentile_metric.set(filters.get('percentile_metric', 'chance'))
        # xg_comparison wird bereits oben gesetzt
    
    def save_strategy(self):
        """Save current strategy"""
        name = simpledialog.askstring("Strategie speichern", "Name der Strategie:")
        if not name:
            return
        
        try:
            filters = self.get_current_filters()
            print(f"[DEBUG] Speichere Strategie '{name}' mit {len(filters)} Filtern")
            self.saved_strategies[name] = {
                'filters': filters,
                'created': datetime.now().isoformat(),
                'updated': datetime.now().isoformat()
            }
            self.save_strategies()
            self.current_strategy_name = name
            self.current_strategy_label.config(text=f"Aktuelle Strategie: {name}", fg="green")
            messagebox.showinfo(
                "Erfolg",
                f"Strategie '{name}' gespeichert!\n\nAls Nächstes: passende bevorstehende Spiele…",
            )
            try:
                self.check_matches_against_strategies()
            except Exception as e2:
                print(f"[WARNING] Upcoming nach Speichern: {e2}")
        except Exception as e:
            print(f"[ERROR] Fehler beim Speichern der Strategie: {e}")
            messagebox.showerror("Fehler", f"Fehler beim Speichern: {e}")
    
    def load_strategy_dialog(self):
        """Show dialog to load a strategy"""
        if not self.saved_strategies:
            messagebox.showinfo("Info", "Keine gespeicherten Strategien vorhanden.")
            return
        
        dialog = tk.Toplevel(self)
        dialog.title("Strategie laden")
        dialog.geometry("520x420")
        dialog.minsize(400, 300)
        dialog.resizable(True, True)
        
        tk.Label(dialog, text="Wähle eine Strategie:", font=("Arial", 10, "bold")).pack(pady=10)
        
        listbox_frame = ttk.Frame(dialog)
        listbox_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        scrollbar = ttk.Scrollbar(listbox_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        listbox = tk.Listbox(listbox_frame, yscrollcommand=scrollbar.set)
        scrollbar.config(command=listbox.yview)
        
        for name in sorted(self.saved_strategies.keys()):
            strategy = self.saved_strategies[name]
            created = strategy.get('created', 'Unknown')
            listbox.insert(tk.END, f"{name} (erstellt: {created[:10]})")
        
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        def load_selected():
            selection = listbox.curselection()
            if not selection:
                messagebox.showwarning("Warnung", "Bitte wähle eine Strategie aus.")
                return
            
            try:
                selected_name = list(listbox.get(i) for i in selection)[0].split(" (")[0]
                strategy = self.saved_strategies[selected_name]
                filters = strategy.get('filters', {})
                print(f"[DEBUG] Lade Strategie '{selected_name}' mit {len(filters)} Filtern")
                print(f"[DEBUG] Filter: {list(filters.keys())}")
                self.apply_filters(filters)
                self.current_strategy_name = selected_name
                self.current_strategy_label.config(text=f"Aktuelle Strategie: {selected_name}", fg="green")
                dialog.destroy()
                messagebox.showinfo("Erfolg", f"Strategie '{selected_name}' geladen!")
            except Exception as e:
                print(f"[ERROR] Fehler beim Laden der Strategie: {e}")
                messagebox.showerror("Fehler", f"Fehler beim Laden: {e}")
        
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)
        ttk.Button(button_frame, text="Laden", command=load_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Abbrechen", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
    
    def manage_strategies(self):
        """Manage saved strategies (view, delete)"""
        if not self.saved_strategies:
            messagebox.showinfo("Info", "Keine gespeicherten Strategien vorhanden.")
            return
        
        dialog = tk.Toplevel(self)
        dialog.title("Strategien verwalten")
        dialog.geometry("640x480")
        dialog.minsize(420, 320)
        dialog.resizable(True, True)
        
        tk.Label(dialog, text="Gespeicherte Strategien:", font=("Arial", 10, "bold")).pack(pady=10)
        
        tree_frame = ttk.Frame(dialog)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        scrollbar = ttk.Scrollbar(tree_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        tree = ttk.Treeview(tree_frame, columns=("created", "updated"), show='tree headings', yscrollcommand=scrollbar.set)
        scrollbar.config(command=tree.yview)
        
        tree.heading('#0', text='Name')
        tree.heading('created', text='Erstellt')
        tree.heading('updated', text='Aktualisiert')
        
        for name, strategy in sorted(self.saved_strategies.items()):
            created = strategy.get('created', 'Unknown')[:19] if strategy.get('created') else 'Unknown'
            updated = strategy.get('updated', 'Unknown')[:19] if strategy.get('updated') else 'Unknown'
            tree.insert('', 'end', text=name, values=(created, updated))
        
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        def delete_selected():
            selection = tree.selection()
            if not selection:
                messagebox.showwarning("Warnung", "Bitte wähle eine Strategie aus.")
                return
            
            selected_name = tree.item(selection[0])['text']
            if messagebox.askyesno("Bestätigen", f"Strategie '{selected_name}' wirklich löschen?"):
                del self.saved_strategies[selected_name]
                self.save_strategies()
                tree.delete(selection[0])
                if self.current_strategy_name == selected_name:
                    self.current_strategy_name = None
                    self.current_strategy_label.config(text="Aktuelle Strategie: Keine", fg="gray")
                messagebox.showinfo("Erfolg", f"Strategie '{selected_name}' gelöscht!")
        
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)
        ttk.Button(button_frame, text="Löschen", command=delete_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Schließen", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
    

    def _strategies_to_check(self):
        """Immer aktuelle UI-Filter; optional geladene Strategie zusätzlich."""
        strategies = [("Aktuelle Filter", {"filters": self.get_current_filters()})]
        name = getattr(self, "current_strategy_name", None)
        if name and name in self.saved_strategies:
            strategies = [(name, self.saved_strategies[name])]
        return strategies

    def _game_passes_strategy_live(
        self,
        filters,
        *,
        odds_map,
        chance_map,
        rating_home,
        rating_away,
        xg_home,
        xg_away,
        country,
        league,
        games_count=None,
        rd_home=None,
        rd_away=None,
        vol_home=None,
        vol_away=None,
        p_home=None,
        p_draw=None,
        p_away=None,
    ):
        """Live-Parität zu Backtest; fehlende Chance/Min-Spiele nicht hart blockieren."""
        markets = strat.selected_markets_from_filters(filters)
        if not markets:
            # Ohne Marktauswahl: alle Märkte mit vorhandener Quote prüfen
            markets = [m for m, o in odds_map.items() if o is not None]
        xg_ctx = {
            "xg_h": xg_home, "xg_a": xg_away,
            "xg_glicko_h": xg_home, "xg_glicko_a": xg_away,
            "rating_h": rating_home, "rating_a": rating_away,
            "rd_h": rd_home, "rd_a": rd_away,
            "vol_h": vol_home, "vol_a": vol_away,
            "p_home": p_home, "p_draw": p_draw, "p_away": p_away,
        }
        matched = []
        for market in markets:
            odds = odds_map.get(market)
            if odds is None:
                continue
            chance = chance_map.get(market)
            if strat.match_prematch_filters(
                filters,
                market=market,
                odds=odds,
                chance=chance,
                rating_h=rating_home,
                rating_a=rating_away,
                country=country,
                league=league,
                games_count=games_count,
                xg_ctx=xg_ctx,
                allow_missing_stats=True,
            ):
                matched.append(market)
        return matched

    def _get_odds_bundle_for_game(self, game_id, row=None):
        """Quotes aus Row oder DB (ohne API)."""
        empty = {m: None for m in strat.MARKET_DEFS}
        if row is not None:
            d = dict(row) if not isinstance(row, dict) else row
            return {m: strat.pick_odds(d, m, "closing") for m in strat.MARKET_DEFS}
        if not game_id:
            return empty
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            r = conn.execute(
                """SELECT odd_home, odd_draw, odd_away,
                          odd_over_25, odd_under_25, odd_over_35, odd_under_35,
                          odd_over_45, odd_under_45,
                          odd_open_home, odd_open_draw, odd_open_away,
                          odd_open_over_25, odd_open_under_25,
                          odd_open_over_35, odd_open_under_35,
                          odd_open_over_45, odd_open_under_45
                   FROM game_odds_pivoted WHERE game_id = ?""",
                (int(game_id),),
            ).fetchone()
            conn.close()
            if r:
                return {m: strat.pick_odds(dict(r), m, "closing") for m in strat.MARKET_DEFS}
        except Exception as e:
            print(f"[WARNING] odds bundle: {e}")
        return empty

    def _load_upcoming_games_bulk(self, limit=1500):
        """Bevorstehende Spiele (ab gestern); kein Join auf fertige games-Zeilen."""
        from datetime import timedelta as _td

        since = (datetime.now() - _td(days=1)).strftime("%Y-%m-%d")
        until = (datetime.now() + _td(days=14)).strftime("%Y-%m-%d")
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT
                u.id AS game_id,
                COALESCE(u.date, u.date_utc) AS date,
                u.status AS status,
                u.status_name AS status_name,
                u.home_team_name,
                u.away_team_name,
                u.country_name,
                u.league_name,
                u.league_id,
                gl.home_xg AS xg_home,
                gl.away_xg AS xg_away,
                gl.home_rating AS rating_home,
                gl.away_rating AS rating_away,
                gl.home_rd AS rd_home,
                gl.away_rd AS rd_away,
                gl.home_volatility AS vol_home,
                gl.away_volatility AS vol_away,
                gl.home_win_probability AS p_home,
                gl.draw_probability AS p_draw,
                gl.away_win_probability AS p_away,
                o.odd_home, o.odd_draw, o.odd_away,
                o.odd_over_25, o.odd_under_25,
                o.odd_over_35, o.odd_under_35,
                o.odd_over_45, o.odd_under_45,
                o.odd_open_home, o.odd_open_draw, o.odd_open_away,
                o.odd_open_over_25, o.odd_open_under_25,
                o.odd_open_over_35, o.odd_open_under_35,
                o.odd_open_over_45, o.odd_open_under_45
            FROM upcoming_games u
            LEFT JOIN game_glicko gl ON gl.game_id = u.id
            LEFT JOIN game_odds_pivoted o ON o.game_id = u.id
            WHERE substr(replace(COALESCE(u.date, ''), 'T', ' '), 1, 10) BETWEEN ? AND ?
              AND (u.home_ft_result IS NULL OR u.away_ft_result IS NULL)
              AND IFNULL(u.status, 0) NOT IN (7, 8, 9, 10, 15)
              AND (
                    lower(COALESCE(u.status_name, '')) LIKE '%not started%'
                    OR lower(COALESCE(u.status_name, '')) LIKE '%scheduled%'
                    OR IFNULL(u.status, 0) IN (0, 1)
                  )
              AND lower(COALESCE(u.status_name, '')) NOT LIKE '%finished%'
              AND lower(COALESCE(u.status_name, '')) NOT LIKE '%1st half%'
              AND lower(COALESCE(u.status_name, '')) NOT LIKE '%2nd half%'
              AND (
                    o.odd_home IS NOT NULL OR o.odd_away IS NOT NULL
                    OR o.odd_over_25 IS NOT NULL OR o.odd_under_25 IS NOT NULL
                    OR o.odd_draw IS NOT NULL
                    OR o.odd_open_home IS NOT NULL OR o.odd_open_over_25 IS NOT NULL
                  )
            ORDER BY date ASC
            LIMIT ?
            """,
            (since, until, limit),
        ).fetchall()
        conn.close()

        if len(rows) >= 5:
            return rows

        api_rows = self._load_upcoming_from_api(limit=min(limit, 400))
        return api_rows if api_rows else rows

    def _load_upcoming_from_api(self, limit=400):
        """Heutige Spiele von der API (nur nicht beendet), Odds/Glicko aus DB."""
        live_service = self.services.get("live_service") if isinstance(self.services, dict) else None
        if live_service is None:
            try:
                from services.live_service import LiveService
                from api.sstats_client import SStatsClient
                from config import config as cfg
                client = self.services.get("client") if isinstance(self.services, dict) else None
                if client is None:
                    client = SStatsClient(base_url=cfg.BASE_URL, api_key=getattr(cfg, "API_KEY", None))
                live_service = LiveService(client)
            except Exception as e:
                print(f"[WARNING] LiveService nicht verfügbar: {e}")
                return []

        # Rohdaten von der API (mit Datum), nicht nur Game-Model
        finished_status = {7, 8, 9, 10, 12, 13, 14, 15, 17, 18}
        candidates = []
        try:
            from config import config as cfg
            client = self.services.get("client") if isinstance(self.services, dict) else None
            if client is None:
                client = getattr(live_service, "client", None)
            params = {"Today": True}
            try:
                params["TimeZone"] = getattr(cfg, "TIMEZONE")
            except Exception:
                pass
            raw = client.get_games(params) if client else []
        except Exception as e:
            print(f"[WARNING] API Upcoming laden fehlgeschlagen: {e}")
            raw = []

        for item in raw or []:
            if not isinstance(item, dict):
                continue
            gid = item.get("id") or item.get("Id") or item.get("gameId")
            status = item.get("status") or item.get("statusName") or item.get("state")
            try:
                status_i = int(status) if status is not None and str(status).strip() != "" else 0
            except (TypeError, ValueError):
                status_i = 0
            if status_i in finished_status or status_i not in (0, 1):
                continue
            if not gid:
                continue

            home = ""
            away = ""
            if isinstance(item.get("homeTeam"), dict):
                home = item["homeTeam"].get("name") or ""
            if isinstance(item.get("awayTeam"), dict):
                away = item["awayTeam"].get("name") or ""
            home = home or item.get("homeTeamName") or item.get("home_team") or ""
            away = away or item.get("awayTeamName") or item.get("away_team") or ""

            country = None
            league_name = None
            season = item.get("season")
            if isinstance(season, dict) and isinstance(season.get("league"), dict):
                league_name = season["league"].get("name")
                lc = season["league"].get("country")
                country = lc.get("name") if isinstance(lc, dict) else lc

            candidates.append({
                "game_id": int(gid),
                "date": item.get("date") or item.get("dateUtc") or item.get("date_utc"),
                "status": status_i,
                "status_name": str(status),
                "home_team_name": home,
                "away_team_name": away,
                "country_name": country or "",
                "league_name": league_name or "",
                "league_id": None,
            })
            if len(candidates) >= limit:
                break

        if not candidates and live_service is not None:
            # Fallback auf LiveService-Mapping ohne Datum
            try:
                for g in list(live_service.fetch_live_games() or []):
                    gid = getattr(g, "id", None) if not isinstance(g, dict) else g.get("id")
                    status = getattr(g, "status", None) if not isinstance(g, dict) else g.get("status")
                    try:
                        status_i = int(status) if status is not None and str(status).strip() != "" else 0
                    except (TypeError, ValueError):
                        status_i = 0
                    if status_i in finished_status or status_i not in (0, 1) or not gid:
                        continue
                    if isinstance(g, dict):
                        candidates.append({
                            "game_id": int(gid),
                            "date": g.get("date"),
                            "status": status_i,
                            "status_name": g.get("status_text"),
                            "home_team_name": g.get("home_team") or "",
                            "away_team_name": g.get("away_team") or "",
                            "country_name": g.get("country") or "",
                            "league_name": g.get("league_name") or "",
                            "league_id": None,
                        })
                    else:
                        candidates.append({
                            "game_id": int(gid),
                            "date": None,
                            "status": status_i,
                            "status_name": getattr(g, "status_text", None),
                            "home_team_name": getattr(g, "home_team", "") or "",
                            "away_team_name": getattr(g, "away_team", "") or "",
                            "country_name": getattr(g, "country", "") or "",
                            "league_name": getattr(g, "league_name", "") or "",
                            "league_id": None,
                        })
                    if len(candidates) >= limit:
                        break
            except Exception as e:
                print(f"[WARNING] LiveService-Fallback: {e}")

        if not candidates:
            return []

        ids = [c["game_id"] for c in candidates]
        odds_by_id = {}
        glicko_by_id = {}
        finished_ids = set()
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            for i in range(0, len(ids), 400):
                chunk = ids[i:i + 400]
                ph = ",".join("?" * len(chunk))
                for r in conn.execute(
                    f"""SELECT game_id, odd_home, odd_draw, odd_away,
                               odd_over_25, odd_under_25, odd_over_35, odd_under_35,
                               odd_over_45, odd_under_45,
                               odd_open_home, odd_open_draw, odd_open_away,
                               odd_open_over_25, odd_open_under_25,
                               odd_open_over_35, odd_open_under_35,
                               odd_open_over_45, odd_open_under_45
                        FROM game_odds_pivoted WHERE game_id IN ({ph})""",
                    chunk,
                ).fetchall():
                    odds_by_id[r["game_id"]] = dict(r)
                for r in conn.execute(
                    f"""SELECT game_id, home_xg, away_xg, home_rating, away_rating
                        FROM game_glicko WHERE game_id IN ({ph})""",
                    chunk,
                ).fetchall():
                    glicko_by_id[r["game_id"]] = dict(r)
                for r in conn.execute(
                    f"""SELECT id, date, status, home_ft_result, away_ft_result
                        FROM games WHERE id IN ({ph})""",
                    chunk,
                ).fetchall():
                    st = r["status"]
                    try:
                        st_i = int(st) if st is not None else 0
                    except (TypeError, ValueError):
                        st_i = 0
                    if r["home_ft_result"] is not None or r["away_ft_result"] is not None or st_i in finished_status:
                        finished_ids.add(r["id"])
                    elif r["date"]:
                        for c in candidates:
                            if c["game_id"] == r["id"]:
                                c["date"] = r["date"]
            conn.close()
        except Exception as e:
            print(f"[WARNING] API-Anreicherung DB: {e}")

        out = []
        for c in candidates:
            gid = c["game_id"]
            if gid in finished_ids:
                continue
            gl = glicko_by_id.get(gid) or {}
            od = odds_by_id.get(gid) or {}
            row = {
                **c,
                "xg_home": gl.get("home_xg"),
                "xg_away": gl.get("away_xg"),
                "rating_home": gl.get("home_rating"),
                "rating_away": gl.get("away_rating"),
                "odd_home": od.get("odd_home"),
                "odd_draw": od.get("odd_draw"),
                "odd_away": od.get("odd_away"),
                "odd_over_25": od.get("odd_over_25"),
                "odd_under_25": od.get("odd_under_25"),
                "odd_over_35": od.get("odd_over_35"),
                "odd_under_35": od.get("odd_under_35"),
                "odd_over_45": od.get("odd_over_45"),
                "odd_under_45": od.get("odd_under_45"),
                "odd_open_home": od.get("odd_open_home"),
                "odd_open_draw": od.get("odd_open_draw"),
                "odd_open_away": od.get("odd_open_away"),
                "odd_open_over_25": od.get("odd_open_over_25"),
                "odd_open_under_25": od.get("odd_open_under_25"),
                "odd_open_over_35": od.get("odd_open_over_35"),
                "odd_open_under_35": od.get("odd_open_under_35"),
                "odd_open_over_45": od.get("odd_open_over_45"),
                "odd_open_under_45": od.get("odd_open_under_45"),
            }
            if any(row.get(k) is not None for k in (
                "odd_home", "odd_away", "odd_draw", "odd_over_25", "odd_under_25"
            )):
                out.append(row)
        print(f"[INFO] API Upcoming für Strategie: {len(out)} nicht beendete Spiele mit Quotes")
        return out

    def check_matches_against_strategies(self):
        """Zukünftige Spiele gegen aktuelle Filter prüfen (schnell, nur DB)."""
        try:
            filters = self.get_current_filters()
            markets = strat.selected_markets_from_filters(filters)
            has_signal = any([
                markets,
                filters.get("glicko_home_min"), filters.get("glicko_home_max"),
                filters.get("glicko_away_min"), filters.get("glicko_away_max"),
                filters.get("use_xg_comparison") and filters.get("xg_comparison_value"),
                filters.get("odds_home_min"), filters.get("odds_home_max"),
                filters.get("odds_draw_min"), filters.get("odds_draw_max"),
                filters.get("odds_away_min"), filters.get("odds_away_max"),
                filters.get("odds_over_min"), filters.get("odds_over_max"),
                filters.get("odds_under_min"), filters.get("odds_under_max"),
                filters.get("odds_over35_min"), filters.get("odds_over35_max"),
                filters.get("odds_under35_min"), filters.get("odds_under35_max"),
                filters.get("odds_over45_min"), filters.get("odds_over45_max"),
                filters.get("odds_under45_min"), filters.get("odds_under45_max"),
                filters.get("chance_min"), filters.get("chance_max"),
                filters.get("country_filter"), filters.get("league_filter"),
            ])
            if not has_signal:
                messagebox.showinfo(
                    "Info",
                    "Bitte wähle mindestens einen Markt und/oder Filter, "
                    "damit zukünftige Matches geprüft werden können.",
                )
                return

            strategies_to_check = self._strategies_to_check()
            # Wenn geladene Strategie: trotzdem aktuelle Filter mitnutzen, falls gewünscht?
            # Aktuell: geladene Strategie ODER aktuelle Filter (siehe _strategies_to_check)

            rows = self._load_upcoming_games_bulk(limit=1500)
            if not rows:
                messagebox.showinfo(
                    "Info",
                    "Keine bevorstehenden Spiele mit Quotes in der DB gefunden.\n"
                    "Bitte Upcoming/Odds zuerst laden.",
                )
                return

            matching_games = []
            checked = 0

            for row in rows:
                checked += 1
                d = dict(row)
                game_id = d.get("game_id")
                odds_bundle = self._get_odds_bundle_for_game(game_id, row=d)
                rating_home = d.get("rating_home")
                rating_away = d.get("rating_away")
                xg_home = d.get("xg_home")
                xg_away = d.get("xg_away")
                country = d.get("country_name") or ""
                league = d.get("league_name") or ""

                odds_open_bundle = {
                    m: strat.pick_odds(d, m, "opening") for m in strat.MARKET_DEFS
                }
                for strategy_name, strategy_data in strategies_to_check:
                    f = strategy_data.get("filters", {})
                    ot = f.get("odds_type") or "closing"
                    odds_for_match = (
                        odds_open_bundle if ot == "opening" else odds_bundle
                    )
                    matched_markets = self._game_passes_strategy_live(
                        f,
                        odds_map=odds_for_match,
                        chance_map={},
                        rating_home=rating_home,
                        rating_away=rating_away,
                        xg_home=xg_home,
                        xg_away=xg_away,
                        country=country,
                        league=league,
                        rd_home=d.get("rd_home"),
                        rd_away=d.get("rd_away"),
                        vol_home=d.get("vol_home"),
                        vol_away=d.get("vol_away"),
                        p_home=d.get("p_home"),
                        p_draw=d.get("p_draw"),
                        p_away=d.get("p_away"),
                    )
                    if matched_markets:
                        # xROI / Open / Close für ersten gematchten Markt
                        primary = matched_markets[0]
                        o_open = odds_open_bundle.get(primary)
                        o_close = odds_bundle.get(primary)
                        matching_games.append({
                            "game_id": game_id,
                            "home": d.get("home_team_name") or "",
                            "away": d.get("away_team_name") or "",
                            "country": country,
                            "league": league,
                            "date": d.get("date"),
                            "strategy": strategy_name,
                            "markets": ", ".join(matched_markets),
                            "xg_home": xg_home,
                            "xg_away": xg_away,
                            "xg_home_glicko": xg_home,
                            "xg_away_glicko": xg_away,
                            "rating_home": rating_home,
                            "rating_away": rating_away,
                            "home_quote": odds_bundle.get("Home"),
                            "draw_quote": odds_bundle.get("Draw"),
                            "away_quote": odds_bundle.get("Away"),
                            "over_25_quote": odds_bundle.get("Over 2.5"),
                            "under_25_quote": odds_bundle.get("Under 2.5"),
                            "odds_opening": o_open,
                            "odds_closing": o_close,
                            "xroi_pct": strat.compute_xroi_pct(o_open, o_close),
                            "primary_market": primary,
                        })

            if not matching_games:
                messagebox.showinfo(
                    "Info",
                    f"Keine passenden zukünftigen Spiele.\n\n"
                    f"Geprüft: {checked} noch nicht beendete Spiele mit Quotes.\n"
                    f"(Bereits gespielte Matches werden ausgefiltert.)\n"
                    f"Tipp: Markt wählen; Glicko/xG-Filter lockern.",
                )
                return

            self.display_matching_games(matching_games)

        except Exception as e:
            messagebox.showerror("Fehler", f"Fehler beim Prüfen der Matches: {e}")
            import traceback
            traceback.print_exc()

    def _get_odds_for_game(self, game_id):
        """Get odds from database first, fallback to API if not found (same logic as Live Match)"""
        if not game_id:
            return None, None, None, None, None
        
        try:
            game_id_int = int(game_id)
            
            # First try to get odds from database (using pivoted view)
            try:
                conn = sqlite3.connect(self.db_path)
                conn.row_factory = sqlite3.Row
                
                # Get odds from pivoted view (much simpler!)
                row = conn.execute(
                    "SELECT odd_home, odd_draw, odd_away, odd_over_25, odd_under_25 FROM game_odds_pivoted WHERE game_id = ?",
                    (game_id_int,)
                ).fetchone()
                conn.close()
                
                # If we have odds in DB, use them
                if row:
                    odd_home = row['odd_home']
                    odd_draw = row['odd_draw']
                    odd_away = row['odd_away']
                    odd_over = row['odd_over_25']
                    odd_under = row['odd_under_25']
                    
                    return odd_home, odd_draw, odd_away, odd_over, odd_under
            except Exception as e:
                print(f"[WARNING] Error loading odds from DB for game {game_id}: {e}")
            
            # Fallback to API if not in database
            client = self.services.get('client')
            if not client:
                # Try to create client if not available
                try:
                    from api.sstats_client import SStatsClient
                    from config import config as cfg
                    client = SStatsClient(base_url=cfg.BASE_URL, api_key=getattr(cfg, 'API_KEY', None))
                except Exception as e:
                    print(f"[WARNING] Could not create API client: {e}")
                    return None, None, None, None, None
            
            odds_data = client.get_game_odds(game_id_int, bookmaker_id=None, opening=False)
            
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
            
            return odd_home, odd_draw, odd_away, odd_over, odd_under
            
        except Exception as e:
            print(f"[WARNING] Error loading odds for game {game_id}: {e}")
            return None, None, None, None, None
    
    def display_matching_games(self, matching_games: List[Dict]):
        """Display matches that match saved strategies"""
        if not matching_games:
            messagebox.showinfo("Info", "Keine Matches gefunden, die zu gespeicherten Strategien passen.")
            return
        
        dialog = tk.Toplevel(self)
        dialog.title("Passende Matches (bevorstehend)")
        dialog.geometry("1500x720")
        dialog.minsize(1000, 480)
        dialog.resizable(True, True)
        
        tk.Label(
            dialog,
            text=f"Gefundene Matches: {len(matching_games)}  ·  xROI = (Open−Close)/Close×100",
            font=("Arial", 12, "bold"),
        ).pack(pady=10)
        
        tree_frame = ttk.Frame(dialog)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        scrollbar_y = ttk.Scrollbar(tree_frame, orient='vertical')
        scrollbar_x = ttk.Scrollbar(tree_frame, orient='horizontal')
        
        columns = ("game_id", "date", "home", "away", "country", "league", "strategy", "markets",
                   "xg_home_glicko", "xg_away_glicko", "rating_h", "rating_a",
                   "odds_open", "odds_close", "xroi",
                   "home_quote", "draw_quote", "away_quote", "over_25_quote", "under_25_quote")
        tree = ttk.Treeview(tree_frame, columns=columns, show='headings',
                           yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)
        
        tree.heading('game_id', text='ID')
        tree.heading('date', text='Datum')
        tree.heading('home', text='Home')
        tree.heading('away', text='Away')
        tree.heading('country', text='Land')
        tree.heading('league', text='Liga')
        tree.heading('strategy', text='Strategie')
        tree.heading('markets', text='Märkte')
        tree.heading('xg_home_glicko', text='xG H')
        tree.heading('xg_away_glicko', text='xG A')
        tree.heading('rating_h', text='Rating H')
        tree.heading('rating_a', text='Rating A')
        tree.heading('odds_open', text='Open')
        tree.heading('odds_close', text='Close')
        tree.heading('xroi', text='xROI %')
        tree.heading('home_quote', text='Quote H')
        tree.heading('draw_quote', text='Quote D')
        tree.heading('away_quote', text='Quote A')
        tree.heading('over_25_quote', text='Quote O2.5')
        tree.heading('under_25_quote', text='Quote U2.5')
        
        tree.column('game_id', width=60, minwidth=40)
        tree.column('date', width=130, minwidth=90)
        tree.column('home', width=120, minwidth=80)
        tree.column('away', width=120, minwidth=80)
        tree.column('country', width=90, minwidth=60)
        tree.column('league', width=140, minwidth=80)
        tree.column('strategy', width=130, minwidth=80)
        tree.column('markets', width=110, minwidth=70)
        tree.column('xg_home_glicko', width=70, minwidth=50)
        tree.column('xg_away_glicko', width=70, minwidth=50)
        tree.column('rating_h', width=70, minwidth=50)
        tree.column('rating_a', width=70, minwidth=50)
        tree.column('odds_open', width=70, minwidth=50)
        tree.column('odds_close', width=70, minwidth=50)
        tree.column('xroi', width=75, minwidth=55)
        tree.column('home_quote', width=65, minwidth=45)
        tree.column('draw_quote', width=65, minwidth=45)
        tree.column('away_quote', width=65, minwidth=45)
        tree.column('over_25_quote', width=75, minwidth=50)
        tree.column('under_25_quote', width=75, minwidth=50)
        
        scrollbar_y.config(command=tree.yview)
        scrollbar_x.config(command=tree.xview)
        
        # Use grid layout for proper scrollbar positioning
        tree.grid(row=0, column=0, sticky='nsew')
        scrollbar_y.grid(row=0, column=1, sticky='ns')
        scrollbar_x.grid(row=1, column=0, sticky='ew')
        
        # Configure grid weights for proper resizing
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        def on_match_activate(event=None):
            sel = tree.selection()
            if not sel:
                return
            values = tree.item(sel[0], "values")
            if not values:
                return
            try:
                game_id = int(values[0])
            except (ValueError, TypeError, IndexError):
                return
            # Wie bei Today's Matches → Analytics-Tab öffnen
            self._show_match_analysis(game_id)

        tree.bind("<Double-1>", on_match_activate)
        tree.bind("<Return>", on_match_activate)
        
        for match in matching_games:
            xg_h = match.get('xg_home_glicko', match.get('xg_home'))
            xg_a = match.get('xg_away_glicko', match.get('xg_away'))
            raw_date = match.get('date') or ''
            date_str = '-'
            if raw_date:
                try:
                    s = str(raw_date).replace('T', ' ')
                    # z.B. 2026-07-12 15:00:00 → 12.07.2026 15:00
                    if len(s) >= 16 and s[4] == '-' and s[7] == '-':
                        date_str = f"{s[8:10]}.{s[5:7]}.{s[0:4]} {s[11:16]}"
                    elif len(s) >= 10 and s[4] == '-' and s[7] == '-':
                        date_str = f"{s[8:10]}.{s[5:7]}.{s[0:4]}"
                    else:
                        date_str = s[:16]
                except Exception:
                    date_str = str(raw_date)[:16]
            xo = match.get("odds_opening")
            xc = match.get("odds_closing")
            xr = match.get("xroi_pct")
            tree.insert('', 'end', values=(
                match['game_id'],
                date_str,
                match['home'],
                match['away'],
                match['country'],
                match['league'],
                match['strategy'],
                match.get('markets', '-'),
                f"{xg_h:.2f}" if xg_h is not None else "-",
                f"{xg_a:.2f}" if xg_a is not None else "-",
                f"{match['rating_home']:.0f}" if match.get('rating_home') else "-",
                f"{match['rating_away']:.0f}" if match.get('rating_away') else "-",
                f"{xo:.2f}" if xo is not None and xo > 0 else "-",
                f"{xc:.2f}" if xc is not None and xc > 0 else "-",
                f"{xr:+.1f}" if xr is not None else "-",
                f"{match['home_quote']:.2f}" if match.get('home_quote') is not None and match['home_quote'] > 0 else "-",
                f"{match['draw_quote']:.2f}" if match.get('draw_quote') is not None and match['draw_quote'] > 0 else "-",
                f"{match['away_quote']:.2f}" if match.get('away_quote') is not None and match['away_quote'] > 0 else "-",
                f"{match['over_25_quote']:.2f}" if match.get('over_25_quote') is not None and match['over_25_quote'] > 0 else "-",
                f"{match['under_25_quote']:.2f}" if match.get('under_25_quote') is not None and match['under_25_quote'] > 0 else "-"
            ))
        
        btn_row = ttk.Frame(dialog)
        btn_row.pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(btn_row, text="📊 Analytics öffnen", command=on_match_activate).pack(side=tk.LEFT)
        ttk.Button(btn_row, text="Schließen", command=dialog.destroy).pack(side=tk.RIGHT)
    
    def import_excel_games(self):
        """Import games from Excel file and check against strategies"""
        from tkinter import filedialog
        try:
            import pandas as pd
        except ImportError:
            messagebox.showerror("Fehler", "pandas nicht installiert.\n\nBitte installieren Sie:\npip install pandas openpyxl")
            return
        
        # Ask user to select Excel file
        file_path = filedialog.askopenfilename(
            title="Excel-Datei auswählen",
            filetypes=[("Excel files", "*.xlsx *.xls"), ("All files", "*.*")]
        )
        
        if not file_path:
            return
        
        try:
            # Read Excel file
            df = pd.read_excel(file_path)
            print(f"[DEBUG] Excel columns: {list(df.columns)}")
            
            # Fix duplicate column names by adding suffix
            if df.columns.duplicated().any():
                print(f"[WARNING] Duplicate columns found, renaming...")
                # Rename duplicate columns by adding suffix
                new_columns = []
                seen = {}
                for col in df.columns:
                    if col in seen:
                        seen[col] += 1
                        new_columns.append(f"{col}_{seen[col]}")
                    else:
                        seen[col] = 0
                        new_columns.append(col)
                df.columns = new_columns
                print(f"[DEBUG] Fixed columns: {list(df.columns)}")
            
            # Try to identify game columns - common column names
            # Look for columns that might contain game data
            game_id_col = None
            home_team_col = None
            away_team_col = None
            date_col = None
            
            # Common column name variations
            for col in df.columns:
                col_lower = str(col).lower()
                if 'id' in col_lower and game_id_col is None:
                    game_id_col = col
                elif 'home' in col_lower and ('team' in col_lower or 'name' in col_lower):
                    if home_team_col is None:
                        home_team_col = col
                elif 'away' in col_lower and ('team' in col_lower or 'name' in col_lower):
                    if away_team_col is None:
                        away_team_col = col
                elif 'date' in col_lower or 'datum' in col_lower:
                    if date_col is None:
                        date_col = col
            
            # If not found, try first few columns
            if not game_id_col and len(df.columns) > 0:
                game_id_col = df.columns[0]
            if not home_team_col and len(df.columns) > 1:
                home_team_col = df.columns[1]
            if not away_team_col and len(df.columns) > 2:
                away_team_col = df.columns[2]
            
            if not home_team_col or not away_team_col:
                messagebox.showerror("Fehler", "Konnte keine Team-Spalten in der Excel-Datei finden.\n\nErwartete Spalten: Home Team, Away Team (oder ähnlich)")
                return
            
            # Convert Excel data to game list
            excel_games = []
            for idx, row in df.iterrows():
                try:
                    # Get game ID - try to extract from first column or use row index
                    game_id = None
                    if game_id_col:
                        game_id_val = row.get(game_id_col)
                        if pd.notna(game_id_val):
                            try:
                                game_id = int(float(game_id_val))
                            except (ValueError, TypeError):
                                pass
                    
                    # If no game ID, skip or use a placeholder
                    if not game_id:
                        # Try to find game in database by team names
                        home_team_name = str(row.get(home_team_col, '')).strip()
                        away_team_name = str(row.get(away_team_col, '')).strip()
                        
                        if not home_team_name or not away_team_name:
                            continue
                        
                        # Try to find game in database
                        conn = sqlite3.connect(self.db_path)
                        conn.row_factory = sqlite3.Row
                        game_row = conn.execute("""
                            SELECT id FROM games 
                            WHERE home_team_name = ? AND away_team_name = ?
                            ORDER BY date DESC
                            LIMIT 1
                        """, (home_team_name, away_team_name)).fetchone()
                        conn.close()
                        
                        if game_row:
                            game_id = game_row['id']
                        else:
                            # Create a temporary ID for games not in DB
                            game_id = f"excel_{idx}"
                    
                    # Get date if available
                    game_date = None
                    if date_col:
                        date_val = row.get(date_col)
                        if pd.notna(date_val):
                            try:
                                if isinstance(date_val, pd.Timestamp):
                                    game_date = date_val.isoformat()
                                else:
                                    game_date = str(date_val)
                            except:
                                pass
                    
                    game_dict = {
                        'id': game_id,
                        'home_team': str(row.get(home_team_col, '')).strip(),
                        'away_team': str(row.get(away_team_col, '')).strip(),
                        'date': game_date,
                        'from_excel': True
                    }
                    excel_games.append(game_dict)
                except Exception as e:
                    print(f"[WARNING] Error processing row {idx}: {e}")
                    continue
            
            if not excel_games:
                messagebox.showinfo("Info", "Keine Spiele in der Excel-Datei gefunden.")
                return
            
            # Check games against strategies
            self._check_excel_games_against_strategies(excel_games)
            
        except ImportError:
            messagebox.showerror("Fehler", "pandas oder openpyxl nicht installiert.\n\nBitte installieren Sie:\npip install pandas openpyxl")
        except Exception as e:
            messagebox.showerror("Fehler", f"Fehler beim Lesen der Excel-Datei:\n{e}")
            import traceback
            traceback.print_exc()
    
    def _check_excel_games_against_strategies(self, excel_games):
        """Check Excel games against strategies"""
        # Use same logic as check_matches_against_strategies but for Excel games
        matching_games = []
        client = self.services.get('client')
        
        if not client:
            messagebox.showerror("Fehler", "API Client nicht verfügbar.")
            return
        
        # Determine which strategies to check
        strategies_to_check = []
        if hasattr(self, 'current_strategy_name') and self.current_strategy_name:
            if self.current_strategy_name in self.saved_strategies:
                strategies_to_check = [(self.current_strategy_name, self.saved_strategies[self.current_strategy_name])]
            else:
                current_filters = self.get_current_filters()
                strategies_to_check = [("Aktuelle Filter", {'filters': current_filters})]
        elif not self.saved_strategies:
            current_filters = self.get_current_filters()
            has_filters = any([
                current_filters.get('glicko_home_min'), current_filters.get('glicko_home_max'),
                current_filters.get('glicko_away_min'), current_filters.get('glicko_away_max'),
                current_filters.get('use_xg_comparison') and current_filters.get('xg_comparison_value'),
                current_filters.get('odds_home_min'), current_filters.get('odds_home_max'),
            ])
            if has_filters:
                strategies_to_check = [("Aktuelle Filter", {'filters': current_filters})]
            else:
                messagebox.showinfo("Info", "Bitte setze zuerst Filter oder speichere eine Strategie.")
                return
        else:
            strategies_to_check = [(name, data) for name, data in self.saved_strategies.items()]
        
        if not strategies_to_check:
            messagebox.showinfo("Info", "Keine Strategien oder Filter gesetzt.")
            return
        
        # Process each Excel game
        for game in excel_games:
            game_id = game.get('id')
            if not game_id or isinstance(game_id, str) and game_id.startswith('excel_'):
                # Game not in database, try to get Glicko from API
                home_team = game.get('home_team')
                away_team = game.get('away_team')
                
                # Try to find game in database by team names
                try:
                    conn = sqlite3.connect(self.db_path)
                    conn.row_factory = sqlite3.Row
                    game_row = conn.execute("""
                        SELECT id FROM games 
                        WHERE home_team_name = ? AND away_team_name = ?
                        ORDER BY date DESC
                        LIMIT 1
                    """, (home_team, away_team)).fetchone()
                    conn.close()
                    
                    if game_row:
                        game_id = game_row['id']
                    else:
                        # Game not found, skip or try to get from API
                        continue
                except:
                    continue
            
            try:
                # Get Glicko data for this game - first from DB, then API
                xg_home = None
                xg_away = None
                rating_home = None
                rating_away = None
                
                # Try database first
                try:
                    conn = sqlite3.connect(self.db_path)
                    conn.row_factory = sqlite3.Row
                    glicko_row = conn.execute(
                        "SELECT home_xg, away_xg, home_rating, away_rating FROM game_glicko WHERE game_id = ?",
                        (game_id,)
                    ).fetchone()
                    conn.close()
                    
                    if glicko_row:
                        xg_home = glicko_row['home_xg']
                        xg_away = glicko_row['away_xg']
                        rating_home = glicko_row['home_rating']
                        rating_away = glicko_row['away_rating']
                except Exception as e:
                    print(f"[WARNING] Error loading Glicko from DB for game {game_id}: {e}")
                
                # Fallback to API if not in database
                if xg_home is None or xg_away is None:
                    try:
                        glicko_data = client.get_game_glicko(str(game_id))
                        if glicko_data and 'glicko' in glicko_data:
                            glicko = glicko_data['glicko']
                            xg_home = glicko.get('homeXg')
                            xg_away = glicko.get('awayXg')
                            rating_home = glicko.get('homeRating')
                            rating_away = glicko.get('awayRating')
                    except Exception as e:
                        print(f"[WARNING] Error loading Glicko from API for game {game_id}: {e}")
                
                # Check against strategies (gleiche Logik wie Live)
                odds_bundle = self._get_odds_bundle_for_game(game_id)
                for strategy_name, strategy_data in strategies_to_check:
                    filters = strategy_data.get('filters', {})
                    matched_markets = self._game_passes_strategy_live(
                        filters,
                        odds_map=odds_bundle,
                        chance_map={},
                        rating_home=rating_home,
                        rating_away=rating_away,
                        xg_home=xg_home,
                        xg_away=xg_away,
                        country=game.get('country'),
                        league=game.get('league_name') or game.get('league'),
                    )
                    if matched_markets:
                        matching_games.append({
                            'game_id': game_id,
                            'home': game.get('home_team'),
                            'away': game.get('away_team'),
                            'country': game.get('country') or '',
                            'league': game.get('league_name') or game.get('league') or '',
                            'strategy': strategy_name,
                            'markets': ", ".join(matched_markets),
                            'xg_home': xg_home,
                            'xg_away': xg_away,
                            'xg_home_glicko': xg_home,
                            'xg_away_glicko': xg_away,
                            'rating_home': rating_home,
                            'rating_away': rating_away,
                            'home_quote': odds_bundle.get('Home'),
                            'draw_quote': odds_bundle.get('Draw'),
                            'away_quote': odds_bundle.get('Away'),
                            'over_25_quote': odds_bundle.get('Over 2.5'),
                            'under_25_quote': odds_bundle.get('Under 2.5'),
                        })
            except Exception as e:
                print(f"[WARNING] Error processing Excel game {game_id}: {e}")
                continue
        
        # Display matching games
        if matching_games:
            self.display_matching_games(matching_games)
        else:
            messagebox.showinfo("Info", f"Keine passenden Spiele gefunden.\n\nGeprüft: {len(excel_games)} Spiele aus Excel")

