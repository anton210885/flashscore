"""Liga-128-Tab: gleiche Features wie LeagueTab, aber nur konfigurierte Liga-128-IDs."""
import json
import os
import threading
import tkinter as tk
from tkinter import messagebox

from ui.tabs.league_tab import LeagueTab

LIGA128_CONFIG_PATH = os.path.join("data", "liga128_leagues.json")


def load_liga128_ids():
    """Load league IDs for Liga 128 tab from config file."""
    default_ids = [128, 265, 23, 9, 239]
    try:
        if os.path.exists(LIGA128_CONFIG_PATH):
            with open(LIGA128_CONFIG_PATH, "r", encoding="utf-8") as f:
                ids = json.load(f)
                if isinstance(ids, list) and all(isinstance(i, int) for i in ids):
                    return ids
    except Exception as e:
        print(f"[WARNING] Could not load liga128 config: {e}")
    return default_ids


def save_liga128_ids(ids):
    """Save league IDs for Liga 128 tab to config file."""
    try:
        os.makedirs(os.path.dirname(LIGA128_CONFIG_PATH), exist_ok=True)
        with open(LIGA128_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(sorted(set(ids)), f)
        print(f"[INFO] Saved Liga 128 config: {sorted(set(ids))}")
    except Exception as e:
        print(f"[ERROR] Could not save liga128 config: {e}")


class League128Tab(LeagueTab):
    """
    Gleiche UI wie LeagueTab (Filter, Detail, Watchlist, Hover-Streaks,
    Trend, Live-Max-Streaks, Chart-Drilldown), gefiltert auf liga128_leagues.json.
    """

    def __init__(self, parent, services):
        # Muss vor LeagueTab.__init__ gesetzt sein (Parent lädt Ligen sofort).
        self.liga128_ids = load_liga128_ids()
        print(f"[DEBUG] Liga 128 configured IDs: {self.liga128_ids}")
        super().__init__(parent, services)
        # Kalenderjahr-Ligen: Saison = Kalenderjahr (Start+Ende 2026)
        self.years_to_show = ["2022", "2023", "2024", "2025", "2026"]
        self.year = "2026"
        for lid in self.liga128_ids:
            self.current_seasons.setdefault(int(lid), 2026)
        print(
            f"[DEBUG] League128Tab ready: {len(self.leagues)} league(s), "
            f"year={self.year}, features inherited from LeagueTab"
        )

    def _create_default_league(self, league_id):
        """Placeholder, wenn eine konfigurierte ID noch keine Spiele in der DB hat."""
        return {
            "id": league_id,
            "name": f"League {league_id}",
            "country": "Unknown",
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
            "streak45": 0,
            "max_streak_2022": 0,
            "min_streak_2022": 0,
            "median_streak_2022": 0.0,
            "max_streak_all": 0,
            "min_streak_all": 0,
            "median_streak_all": 0.0,
            "max_streak_2022_35": 0,
            "median_streak_2022_35": 0.0,
            "max_streak_all_35": 0,
            "median_streak_all_35": 0.0,
            "max_streak_2022_45": 0,
            "median_streak_2022_45": 0.0,
            "max_streak_all_45": 0,
            "median_streak_all_45": 0.0,
            "max_streak_2022_25_season": 0,
            "max_streak_2023_25_season": 0,
            "max_streak_2024_25_season": 0,
            "max_streak_2025_25_season": 0,
            "max_streak_2026_25_season": 0,
            "max_streak_2022_35_season": 0,
            "max_streak_2023_35_season": 0,
            "max_streak_2024_35_season": 0,
            "max_streak_2025_35_season": 0,
            "max_streak_2026_35_season": 0,
            "max_streak_2022_45_season": 0,
            "max_streak_2023_45_season": 0,
            "max_streak_2024_45_season": 0,
            "max_streak_2025_45_season": 0,
            "max_streak_2026_45_season": 0,
        }

    def _load_leagues_from_database(self):
        """Nur Ligen aus data/liga128_leagues.json (nicht die Haupt-League-Liste)."""
        if not getattr(self, "liga128_ids", None):
            self.liga128_ids = load_liga128_ids()

        try:
            from database import DatabaseManager

            db_manager = DatabaseManager("data/flashscore.db")
            conn = db_manager.get_connection()
            self._ensure_league_streak_columns(conn)

            ids = list(self.liga128_ids)
            if not ids:
                return []

            placeholders = ",".join(["?"] * len(ids))
            leagues_data = conn.execute(
                f"""
                SELECT DISTINCT
                    league_id,
                    COALESCE(league_name, 'Unknown League') as league_name,
                    COALESCE(country_name, 'Unknown') as country_name,
                    country_code
                FROM games
                WHERE league_id IN ({placeholders})
                ORDER BY country_name, league_name
                """,
                ids,
            ).fetchall()

            print(f"[DEBUG] Liga128 loaded {len(leagues_data)} leagues from DB (IDs: {ids})")

            league_name_fixes = {
                128: "Liga Profesional",
                307: "Saudi Pro League",
                308: "Saudi Division 1",
                303: "UAE Division 1",
                301: "UAE Pro League",
            }

            leagues = []
            found_league_ids = set()
            seen_names = {}

            for row in leagues_data:
                league_id, league_name, country_name, country_code = row
                if league_id in found_league_ids:
                    continue
                if league_id in league_name_fixes:
                    league_name = league_name_fixes[league_id]

                key = (country_name or "Unknown", league_name)
                if key in seen_names:
                    existing_id = seen_names[key]
                    for league in leagues:
                        if league["id"] == existing_id:
                            league["name"] = f"{league['name']} ({existing_id})"
                            break
                    league_name = f"{league_name} ({league_id})"
                else:
                    seen_names[key] = league_id

                found_league_ids.add(league_id)
                leagues.append(
                    {
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
                        "streak45": 0,
                    }
                )

            # Streak-Metadaten aus leagues-Tabelle (Live-Max kommt zusätzlich in load_league_games_counts)
            streak_dict = {}
            try:
                streak_data = conn.execute(
                    """
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
                    """
                ).fetchall()
                for row in streak_data:
                    streak_dict[row[0]] = {
                        "max_streak_2022": row[1] or 0,
                        "min_streak_2022": row[2] or 0,
                        "median_streak_2022": row[3] or 0.0,
                        "max_streak_all": row[4] or 0,
                        "min_streak_all": row[5] or 0,
                        "median_streak_all": row[6] or 0.0,
                        "max_streak_2022_35": row[7] or 0,
                        "median_streak_2022_35": row[8] or 0.0,
                        "max_streak_all_35": row[9] or 0,
                        "median_streak_all_35": row[10] or 0.0,
                        "max_streak_2022_45": row[11] or 0,
                        "median_streak_2022_45": row[12] or 0.0,
                        "max_streak_all_45": row[13] or 0,
                        "median_streak_all_45": row[14] or 0.0,
                        "max_streak_2022_25_season": row[15] or 0,
                        "max_streak_2023_25_season": row[16] or 0,
                        "max_streak_2024_25_season": row[17] or 0,
                        "max_streak_2025_25_season": row[18] or 0,
                        "max_streak_2026_25_season": row[19] or 0,
                        "max_streak_2022_35_season": row[20] or 0,
                        "max_streak_2023_35_season": row[21] or 0,
                        "max_streak_2024_35_season": row[22] or 0,
                        "max_streak_2025_35_season": row[23] or 0,
                        "max_streak_2026_35_season": row[24] or 0,
                        "max_streak_2022_45_season": row[25] or 0,
                        "max_streak_2023_45_season": row[26] or 0,
                        "max_streak_2024_45_season": row[27] or 0,
                        "max_streak_2025_45_season": row[28] or 0,
                        "max_streak_2026_45_season": row[29] or 0,
                    }
            except Exception as e:
                print(f"[WARNING] Liga128 streak load: {e}")

            for league in leagues:
                if league["id"] in streak_dict:
                    league.update(streak_dict[league["id"]])
                else:
                    defaults = self._create_default_league(league["id"])
                    for key, val in defaults.items():
                        if key in ("id", "name", "country"):
                            continue
                        league.setdefault(key, val)

            # Konfigurierte IDs ohne Spiele trotzdem anzeigen
            for lid in ids:
                if lid not in found_league_ids:
                    print(f"[WARNING] League {lid} not in DB games, creating placeholder")
                    leagues.append(self._create_default_league(lid))

            leagues.sort(key=lambda x: (x.get("country") or "", x.get("name") or ""))
            return leagues
        except Exception as e:
            import traceback

            print(f"[ERROR] Liga128 _load_leagues_from_database: {e}")
            print(traceback.format_exc())
            return [self._create_default_league(lid) for lid in getattr(self, "liga128_ids", [])]

    def refresh_data(self):
        """API-Refresh nur für konfigurierte Liga-128-IDs, danach Parent-Statistik neu berechnen."""
        self.liga128_ids = load_liga128_ids()
        print(f"[DEBUG] Liga128 refresh_data for IDs: {self.liga128_ids}")

        def refresh_in_thread():
            try:
                from datetime import datetime

                from database import DatabaseManager
                from services.game_loader_service import GameLoaderService

                db_manager = DatabaseManager("data/flashscore.db")
                api_client = self.services.get("client")
                loader_service = GameLoaderService(api_client, db_manager, rate_limit_ms=1000)

                for league_id in self.liga128_ids:
                    target_year = loader_service.detect_current_season_year(league_id)
                    if target_year is None:
                        target_year = datetime.now().year
                    self.after(
                        0,
                        lambda lid=league_id, ty=target_year: self.status_label.config(
                            text=f"Lade Spiele für Liga {lid} (Saison {ty})..."
                        )
                        if hasattr(self, "status_label")
                        else None,
                    )

                    def progress_callback(current, total, message, lid=league_id):
                        self.after(
                            0,
                            lambda: self.status_label.config(
                                text=f"Lade Spiele für Liga {lid}: {message} ({current}/{total})"
                            )
                            if hasattr(self, "status_label")
                            else None,
                        )

                    loader_service.load_games_for_league(
                        league_id,
                        target_year,
                        progress_callback=progress_callback,
                        load_details=True,
                        skip_existing=True,
                    )

                self.after(0, lambda: self.status_label.config(text="Aktualisiere Liga-Daten..."))
                self.leagues = self._load_leagues_from_database()
                self.after(0, self.load_league_games_counts)
                if hasattr(self, "leagues_tree_max_streaks"):
                    self.after(0, self.load_max_streaks)
                self.after(0, lambda: self.status_label.config(text="Aktualisierung abgeschlossen"))
            except Exception as e:
                import traceback

                print(f"[ERROR] Liga128 refresh: {e}")
                traceback.print_exc()
                self.after(
                    0,
                    lambda: messagebox.showerror("Fehler", f"Liga-128-Aktualisierung fehlgeschlagen:\n{e}"),
                )

        threading.Thread(target=refresh_in_thread, daemon=True).start()

    def reload_league_list_from_database(self):
        """Nach Import / JSON-Änderung: IDs neu lesen und Tabellen neu füllen."""
        try:
            self.liga128_ids = load_liga128_ids()
            self.leagues = self._load_leagues_from_database()
            if getattr(self, "leagues_tree_25", None):
                self.load_league_games_counts()
            if hasattr(self, "leagues_tree_max_streaks"):
                self.load_max_streaks()
        except Exception as e:
            print(f"[ERROR] League128Tab.reload_league_list_from_database: {e}")

    def show_games_list(self, event):
        """Immer Saison 2026 als bevorzugtes Jahr."""
        original_year = getattr(self, "year", "2026")
        self.year = "2026"
        try:
            return LeagueTab.show_games_list(self, event)
        finally:
            self.year = original_year
