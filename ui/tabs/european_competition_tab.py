"""European Competitions Tab: Champions League, Europa League, Conference League."""
import sqlite3
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from ui.tabs.league_tab import LeagueTab
from services.european_competition_service import (
    EURO_COMPETITIONS,
    EURO_LEAGUE_IDS,
    EURO_PHASES,
    competition_by_id,
    decode_row_id,
    encode_row_id,
    ensure_european_league_rows,
    fetch_finished_games,
    fetch_today_games,
    phase_from_label,
    stats_for_league_year,
    today_counts_by_phase,
)


class EuropeanCompetitionTab(LeagueTab):
    """League-Tab-Format, nur UEFA-Klubwettbewerbe inkl. Quali/Playoffs und Over 5.5."""

    def __init__(self, parent, services):
        self.euro_ids = list(EURO_LEAGUE_IDS)
        self.years_to_show = ["2024", "2025", "2026"]
        super().__init__(parent, services)
        self.years_to_show = ["2024", "2025", "2026"]
        self.year = "2026"
        for lid in self.euro_ids:
            self.current_seasons.setdefault(int(lid), 2026)
            for phase_key, _label in EURO_PHASES:
                self.current_seasons.setdefault(encode_row_id(lid, phase_key), 2026)
        self._retitle()
        self._setup_euro_extra_tabs()
        try:
            self.filter_has_data_var.set(False)
        except Exception:
            pass

    def _retitle(self):
        def walk(widget):
            for child in widget.winfo_children():
                try:
                    if isinstance(child, tk.Label) and "League Information" in str(child.cget("text")):
                        child.config(text="European Competitions  ·  CL / EL / Conference")
                        return True
                except Exception:
                    pass
                if walk(child):
                    return True
            return False
        walk(self)

    def _setup_euro_extra_tabs(self):
        if not hasattr(self, "notebook"):
            return
        tab_55 = tk.Frame(self.notebook)
        self.notebook.add(tab_55, text="5.5 Goals")
        self.setup_tab_55(tab_55)

        tab_phases = tk.Frame(self.notebook)
        self.notebook.add(tab_phases, text="Quali / Playoffs")
        self._setup_phases_tab(tab_phases)

    def _create_default_league(self, league_id):
        comp = competition_by_id(league_id) or {}
        return {
            "id": league_id,
            "name": comp.get("name") or f"League {league_id}",
            "country": "World",
            "games_season": 0,
            "over25": 0, "over35": 0, "over45": 0, "over55": 0,
            "last10_over25": 0, "last10_over35": 0, "last10_over45": 0, "last10_over55": 0,
            "last20_over25": 0, "last20_over35": 0, "last20_over45": 0, "last20_over55": 0,
            "streak25": 0, "streak35": 0, "streak45": 0, "streak55": 0,
            "max_streak_2022": 0, "min_streak_2022": 0, "median_streak_2022": 0.0,
            "max_streak_all": 0, "min_streak_all": 0, "median_streak_all": 0.0,
            "max_streak_2022_35": 0, "median_streak_2022_35": 0.0,
            "max_streak_all_35": 0, "median_streak_all_35": 0.0,
            "max_streak_2022_45": 0, "median_streak_2022_45": 0.0,
            "max_streak_all_45": 0, "median_streak_all_45": 0.0,
            "max_streak_2022_25_season": 0, "max_streak_2023_25_season": 0,
            "max_streak_2024_25_season": 0, "max_streak_2025_25_season": 0,
            "max_streak_2026_25_season": 0,
            "max_streak_2022_35_season": 0, "max_streak_2023_35_season": 0,
            "max_streak_2024_35_season": 0, "max_streak_2025_35_season": 0,
            "max_streak_2026_35_season": 0,
            "max_streak_2022_45_season": 0, "max_streak_2023_45_season": 0,
            "max_streak_2024_45_season": 0, "max_streak_2025_45_season": 0,
            "max_streak_2026_45_season": 0,
        }

    def _load_leagues_from_database(self):
        try:
            from database import DatabaseManager

            db_manager = DatabaseManager("data/flashscore.db")
            ensure_european_league_rows(db_manager)
            conn = db_manager.get_connection()
            self._ensure_league_streak_columns(conn)

            ids = list(self.euro_ids)
            placeholders = ",".join(["?"] * len(ids))
            rows = conn.execute(
                f"""
                SELECT DISTINCT
                    league_id,
                    COALESCE(league_name, 'Unknown League') as league_name,
                    COALESCE(country_name, 'World') as country_name
                FROM games
                WHERE league_id IN ({placeholders})
                """,
                ids,
            ).fetchall()
            by_id = {r[0]: r for r in rows}

            leagues = []
            for lid in ids:
                leagues.extend(self._phase_rows_for_competition(lid))
            return leagues
        except Exception as e:
            print(f"[ERROR] EuropeanCompetitionTab load: {e}")
            leagues = []
            for lid in self.euro_ids:
                leagues.extend(self._phase_rows_for_competition(lid))
            return leagues or [self._create_default_league(lid) for lid in self.euro_ids]

    def _phase_rows_for_competition(self, lid):
        comp = competition_by_id(lid) or {}
        short = comp.get("short") or "UEFA"
        full_name = comp.get("name") or f"League {lid}"
        rows = []
        for phase_key, phase_label in EURO_PHASES:
            indent = "" if phase_key == "all" else "    "
            row = self._create_default_league(lid)
            row["id"] = encode_row_id(lid, phase_key)
            row["source_id"] = lid
            row["phase"] = phase_key
            row["country"] = short
            row["name"] = f"{indent}{phase_label}" if phase_key != "all" else full_name
            rows.append(row)
        return rows

    def get_games_count_for_league(self, league_id, year):
        source_id, phase = decode_row_id(league_id)
        try:
            from database import DatabaseManager

            db_manager = DatabaseManager("data/flashscore.db")
            conn = db_manager.get_connection()
            extra = stats_for_league_year(conn, int(source_id), int(year), phase)
            n = extra.get("n") or 0
            return {
                "total": n,
                "total_finished": n,
                "over25": extra.get("over25", "0.0%"),
                "over35": extra.get("over35", "0.0%"),
                "over45": extra.get("over45", "0.0%"),
                "over55": extra.get("over55", "0.0%"),
                "last10_over25": extra.get("last10_over25", "0.0%"),
                "last10_over35": extra.get("last10_over35", "0.0%"),
                "last10_over45": extra.get("last10_over45", "0.0%"),
                "last10_over55": extra.get("last10_over55", "0.0%"),
                "last20_over25": extra.get("last20_over25", "0.0%"),
                "last20_over35": extra.get("last20_over35", "0.0%"),
                "last20_over45": extra.get("last20_over45", "0.0%"),
                "last20_over55": extra.get("last20_over55", "0.0%"),
                "streak25": extra.get("streak25", 0),
                "streak35": extra.get("streak35", 0),
                "streak45": extra.get("streak45", 0),
                "streak55": extra.get("streak55", 0),
            }
        except Exception as e:
            print(f"[WARNING] euro stats {league_id}/{year}: {e}")
            empty = "0.0%"
            return {
                "total": 0,
                "total_finished": 0,
                "over25": empty, "over35": empty, "over45": empty, "over55": empty,
                "last10_over25": empty, "last10_over35": empty, "last10_over45": empty, "last10_over55": empty,
                "last20_over25": empty, "last20_over35": empty, "last20_over45": empty, "last20_over55": empty,
                "streak25": 0, "streak35": 0, "streak45": 0, "streak55": 0,
            }

    def _get_today_upcoming_counts(self):
        """Noch ausstehende Spiele je Untergruppe (ohne bereits beendete)."""
        counts = {}
        try:
            from database import DatabaseManager

            db_manager = DatabaseManager("data/flashscore.db")
            conn = db_manager.get_connection()
            for lid in self.euro_ids:
                by_phase = today_counts_by_phase(conn, int(lid))
                counts[int(lid)] = int(by_phase.get("all", 0) or 0)
                for phase_key, _label in EURO_PHASES:
                    counts[encode_row_id(int(lid), phase_key)] = int(by_phase.get(phase_key, 0) or 0)
        except Exception as e:
            print(f"[WARNING] euro today counts: {e}")
        return counts

    def load_league_games_counts(self):
        if getattr(self, "_euro_filling", False):
            return
        self._euro_filling = True
        try:
            super().load_league_games_counts()
            self._apply_phase_max_streaks()
            for league in self.leagues:
                source_id, phase = decode_row_id(league.get("id") or 0)
                for year in self.years_to_show:
                    try:
                        from database import DatabaseManager

                        db_manager = DatabaseManager("data/flashscore.db")
                        conn = db_manager.get_connection()
                        extra = stats_for_league_year(conn, int(source_id), int(year), phase)
                        league[f"over55_{year}"] = extra.get("over55", "0.0%")
                        league[f"last10_over55_{year}"] = extra.get("last10_over55", "0.0%")
                        league[f"last20_over55_{year}"] = extra.get("last20_over55", "0.0%")
                        league[f"streak55_{year}"] = extra.get("streak55", 0)
                    except Exception:
                        league[f"over55_{year}"] = "0.0%"
                        league[f"last10_over55_{year}"] = "0.0%"
                        league[f"last20_over55_{year}"] = "0.0%"
                        league[f"streak55_{year}"] = 0
            self._skip_db_reload_once = True
            super().load_league_games_counts()
            self._rewrite_displayed_league_ids()
            self._fill_tab_55()
            self._fill_phases_tab()
        except Exception as e:
            print(f"[WARNING] euro extra tabs fill: {e}")
        finally:
            self._euro_filling = False

    def _apply_phase_max_streaks(self):
        from database import DatabaseManager

        db_manager = DatabaseManager("data/flashscore.db")
        conn = db_manager.get_connection()
        for league in self.leagues:
            source_id, phase = decode_row_id(league.get("id") or 0)
            max_of_max_25 = max_of_max_35 = max_of_max_45 = 0
            for year in [int(y) for y in self.years_to_show]:
                games = fetch_finished_games(conn, source_id, year, phase)
                games_asc = list(reversed(games))
                year_max_25 = year_max_35 = year_max_45 = 0
                cur25 = cur35 = cur45 = 0
                for g in games_asc:
                    total = g.get("total_goals") or 0
                    if total <= 2:
                        cur25 += 1
                        year_max_25 = max(year_max_25, cur25)
                    else:
                        cur25 = 0
                    if total <= 3:
                        cur35 += 1
                        year_max_35 = max(year_max_35, cur35)
                    else:
                        cur35 = 0
                    if total <= 4:
                        cur45 += 1
                        year_max_45 = max(year_max_45, cur45)
                    else:
                        cur45 = 0
                league[f"max_streak_{year}_25_season"] = year_max_25
                league[f"max_streak_{year}_35_season"] = year_max_35
                league[f"max_streak_{year}_45_season"] = year_max_45
                max_of_max_25 = max(max_of_max_25, year_max_25)
                max_of_max_35 = max(max_of_max_35, year_max_35)
                max_of_max_45 = max(max_of_max_45, year_max_45)
            league["max_of_max_25"] = max_of_max_25
            league["max_of_max_35"] = max_of_max_35
            league["max_of_max_45"] = max_of_max_45
            league["max_streak_all"] = max_of_max_25
            league["max_streak_all_35"] = max_of_max_35
            league["max_streak_all_45"] = max_of_max_45

    def _rewrite_displayed_league_ids(self):
        """ID-Spalte zeigt echte Liga (2/3/848), nicht die interne Phasen-ID."""
        trees = [
            getattr(self, "leagues_tree_25", None),
            getattr(self, "leagues_tree_35", None),
            getattr(self, "leagues_tree_45", None),
            getattr(self, "leagues_tree_current", None),
            getattr(self, "leagues_tree_alarm", None),
            getattr(self, "leagues_tree_max_streaks", None),
        ]
        for tree in trees:
            if tree is None:
                continue
            for iid in tree.get_children():
                vals = list(tree.item(iid, "values") or ())
                if len(vals) < 2:
                    continue
                try:
                    source, _phase = decode_row_id(int(vals[1]))
                    vals[1] = source
                    tree.item(iid, values=vals)
                except Exception:
                    pass

    def setup_tab_55(self, parent):
        table_frame = tk.LabelFrame(parent, text="European Competitions - 5.5 Goals")
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        years_reversed = list(reversed(self.years_to_show))
        base = ["Country", "ID", "Name", "Heute", "CurrentSeason", "Games_2026", "Alarm", "Streak5.5_2026"]
        year_cols = [f"Over5.5_{y}" for y in years_reversed]
        year_cols.extend(["Last10_5.5_2026", "Last20_5.5_2026"])
        all_columns = tuple(base + year_cols)

        self.leagues_tree_55 = ttk.Treeview(table_frame, columns=all_columns, show="headings", height=10)
        self.leagues_tree_55.sort_column = None
        self.leagues_tree_55.sort_reverse = False
        headings = {
            "Country": "Country", "ID": "League ID", "Name": "League Name",
            "Heute": "Heute Spi.", "CurrentSeason": "Current Season",
            "Games_2026": "Total Games (2026)", "Alarm": "Alarm",
            "Streak5.5_2026": "Streak 5.5 (2026)",
            "Last10_5.5_2026": "Last 10 (2026)", "Last20_5.5_2026": "Last 20 (2026)",
        }
        for y in years_reversed:
            headings[f"Over5.5_{y}"] = f"Over 5.5 ({y})"
        for col in all_columns:
            self.leagues_tree_55.heading(col, text=headings.get(col, col), command=lambda c=col: self.sort_tree(self.leagues_tree_55, c))
            width = 200 if col == "Name" else 110 if "Over" in col or "Last" in col or "Games" in col else 90
            self.leagues_tree_55.column(col, width=width, anchor="center" if col != "Name" else "w")

        for tag, color in (("diff_positive", "#d4edda"), ("diff_negative", "#f8d7da"), ("games_today", "#cce7ff"), ("no_data", "#e9ecef")):
            self.leagues_tree_55.tag_configure(tag, background=color)

        vsb = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.leagues_tree_55.yview)
        hsb = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.leagues_tree_55.xview)
        self.leagues_tree_55.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.leagues_tree_55.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        self.leagues_tree_55.bind("<Double-1>", self.show_games_list)
        self._bind_enhanced_tree(self.leagues_tree_55, "55")
        self._configure_alert_tree_tags(self.leagues_tree_55)

    def _find_league_for_row(self, values):
        league = super()._find_league_for_row(values)
        if league:
            return league
        if not values or len(values) < 2:
            return None
        try:
            raw_id = int(values[1])
        except (TypeError, ValueError):
            return None
        name = str(values[2]).replace("⚠", "").strip() if len(values) > 2 else ""
        if raw_id in EURO_LEAGUE_IDS:
            source_id = raw_id
            phase = phase_from_label(name)
        else:
            source_id, phase = decode_row_id(raw_id)
        for league in self.leagues or []:
            src, ph = decode_row_id(league.get("id", 0))
            if src == source_id and ph == phase:
                return league
            ln = (league.get("name") or "").replace("⚠", "").strip()
            if src == source_id and ln == name:
                return league
        return None

    def _fill_tab_55(self):
        tree = getattr(self, "leagues_tree_55", None)
        if tree is None:
            return
        for item in tree.get_children():
            tree.delete(item)
        years_reversed = list(reversed(self.years_to_show))
        today = getattr(self, "_today_upcoming_counts", {}) or {}
        for league in self.leagues:
            source_id, _phase = decode_row_id(league.get("id") or 0)
            today_cnt = today.get(int(league.get("id") or 0), 0)
            if not today_cnt:
                today_cnt = today.get(int(source_id), 0) if source_id and _phase == "all" else 0
            values = [
                league.get("country", "World"),
                source_id,
                league.get("name", ""),
                self._today_games_cell_label(today_cnt) if hasattr(self, "_today_games_cell_label") else today_cnt,
                self.current_seasons.get(source_id, 2026),
                league.get("games_2026", 0),
                "",
                league.get("streak55_2026", 0),
            ]
            for year in years_reversed:
                values.append(league.get(f"over55_{year}", "0.0%"))
            values.extend([
                league.get("last10_over55_2026", "0.0%"),
                league.get("last20_over55_2026", "0.0%"),
            ])
            tags = ("games_today",) if today_cnt else ()
            tree.insert("", tk.END, values=values, tags=tags)

    def _setup_phases_tab(self, parent):
        hint = tk.Label(
            parent,
            text="Jede Zeile = Wettbewerb × Phase (Qualifikation, Liga-Phase, Playoffs, K.-o.). Doppelklick öffnet die Spiele.",
            fg="#475569",
            anchor="w",
        )
        hint.pack(fill=tk.X, padx=10, pady=(8, 2))

        table_frame = tk.Frame(parent)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        cols = (
            "comp", "phase", "id", "games",
            "o25", "o35", "o45", "o55",
            "l10_25", "l10_35", "l10_45", "l10_55",
            "st25", "st35", "st45", "st55",
        )
        self.phases_tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=14)
        headings = {
            "comp": "Wettbewerb", "phase": "Phase", "id": "ID", "games": "Spiele 2026",
            "o25": "Over 2.5", "o35": "Over 3.5", "o45": "Over 4.5", "o55": "Over 5.5",
            "l10_25": "L10 2.5", "l10_35": "L10 3.5", "l10_45": "L10 4.5", "l10_55": "L10 5.5",
            "st25": "Streak 2.5", "st35": "Streak 3.5", "st45": "Streak 4.5", "st55": "Streak 5.5",
        }
        widths = {
            "comp": 220, "phase": 120, "id": 60, "games": 90,
            "o25": 80, "o35": 80, "o45": 80, "o55": 80,
            "l10_25": 70, "l10_35": 70, "l10_45": 70, "l10_55": 70,
            "st25": 80, "st35": 80, "st45": 80, "st55": 80,
        }
        for c in cols:
            self.phases_tree.heading(c, text=headings[c], command=lambda col=c: self.sort_tree(self.phases_tree, col))
            self.phases_tree.column(c, width=widths[c], anchor="center" if c != "comp" else "w")
        self.phases_tree.tag_configure("pos", background="#dcfce7")
        self.phases_tree.tag_configure("empty", foreground="#94a3b8")

        vsb = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.phases_tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.phases_tree.xview)
        self.phases_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.phases_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        self.phases_tree.bind("<Double-1>", self._on_phase_double_click)
        self._phase_row_meta = {}

    def _fill_phases_tab(self):
        tree = getattr(self, "phases_tree", None)
        if tree is None:
            return
        for item in tree.get_children():
            tree.delete(item)
        self._phase_row_meta = {}
        year = int(getattr(self, "year", "2026") or 2026)
        try:
            from database import DatabaseManager
            conn = DatabaseManager("data/flashscore.db").get_connection()
        except Exception as e:
            print(f"[WARNING] phases tab db: {e}")
            return

        for comp in EURO_COMPETITIONS:
            for phase_key, phase_label in EURO_PHASES:
                st = stats_for_league_year(conn, int(comp["id"]), year, phase_key)
                n = st.get("n") or 0
                values = (
                    comp["name"],
                    phase_label,
                    comp["id"],
                    n,
                    st.get("over25", "0.0%"),
                    st.get("over35", "0.0%"),
                    st.get("over45", "0.0%"),
                    st.get("over55", "0.0%"),
                    st.get("last10_over25", "0.0%"),
                    st.get("last10_over35", "0.0%"),
                    st.get("last10_over45", "0.0%"),
                    st.get("last10_over55", "0.0%"),
                    st.get("streak25", 0),
                    st.get("streak35", 0),
                    st.get("streak45", 0),
                    st.get("streak55", 0),
                )
                tag = "empty" if n == 0 else "pos"
                iid = tree.insert("", tk.END, values=values, tags=(tag,))
                self._phase_row_meta[iid] = {"league_id": int(comp["id"]), "phase": phase_key, "name": f"{comp['name']} · {phase_label}"}

    def _on_phase_double_click(self, event):
        sel = self.phases_tree.selection()
        if not sel:
            return
        meta = self._phase_row_meta.get(sel[0]) or {}
        league_id = meta.get("league_id")
        phase = meta.get("phase") or "all"
        name = meta.get("name") or "Phase"
        if not league_id:
            return
        self._open_phase_games_popup(league_id, phase, name)

    def show_games_list(self, event):
        widget = event.widget
        sel = widget.selection() if hasattr(widget, "selection") else ()
        if not sel:
            return
        values = widget.item(sel[0], "values")
        if not values or len(values) < 3:
            return
        try:
            raw_id = int(values[1])
        except (TypeError, ValueError):
            return
        name = str(values[2]).replace("⚠", "").strip()
        source_id, phase = decode_row_id(raw_id)
        if raw_id in EURO_LEAGUE_IDS:
            source_id = raw_id
            phase = phase_from_label(name)
        comp = competition_by_id(source_id)
        title = f"{(comp or {}).get('name', source_id)} · {name}"
        self._open_phase_games_popup(source_id, phase, title)

    def _append_phase_tabs_to_popup(self, league_id: int):
        popup = getattr(self, "games_popup", None)
        if popup is None:
            return
        nb = None
        for child in popup.winfo_children():
            if isinstance(child, ttk.Notebook):
                nb = child
                break
        if nb is None:
            return
        year = int(getattr(self, "year", "2026") or 2026)
        for phase_key, phase_label in EURO_PHASES:
            if phase_key == "all":
                continue
            frame = tk.Frame(nb)
            nb.add(frame, text=phase_label)
            self._fill_phase_games_table(frame, league_id, phase_key, year)

    def _open_phase_games_popup(self, league_id: int, phase: str, title: str):
        popup = tk.Toplevel(self)
        popup.title(title)
        popup.geometry("1400x700")
        year = int(getattr(self, "year", "2026") or 2026)
        self._fill_phase_games_table(popup, league_id, phase, year)

    def _fill_phase_games_table(self, parent, league_id: int, phase: str, year: int):
        from database import DatabaseManager

        conn = DatabaseManager("data/flashscore.db").get_connection()
        today_games = fetch_today_games(conn, league_id, phase)
        games = fetch_finished_games(conn, league_id, year, phase)
        summary = stats_for_league_year(conn, league_id, year, phase)
        n_today = len(today_games)
        tk.Label(
            parent,
            text=(
                f"Heute in dieser Untergruppe: {n_today}  |  "
                f"{year} fertig n={summary.get('n', 0)}  |  "
                f"2.5 {summary.get('over25')}  ·  3.5 {summary.get('over35')}  ·  "
                f"4.5 {summary.get('over45')}  ·  5.5 {summary.get('over55')}"
            ),
            anchor="w",
        ).pack(fill=tk.X, padx=10, pady=(8, 4))

        if today_games:
            today_frame = tk.LabelFrame(parent, text="Heute / noch nicht gespielt")
            today_frame.pack(fill=tk.X, padx=8, pady=(0, 6))
            tcols = ("date", "round", "home", "away", "status")
            ttree = ttk.Treeview(today_frame, columns=tcols, show="headings", height=min(8, max(3, n_today)))
            for c, h, w in (
                ("date", "Kickoff", 130),
                ("round", "Runde", 180),
                ("home", "Home", 180),
                ("away", "Away", 180),
                ("status", "Status", 120),
            ):
                ttree.heading(c, text=h)
                ttree.column(c, width=w, anchor="center" if c in ("date", "status") else "w")
            ttree.tag_configure("today", background="#dbeafe")
            ttree.pack(fill=tk.X, padx=4, pady=4)
            for g in today_games:
                date_val = str(g.get("date") or "")
                if "T" in date_val:
                    try:
                        from datetime import datetime as _dt
                        date_val = _dt.fromisoformat(date_val.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M")
                    except Exception:
                        date_val = date_val[:16]
                ttree.insert(
                    "", tk.END,
                    values=(
                        date_val[:16],
                        g.get("round_name") or "",
                        g.get("home_team_name") or "",
                        g.get("away_team_name") or "",
                        g.get("status_name") or "Upcoming",
                    ),
                    tags=("today",),
                )

        wrap = tk.Frame(parent)
        wrap.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        cols = ("date", "round", "home", "away", "score", "goals", "o25", "o35", "o45", "o55")
        tree = ttk.Treeview(wrap, columns=cols, show="headings", height=18)
        headings = {
            "date": "Datum", "round": "Runde", "home": "Home", "away": "Away",
            "score": "Ergebnis", "goals": "Tore",
            "o25": "O2.5", "o35": "O3.5", "o45": "O4.5", "o55": "O5.5",
        }
        widths = {"date": 110, "round": 180, "home": 160, "away": 160, "score": 70, "goals": 50, "o25": 50, "o35": 50, "o45": 50, "o55": 50}
        for c in cols:
            tree.heading(c, text=headings[c])
            tree.column(c, width=widths[c], anchor="center" if c not in ("round", "home", "away") else "w")
        tree.tag_configure("over", background="#dcfce7")
        tree.tag_configure("under", background="#fee2e2")
        vsb = ttk.Scrollbar(wrap, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        for g in games:
            goals = g.get("total_goals") or 0
            hs = g.get("home_ft_result")
            aws = g.get("away_ft_result")
            tree.insert(
                "", tk.END,
                values=(
                    str(g.get("date") or "")[:16],
                    g.get("round_name") or "",
                    g.get("home_team_name") or "",
                    g.get("away_team_name") or "",
                    f"{hs}:{aws}",
                    goals,
                    "✓" if goals > 2.5 else "",
                    "✓" if goals > 3.5 else "",
                    "✓" if goals > 4.5 else "",
                    "✓" if goals > 5.5 else "",
                ),
                tags=("over" if goals > 2.5 else "under",),
            )

    def refresh_data(self):
        def refresh_in_thread():
            try:
                from database import DatabaseManager
                from services.game_loader_service import GameLoaderService

                db_manager = DatabaseManager("data/flashscore.db")
                ensure_european_league_rows(db_manager)
                api_client = self.services.get("client")
                loader_service = GameLoaderService(api_client, db_manager, rate_limit_ms=1000)
                years = [2024, 2025, 2026]

                for league_id in self.euro_ids:
                    for year in years:
                        self.after(
                            0,
                            lambda lid=league_id, y=year: self.status_label.config(
                                text=f"Lade {competition_by_id(lid)['name'] if competition_by_id(lid) else lid} {y}..."
                            )
                            if hasattr(self, "status_label")
                            else None,
                        )

                        def progress_callback(current, total, message, lid=league_id, y=year):
                            self.after(
                                0,
                                lambda: self.status_label.config(
                                    text=f"Liga {lid} {y}: {message} ({current}/{total})"
                                )
                                if hasattr(self, "status_label")
                                else None,
                            )

                        loader_service.load_games_for_league(
                            league_id,
                            year,
                            progress_callback=progress_callback,
                            load_details=True,
                            skip_existing=True,
                        )

                self.after(0, lambda: self.status_label.config(text="Aktualisiere Anzeige..."))
                self.leagues = self._load_leagues_from_database()
                self.after(0, self.load_league_games_counts)
                if hasattr(self, "leagues_tree_max_streaks"):
                    self.after(0, self.load_max_streaks)
                self.after(0, lambda: self.status_label.config(text="European Competitions aktualisiert"))
                self.after(0, lambda: messagebox.showinfo("Fertig", "CL / EL / Conference League geladen."))
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.after(0, lambda: messagebox.showerror("Fehler", f"European Competitions Update fehlgeschlagen:\n{e}"))

        threading.Thread(target=refresh_in_thread, daemon=True).start()
