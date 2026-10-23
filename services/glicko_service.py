"""Glicko-2 wrapper / fetcher (uses SStats API)

Provides method to fetch Glicko predictions for a match from the API.
"""
from typing import Any, Dict, Optional


class GlickoService:
    def __init__(self, client=None):
        """`client` should be an instance of `SStatsClient` or similar with
        `get_game_glicko(game_id)` method.
        """
        self.client = client

    def fetch_glicko(self, game_id: str) -> Dict[str, Any]:
        """Fetch Glicko information for a given match id via the API client.

        Returns the raw dictionary from the API (home/away ratings, probabilities, etc.).
        """
        if not self.client:
            raise RuntimeError("No API client configured for GlickoService")
        return self.client.get_game_glicko(game_id)

    def rate(self, *args, **kwargs):
        raise NotImplementedError("Local Glicko calculation not implemented; use fetch_glicko")
