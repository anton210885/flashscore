"""Tab: FIFA World Cup – Spiele, Spieltage, KO, Over-Statistik."""
import csv
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime

from services.world_cup_service import (
    WORLD_CUP_LEAGUE_ID,
    WORLD_CUP_YEARS,
    WORLD_CUP_UPCOMING_YEAR,
    OVER_THRESHOLDS,
    COMPARE_WM_YEARS,
    CHART_SEGMENTS,
    fetch_world_cup_games_from_db,
    split_by_phase,
    split_group_by_matchday,
    build_statistics_segments,
    format_over_cell,
    ensure_world_cup_league_row,
    load_wm_years_from_db,
    get_games_for_segment,
    compute_over_stats,
    compute_goals_distribution,
)
from services.game_loader_service import GameLoaderService

try:
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

_CHART_YEAR_COLORS = ("#1f77b4", "#ff7f0e", "#2ca02c")


class WorldCupTab(tk.Frame):
    LEAGUE_ID = WORLD_CUP_LEAGUE_ID

    def __init__(self, parent, services):
        super().__init__(parent)
        self.services = services
        self.db_manager = None
        self.loader_service = None
        self._games_cache: list = []
        self._group_trees: dict = {}
        self._chart_panels: dict = {}
        self._chart_canvases: list = []
        self._build_ui()
        self._init_services()
        self.after(300, self.refresh_display)

    def _init_services(self):
        try:
            from database import DatabaseManager

            self.db_manager = DatabaseManager("data/flashscore.db")
            ensure_world_cup_league_row(self.db_manager)
            self.loader_service = GameLoaderService(
                self.services["client"],
                self.db_manager,
                rate_limit_ms=1000,
            )
        except Exception as e:
            messagebox.showerror("World Cup", f"Datenbank konnte nicht initialisiert werden:\n{e}")

    def _build_ui(self):
        header = tk.Frame(self)
        header.pack(fill=tk.X, padx=10, pady=8)
        tk.Label(header, text="FIFA World Cup (WM)", font=("Arial", 16, "bold")).pack(side=tk.LEFT)

        ctrl = tk.Frame(self)
        ctrl.pack(fill=tk.X, padx=10, pady=4)

        tk.Label(ctrl, text="WM-Jahr:", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=(0, 6))
        self.year_var = tk.StringVar(value=str(WORLD_CUP_YEARS[-2]))  # default 2022
        year_combo = ttk.Combobox(
            ctrl,
            textvariable=self.year_var,
            values=[str(y) for y in WORLD_CUP_YEARS],
            width=8,
            state="readonly",
        )
        year_combo.pack(side=tk.LEFT, padx=4)
        year_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_display())

        tk.Button(ctrl, text="Anzeige aktualisieren", command=self.refresh_display).pack(side=tk.LEFT, padx=6)
        tk.Button(
            ctrl,
            text="Gewähltes Jahr laden",
            command=self._load_selected_year,
            bg="#4CAF50",
            fg="white",
        ).pack(side=tk.LEFT, padx=4)
        tk.Button(
            ctrl,
            text="Alle WM laden",
            command=self._load_all_years,
            bg="#2196F3",
            fg="white",
        ).pack(side=tk.LEFT, padx=4)

        self.btn_refresh_2026 = tk.Button(
            ctrl,
            text="WM 2026 aktualisieren",
            command=self._refresh_2026,
            bg="#FF9800",
            fg="white",
            font=("Arial", 9, "bold"),
        )
        self.btn_refresh_2026.pack(side=tk.LEFT, padx=8)

        tk.Button(ctrl, text="CSV exportieren", command=self._export_csv).pack(side=tk.RIGHT, padx=4)

        prog_frame = tk.Frame(self)
        prog_frame.pack(fill=tk.X, padx=10, pady=4)
        self.status_label = tk.Label(prog_frame, text="Bereit", anchor="w", fg="gray")
        self.status_label.pack(fill=tk.X)
        self.progress = ttk.Progressbar(prog_frame, mode="determinate")
        self.progress.pack(fill=tk.X, pady=4)

        tk.Label(
            self,
            text=(
                "Liga-ID 1 · Over-Statistik für 0.5 / 1.5 / 2.5 / 3.5 / 4.5 Tore · "
                "Gruppenphase nach Spieltag 1–3 · WM 2026 per Button aktualisieren"
            ),
            fg="gray",
            font=("Arial", 9),
            wraplength=920,
            justify="left",
        ).pack(anchor="w", padx=12, pady=(0, 4))

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=6)

        for md, title in ((1, "Gruppe · Spieltag 1"), (2, "Gruppe · Spieltag 2"), (3, "Gruppe · Spieltag 3")):
            self._group_trees[md] = self._make_games_tab(title)

        self._group_trees["other"] = self._make_games_tab("Gruppe · Sonstige")
        self.tree_ko = self._make_games_tab("K.-o.-Phase")
        self.tree_stats = self._make_stats_tab()
        self._build_charts_tab()

        self.summary_label = tk.Label(self, text="", font=("Arial", 9))
        self.summary_label.pack(anchor="w", padx=12, pady=(0, 8))

    def _make_games_tab(self, title: str) -> ttk.Treeview:
        frame = tk.Frame(self.notebook)
        self.notebook.add(frame, text=title)
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        cols = ("date", "home", "away", "score", "goals", "round", "status")
        tree = ttk.Treeview(frame, columns=cols, show="headings", height=16)
        tree.heading("date", text="Datum")
        tree.heading("home", text="Heim")
        tree.heading("away", text="Auswärts")
        tree.heading("score", text="Ergebnis")
        tree.heading("goals", text="Tore")
        tree.heading("round", text="Runde")
        tree.heading("status", text="Status")

        tree.column("date", width=120, anchor="center")
        tree.column("home", width=175)
        tree.column("away", width=175)
        tree.column("score", width=65, anchor="center")
        tree.column("goals", width=45, anchor="center")
        tree.column("round", width=160)
        tree.column("status", width=90, anchor="center")

        vsb = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
        hsb = ttk.Scrollbar(frame, orient=tk.HORIZONTAL, command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        return tree

    def _make_stats_tab(self) -> ttk.Treeview:
        frame = tk.Frame(self.notebook)
        self.notebook.add(frame, text="Statistik Over")
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        cols = ["bereich", "spiele", "mit_ergebnis"] + [f"over_{str(t).replace('.', '')}" for t in OVER_THRESHOLDS]
        tree = ttk.Treeview(frame, columns=cols, show="headings", height=12)
        tree.heading("bereich", text="Bereich")
        tree.heading("spiele", text="Spiele")
        tree.heading("mit_ergebnis", text="m. Ergebnis")
        for t in OVER_THRESHOLDS:
            key = f"over_{str(t).replace('.', '')}"
            tree.heading(key, text=f"Over {t}")

        tree.column("bereich", width=200)
        tree.column("spiele", width=60, anchor="center")
        tree.column("mit_ergebnis", width=80, anchor="center")
        for t in OVER_THRESHOLDS:
            key = f"over_{str(t).replace('.', '')}"
            tree.column(key, width=95, anchor="center")

        vsb = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        return tree

    def _build_charts_tab(self):
        """Unter-Tabs je Bereich: Over-Vergleich + Tore-pro-Spiel-Balken (2018/2022/2026)."""
        outer = tk.Frame(self.notebook)
        self.notebook.add(outer, text="Grafiken")

        if not HAS_MATPLOTLIB:
            tk.Label(
                outer,
                text="Matplotlib fehlt – bitte installieren: pip install matplotlib",
                fg="red",
            ).pack(pady=20)
            return

        tk.Label(
            outer,
            text="Vergleich WM 2018 · 2022 · 2026 — Over-Linien und Tore pro Spiel je Bereich",
            font=("Arial", 10, "bold"),
        ).pack(anchor="w", padx=8, pady=6)

        self.charts_notebook = ttk.Notebook(outer)
        self.charts_notebook.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

        for seg_key, seg_title in CHART_SEGMENTS:
            panel = tk.Frame(self.charts_notebook)
            self.charts_notebook.add(panel, text=seg_title)
            panel.grid_rowconfigure(0, weight=1)
            panel.grid_rowconfigure(1, weight=1)
            panel.grid_columnconfigure(0, weight=1)

            over_frame = tk.LabelFrame(panel, text="Over 0.5 – 4.5 (% der Spiele)")
            over_frame.grid(row=0, column=0, sticky="nsew", padx=6, pady=4)
            goals_frame = tk.LabelFrame(panel, text="Tore pro Spiel (Anzahl Spiele)")
            goals_frame.grid(row=1, column=0, sticky="nsew", padx=6, pady=4)

            self._chart_panels[seg_key] = {
                "over": over_frame,
                "goals": goals_frame,
            }

    def _clear_chart_canvases(self):
        for canvas in self._chart_canvases:
            try:
                canvas.get_tk_widget().destroy()
            except tk.TclError:
                pass
        self._chart_canvases.clear()

    def _draw_comparison_charts(self):
        if not HAS_MATPLOTLIB or not self._chart_panels or not self.db_manager:
            return

        self._clear_chart_canvases()
        years_data = load_wm_years_from_db(self.db_manager, COMPARE_WM_YEARS)

        for seg_key, _seg_title in CHART_SEGMENTS:
            panels = self._chart_panels.get(seg_key)
            if not panels:
                continue

            # --- Over-Vergleich ---
            fig_over = Figure(figsize=(9, 3.2), dpi=100)
            ax_over = fig_over.add_subplot(111)
            self._plot_over_comparison(ax_over, years_data, seg_key)
            fig_over.tight_layout()
            canvas_over = FigureCanvasTkAgg(fig_over, master=panels["over"])
            canvas_over.draw()
            canvas_over.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            self._chart_canvases.append(canvas_over)

            # --- Tore pro Spiel ---
            fig_goals = Figure(figsize=(9, 3.2), dpi=100)
            ax_goals = fig_goals.add_subplot(111)
            self._plot_goals_distribution(ax_goals, years_data, seg_key)
            fig_goals.tight_layout()
            canvas_goals = FigureCanvasTkAgg(fig_goals, master=panels["goals"])
            canvas_goals.draw()
            canvas_goals.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            self._chart_canvases.append(canvas_goals)

    def _plot_over_comparison(self, ax, years_data: dict, segment_key: str):
        labels = [f"Over {t}" for t in OVER_THRESHOLDS]
        n = len(labels)
        bar_w = 0.22
        x_base = list(range(n))

        for i, year in enumerate(COMPARE_WM_YEARS):
            games = years_data.get(year, [])
            subset = get_games_for_segment(games, segment_key)
            stats = compute_over_stats(subset)
            if stats["with_score"] == 0:
                pcts = [0.0] * n
                note = f"{year} (0 Spiele)"
            else:
                pcts = [stats["overs"][str(t)]["pct"] for t in OVER_THRESHOLDS]
                note = f"{year} (n={stats['with_score']})"
            offsets = [x + (i - 1) * bar_w for x in x_base]
            ax.bar(
                offsets,
                pcts,
                width=bar_w,
                label=note,
                color=_CHART_YEAR_COLORS[i % len(_CHART_YEAR_COLORS)],
                alpha=0.9,
            )

        ax.set_xticks(x_base)
        ax.set_xticklabels(labels, fontsize=9)
        ax.set_ylabel("Anteil (%)")
        ax.set_ylim(0, 105)
        ax.legend(loc="upper right", fontsize=8)
        ax.grid(axis="y", linestyle="--", alpha=0.4)
        ax.set_title("Over-Vergleich WM 2018 / 2022 / 2026")

    def _plot_goals_distribution(self, ax, years_data: dict, segment_key: str):
        dists = {}
        max_goal = 0
        for year in COMPARE_WM_YEARS:
            games = years_data.get(year, [])
            subset = get_games_for_segment(games, segment_key)
            dists[year] = compute_goals_distribution(subset)
            if dists[year]:
                max_goal = max(max_goal, max(dists[year].keys()))

        goal_range = list(range(0, max(max_goal, 7) + 1))
        n = len(goal_range)
        bar_w = 0.22
        x_base = list(range(n))

        for i, year in enumerate(COMPARE_WM_YEARS):
            counts = [dists[year].get(g, 0) for g in goal_range]
            total = sum(counts)
            offsets = [x + (i - 1) * bar_w for x in x_base]
            ax.bar(
                offsets,
                counts,
                width=bar_w,
                label=f"{year} (n={total})",
                color=_CHART_YEAR_COLORS[i % len(_CHART_YEAR_COLORS)],
                alpha=0.9,
            )

        ax.set_xticks(x_base)
        ax.set_xticklabels([str(g) for g in goal_range], fontsize=9)
        ax.set_xlabel("Gesamttore pro Spiel")
        ax.set_ylabel("Anzahl Spiele")
        ax.legend(loc="upper right", fontsize=8)
        ax.grid(axis="y", linestyle="--", alpha=0.4)
        ax.set_title("Verteilung: wie oft 0, 1, 2, … Tore pro Spiel")

    def _format_date(self, raw) -> str:
        if not raw:
            return ""
        s = str(raw)
        if "T" in s:
            try:
                dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
                return dt.strftime("%Y-%m-%d %H:%M")
            except ValueError:
                return s[:16].replace("T", " ")
        return s[:16]

    def _format_score(self, g: dict) -> str:
        h, a = g.get("home_ft_result"), g.get("away_ft_result")
        if h is not None and a is not None:
            return f"{h}:{a}"
        return "–"

    def _total_goals(self, g: dict):
        h, a = g.get("home_ft_result"), g.get("away_ft_result")
        if h is None or a is None:
            return ""
        try:
            return int(h) + int(a)
        except (TypeError, ValueError):
            return ""

    def _fill_tree(self, tree: ttk.Treeview, games: list):
        for item in tree.get_children():
            tree.delete(item)
        for g in games:
            tree.insert(
                "",
                tk.END,
                values=(
                    self._format_date(g.get("date")),
                    g.get("home_team_name") or "",
                    g.get("away_team_name") or "",
                    self._format_score(g),
                    self._total_goals(g),
                    g.get("round_name") or "",
                    g.get("status_name") or "",
                ),
            )

    def _fill_stats_tree(self, segments: list):
        for item in self.tree_stats.get_children():
            self.tree_stats.delete(item)
        for seg in segments:
            st = seg["stats"]
            vals = [
                seg["label"],
                st["total"],
                st["with_score"],
            ]
            for t in OVER_THRESHOLDS:
                vals.append(format_over_cell(st, t))
            self.tree_stats.insert("", tk.END, values=tuple(vals))

    def refresh_display(self):
        if not self.db_manager:
            return
        try:
            year = int(self.year_var.get())
        except ValueError:
            year = WORLD_CUP_YEARS[-2]

        games = fetch_world_cup_games_from_db(self.db_manager, year)
        self._games_cache = games
        phases = split_by_phase(games)
        by_md = split_group_by_matchday(phases["group"])

        self._fill_tree(self._group_trees[1], by_md[1])
        self._fill_tree(self._group_trees[2], by_md[2])
        self._fill_tree(self._group_trees[3], by_md[3])
        self._fill_tree(self._group_trees["other"], by_md[None])
        self._fill_tree(self.tree_ko, phases["ko"])

        segments = build_statistics_segments(games)
        self._fill_stats_tree(segments)

        total = len(games)
        self.summary_label.config(
            text=(
                f"WM {year}: {total} Spiele · "
                f"Gruppe ST1–3: {len(by_md[1])}/{len(by_md[2])}/{len(by_md[3])} · "
                f"KO: {len(phases['ko'])}"
            )
        )
        if total == 0:
            self.status_label.config(
                text=f"WM {year}: keine Spiele in der DB – bitte laden oder WM 2026 aktualisieren."
            )
        else:
            self.status_label.config(text=f"WM {year}: {total} Spiele · Statistik aktualisiert.")

        self._draw_comparison_charts()

    def _load_selected_year(self):
        if not self.loader_service:
            messagebox.showerror("Fehler", "Loader nicht bereit.")
            return
        try:
            year = int(self.year_var.get())
        except ValueError:
            messagebox.showwarning("Jahr", "Bitte ein gültiges WM-Jahr wählen.")
            return
        if not messagebox.askyesno(
            "WM laden",
            f"Beendete Spiele WM {year} (Liga-ID {self.LEAGUE_ID}) von der API laden?",
        ):
            return
        threading.Thread(
            target=self._load_years_thread,
            args=([year],),
            kwargs={"skip_existing": True},
            daemon=True,
        ).start()

    def _load_all_years(self):
        if not self.loader_service:
            messagebox.showerror("Fehler", "Loader nicht bereit.")
            return
        years = list(WORLD_CUP_YEARS)
        if not messagebox.askyesno(
            "Alle WM laden",
            f"Alle WM-Jahre laden ({years[0]}–{years[-1]})?\nKann wegen API-Limit lange dauern.",
        ):
            return
        threading.Thread(
            target=self._load_years_thread,
            args=(years,),
            kwargs={"skip_existing": True},
            daemon=True,
        ).start()

    def _refresh_2026(self):
        """WM 2026: neue + geänderte Spiele nachladen (skip_existing=False)."""
        if not self.loader_service:
            messagebox.showerror("Fehler", "Loader nicht bereit.")
            return
        self.year_var.set(str(WORLD_CUP_UPCOMING_YEAR))
        if not messagebox.askyesno(
            "WM 2026 aktualisieren",
            "Spiele der WM 2026 von der API neu einlesen?\n"
            "Bereits vorhandene Spiele werden erneut geprüft/aktualisiert.",
        ):
            return
        threading.Thread(
            target=self._load_years_thread,
            args=([WORLD_CUP_UPCOMING_YEAR],),
            kwargs={"skip_existing": False},
            daemon=True,
        ).start()

    def _load_years_thread(self, years: list, skip_existing: bool = True):
        total_years = len(years)
        summary_lines = []

        self.after(0, lambda: self.progress.configure(value=0, maximum=total_years))
        self.after(0, lambda: self.status_label.config(text="Starte Download…"))

        for idx, year in enumerate(years):
            self.after(
                0,
                lambda y=year, i=idx: self.status_label.config(
                    text=f"Lade WM {y} ({i + 1}/{total_years})…"
                ),
            )
            try:

                def cb(c, t, m, y=year):
                    if t > 0:
                        self.after(0, lambda: self.progress.configure(maximum=t, value=c))
                    self.after(0, lambda: self.status_label.config(text=f"WM {y}: {m}"))

                stats = self.loader_service.load_games_for_league(
                    self.LEAGUE_ID,
                    year,
                    progress_callback=cb,
                    load_details=True,
                    skip_existing=skip_existing,
                )
                summary_lines.append(
                    f"WM {year}: neu {stats.get('loaded', 0)}, "
                    f"vorhanden {stats.get('already_exists', 0)}, "
                    f"Fehler {stats.get('errors', 0)}"
                )
            except Exception as e:
                summary_lines.append(f"WM {year}: Fehler – {e}")

            self.after(0, lambda v=idx + 1: self.progress.configure(value=v))

        def done():
            self.progress.configure(value=0)
            self.status_label.config(text="Download abgeschlossen.")
            self.refresh_display()
            messagebox.showinfo("WM Download", "\n".join(summary_lines))

        self.after(0, done)

    def _export_csv(self):
        if not self._games_cache:
            messagebox.showinfo("Export", "Keine Spiele – zuerst laden.")
            return
        year = self.year_var.get()
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile=f"world_cup_{year}.csv",
        )
        if not path:
            return
        phases = split_by_phase(self._games_cache)
        by_md = split_group_by_matchday(phases["group"])
        segments = build_statistics_segments(self._games_cache)

        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f, delimiter=";")
                writer.writerow(
                    ["Bereich", "Spiele", "m. Ergebnis"]
                    + [f"Over {t}" for t in OVER_THRESHOLDS]
                )
                for seg in segments:
                    st = seg["stats"]
                    row = [seg["label"], st["total"], st["with_score"]]
                    for t in OVER_THRESHOLDS:
                        row.append(format_over_cell(st, t))
                    writer.writerow(row)

                writer.writerow([])
                writer.writerow(
                    ["Phase/Spieltag", "Datum", "Heim", "Auswärts", "Ergebnis", "Tore", "Runde", "Status", "ID"]
                )
                export_blocks = [
                    ("Spieltag 1", by_md[1]),
                    ("Spieltag 2", by_md[2]),
                    ("Spieltag 3", by_md[3]),
                    ("Gruppe Sonstige", by_md[None]),
                    ("KO-Phase", phases["ko"]),
                ]
                for label, games in export_blocks:
                    for g in games:
                        writer.writerow(
                            [
                                label,
                                self._format_date(g.get("date")),
                                g.get("home_team_name") or "",
                                g.get("away_team_name") or "",
                                self._format_score(g),
                                self._total_goals(g),
                                g.get("round_name") or "",
                                g.get("status_name") or "",
                                g.get("id") or "",
                            ]
                        )
            messagebox.showinfo("Export", f"Gespeichert:\n{path}")
        except OSError as e:
            messagebox.showerror("Export", str(e))
