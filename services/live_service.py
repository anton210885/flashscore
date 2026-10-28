"""Live games logic (stub)
"""
from typing import List
from models.game import Game


def status_to_text(status_num):
    """Map status number to readable text."""
    if not status_num:
        return ""
    try:
        status_int = int(status_num)
    except ValueError:
        return str(status_num)
    mapping = {
        1: "Not Started",
        2: "1st Half",
        3: "Half Time",
        4: "2nd Half",
        5: "Extra Time",
        6: "Penalties",
        7: "Finished",
        8: "Finished",
        9: "Finished (ET)",
        10: "Finished (Pen)",
        11: "ET Break",
        12: "Postponed",
        13: "Interrupted",
        14: "Cancelled",
        15: "Abandoned",
        17: "Technical Loss",
        18: "Walkover",
        19: "In Progress"
    }
    text = mapping.get(status_int, f"Status {status_int}")
    # Add LIVE indicator for live games
    if status_int in {3, 4, 5, 6, 7, 11, 19}:
        text = f"LIVE - {text}"
    return text


class LiveService:
    def __init__(self, client):
        self.client = client

    def fetch_live_game(self, game_id: int) -> Game:
        data = self.client.get_game(game_id)
        # Map API response to Game model (simple mapping)
        return Game(
            id=data.get("id", game_id),
            home_team=data.get("home_team", ""),
            away_team=data.get("away_team", ""),
            score_home=data.get("score_home", 0),
            score_away=data.get("score_away", 0),
            status=data.get("status", "")
        )

    def fetch_live_games(self) -> List[Game]:
        """Fetch today's games (ended, live, upcoming) from the client and map to Game models."""
        # Use Today=True to get all matches for today, including ended, live, and upcoming
        from config import config as cfg

        params = {"Today": True}
        try:
            params["TimeZone"] = cfg.timezone_offset()
        except Exception:
            pass

        raw = self.client.get_games(params)
        games: List[Game] = []
        for item in raw:
            gid = item.get("id") or item.get("Id") or item.get("gameId")
            # Many fields are nested per OpenAPI: homeTeam:{name:..}, awayTeam:{name:..}
            home = ""
            away = ""
            if isinstance(item.get("homeTeam"), dict):
                home = item["homeTeam"].get("name") or item["homeTeam"].get("teamName")
            home = home or item.get("homeTeamName") or item.get("home_team") or item.get("home")
            if isinstance(item.get("awayTeam"), dict):
                away = item["awayTeam"].get("name") or item["awayTeam"].get("teamName")
            away = away or item.get("awayTeamName") or item.get("away_team") or item.get("away")

            sh = item.get("homeResult") or item.get("homeFTResult") or item.get("score_home") or item.get("scoreHome") or 0
            sa = item.get("awayResult") or item.get("awayFTResult") or item.get("score_away") or item.get("scoreAway") or 0

            # League and country extraction - based on API structure: season.league
            league_id = None
            league_name = None
            country = None
            season = item.get("season")
            if season and isinstance(season, dict):
                league_obj = season.get("league")
                if league_obj and isinstance(league_obj, dict):
                    league_id = league_obj.get("id") or league_obj.get("leagueId")
                    league_name = league_obj.get("name") or league_obj.get("leagueName")
                    # country nested in league
                    league_country = league_obj.get("country")
                    if isinstance(league_country, dict):
                        country = league_country.get("name")
                    else:
                        country = league_country
            # fallback if no season.league, check top-level league
            if not league_name:
                league_fallback = item.get("league")
                if isinstance(league_fallback, dict):
                    league_id = league_fallback.get("id") or league_id
                    league_name = league_fallback.get("name") or league_fallback.get("leagueName")
                    league_country = league_fallback.get("country")
                    if isinstance(league_country, dict):
                        country = league_country.get("name") or country
                    else:
                        country = league_country or country
            # final fallbacks
            league_name = league_name or item.get("leagueName") or item.get("LeagueName")
            country = country or item.get("country") or item.get("countryName")

            status_num = item.get("status") or item.get("statusName") or item.get("state")
            status_text = status_to_text(status_num)

            games.append(
                Game(
                    id=int(gid) if gid is not None else 0,
                    home_team=home or "",
                    away_team=away or "",
                    score_home=int(sh) if sh is not None else 0,
                    score_away=int(sa) if sa is not None else 0,
                    status=str(status_num) if status_num is not None else "",
                    league_id=str(league_id) if league_id is not None else None,
                    league_name=league_name,
                    country=country,
                    status_text=status_text
                )
            )
        return games
