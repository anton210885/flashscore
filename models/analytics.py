"""Analytics model
"""
from dataclasses import dataclass


@dataclass
class Analytics:
    match_id: int
    possession_home: float
    possession_away: float
    xg_home: float
    xg_away: float


@dataclass
class LeagueStats:
    league_name: str
    country: str
    games: int
    o25_percent: float
    o35_percent: float
    o45_percent: float
    o25_streak: int
    o35_streak: int
    o45_streak: int
    o25_trend: str  # ↑ ↓ →
    o35_trend: str
    o45_trend: str
    o25_alarm: bool
    o35_alarm: bool
    o45_alarm: bool
