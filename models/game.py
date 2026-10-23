"""Domain model: Game
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class Game:
    id: int
    home_team: str
    away_team: str
    score_home: int = 0
    score_away: int = 0
    status: str = ""
    league_id: Optional[str] = None
    league_name: Optional[str] = None
    country: Optional[str] = None
    status_text: Optional[str] = None
