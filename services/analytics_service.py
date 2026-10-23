"""Analytics data extraction
"""
from models.analytics import Analytics, LeagueStats
from typing import List, Optional
import datetime


class AnalyticsService:
    def __init__(self, client):
        self.client = client

    def compute_match_analytics(self, game_id: int) -> Analytics:
        # placeholder - compute analytics from repository/game data
        return Analytics(match_id=game_id, possession_home=50.0, possession_away=50.0, xg_home=0.0, xg_away=0.0)

    def get_league_stats(self, league_id: int, league_name: str, country: str, season: Optional[str] = None) -> LeagueStats:
        # Fetch games for the league
        params = {
            'leagueId': league_id,
        }
        if season:
            params['season'] = season
        else:
            params['season'] = "2026"  # Default to current season (26/27)

        # Limit to recent games, say last 1000
        params['limit'] = 1000

        response = self.client.get_games(params)
        games = response if isinstance(response, list) else []

        # Filter to games with scores (ended games)
        games = [g for g in games if g.get('homeFTResult') is not None and g.get('awayFTResult') is not None]

        # Filter by year if season specified
        if season and season != "All":
            games = [g for g in games if g.get('date', '').startswith(season)]

        if not games:
            return LeagueStats(
                league_name=league_name,
                country=country,
                games=0,
                o25_percent=0.0,
                o35_percent=0.0,
                o45_percent=0.0,
                o25_streak=0,
                o35_streak=0,
                o45_streak=0,
                o25_trend='→',
                o35_trend='→',
                o45_trend='→',
                o25_alarm=False,
                o35_alarm=False,
                o45_alarm=False
            )

        # Sort games by date descending (most recent first)
        games.sort(key=lambda g: g.get('date', ''), reverse=True)

        total_games = len(games)
        o25_count = 0
        o35_count = 0
        o45_count = 0

        streaks = {'o25': 0, 'o35': 0, 'o45': 0}
        trends = {'o25': '→', 'o35': '→', 'o45': '→'}
        alarms = {'o25': False, 'o35': False, 'o45': False}

        for game in games:
            score_home = game.get('homeFTResult', 0) or 0
            score_away = game.get('awayFTResult', 0) or 0
            total_goals = score_home + score_away

            if total_goals > 2.5:
                o25_count += 1
            if total_goals > 3.5:
                o35_count += 1
            if total_goals > 4.5:
                o45_count += 1

        o25_percent = (o25_count / total_games) * 100 if total_games > 0 else 0
        o35_percent = (o35_count / total_games) * 100 if total_games > 0 else 0
        o45_percent = (o45_count / total_games) * 100 if total_games > 0 else 0

        # Compute streaks (last 10 games)
        recent_games = games[:10]
        for i, game in enumerate(recent_games):
            score_home = game.get('scoreHome', 0) or 0
            score_away = game.get('scoreAway', 0) or 0
            total_goals = score_home + score_away

            if i == 0:
                if total_goals > 2.5:
                    streaks['o25'] = 1
                else:
                    streaks['o25'] = -1
                if total_goals > 3.5:
                    streaks['o35'] = 1
                else:
                    streaks['o35'] = -1
                if total_goals > 4.5:
                    streaks['o45'] = 1
                else:
                    streaks['o45'] = -1
            else:
                if total_goals > 2.5:
                    if streaks['o25'] > 0:
                        streaks['o25'] += 1
                    else:
                        streaks['o25'] = 1
                else:
                    if streaks['o25'] < 0:
                        streaks['o25'] -= 1
                    else:
                        streaks['o25'] = -1
                # Similar for o35, o45
                if total_goals > 3.5:
                    if streaks['o35'] > 0:
                        streaks['o35'] += 1
                    else:
                        streaks['o35'] = 1
                else:
                    if streaks['o35'] < 0:
                        streaks['o35'] -= 1
                    else:
                        streaks['o35'] = -1
                if total_goals > 4.5:
                    if streaks['o45'] > 0:
                        streaks['o45'] += 1
                    else:
                        streaks['o45'] = 1
                else:
                    if streaks['o45'] < 0:
                        streaks['o45'] -= 1
                    else:
                        streaks['o45'] = -1

        # Trends: compare recent 5 vs overall
        if total_games >= 10:
            recent_5 = games[:5]
            recent_o25 = sum(1 for g in recent_5 if (g.get('homeFTResult', 0) or 0) + (g.get('awayFTResult', 0) or 0) > 2.5)
            recent_o25_pct = (recent_o25 / 5) * 100
            if recent_o25_pct > o25_percent + 5:
                trends['o25'] = '↑'
            elif recent_o25_pct < o25_percent - 5:
                trends['o25'] = '↓'
            # Similar for others
            recent_o35 = sum(1 for g in recent_5 if (g.get('homeFTResult', 0) or 0) + (g.get('awayFTResult', 0) or 0) > 3.5)
            recent_o35_pct = (recent_o35 / 5) * 100
            if recent_o35_pct > o35_percent + 5:
                trends['o35'] = '↑'
            elif recent_o35_pct < o35_percent - 5:
                trends['o35'] = '↓'
            recent_o45 = sum(1 for g in recent_5 if (g.get('homeFTResult', 0) or 0) + (g.get('awayFTResult', 0) or 0) > 4.5)
            recent_o45_pct = (recent_o45 / 5) * 100
            if recent_o45_pct > o45_percent + 5:
                trends['o45'] = '↑'
            elif recent_o45_pct < o45_percent - 5:
                trends['o45'] = '↓'

        # Alarms: if streak >= 4 or <= -4
        alarms['o25'] = abs(streaks['o25']) >= 4
        alarms['o35'] = abs(streaks['o35']) >= 4
        alarms['o45'] = abs(streaks['o45']) >= 4

        return LeagueStats(
            league_name=league_name,
            country=country,
            games=total_games,
            o25_percent=round(o25_percent, 1),
            o35_percent=round(o35_percent, 1),
            o45_percent=round(o45_percent, 1),
            o25_streak=streaks['o25'],
            o35_streak=streaks['o35'],
            o45_streak=streaks['o45'],
            o25_trend=trends['o25'],
            o35_trend=trends['o35'],
            o45_trend=trends['o45'],
            o25_alarm=alarms['o25'],
            o35_alarm=alarms['o35'],
            o45_alarm=alarms['o45']
        )
