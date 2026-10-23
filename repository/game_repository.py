"""Zentrale Datenquelle für Spiele (in-memory stub)
"""
from typing import Dict, Optional
from models.game import Game


class GameRepository:
    def __init__(self):
        self._store: Dict[int, Game] = {}

    def save(self, game: Game) -> None:
        self._store[game.id] = game

    def get(self, game_id: int) -> Optional[Game]:
        return self._store.get(game_id)

    def list_all(self):
        return list(self._store.values())
