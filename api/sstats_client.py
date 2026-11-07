"""Low-level SStats API client (minimal stub)
"""
import os
import requests
import time
from typing import Any, Dict, Optional, List


class SStatsClient:
    def __init__(self, base_url: str, api_key: Optional[str] = None, session: Optional[requests.Session] = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or ""
        self.session = session or requests.Session()
        # Oracle-Server: sstats bricht grosse Antworten an Cloud-IPs ab -> Umweg ueber
        # Cloudflare WARP (SSTATS_PROXY=socks5h://127.0.0.1:40000 in der .env, siehe deploy/ORACLE.md)
        proxy = os.environ.get("SSTATS_PROXY")
        if proxy:
            self.session.proxies = {"http": proxy, "https": proxy}
        # API can be slow at peak times; keep defaults resilient.
        self.request_timeout = 10
        self.max_retries = 4
        self.retry_initial_delay = 3.0

    def _headers(self) -> Dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _make_request_with_retry(
        self,
        method: str,
        url: str,
        max_retries: Optional[int] = None,
        initial_delay: Optional[float] = None,
        **kwargs
    ) -> requests.Response:
        """
        Make HTTP request with automatic retry on rate limiting (429 errors)
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            max_retries: Maximum number of retries (default: 3)
            initial_delay: Initial delay in seconds before retry (default: 5.0)
            **kwargs: Additional arguments to pass to requests method
            
        Returns:
            Response object
            
        Raises:
            requests.HTTPError: If request fails after all retries
        """
        max_retries = self.max_retries if max_retries is None else max_retries
        retry_delay = self.retry_initial_delay if initial_delay is None else initial_delay
        
        for attempt in range(max_retries):
            try:
                resp = self.session.request(method, url, **kwargs)
                
                # If we get a 429 (Too Many Requests), wait and retry
                if resp.status_code == 429:
                    if attempt < max_retries - 1:
                        # Exponential backoff: wait longer each time
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Double the delay for next retry
                        continue
                    else:
                        # Last attempt failed, raise the error
                        resp.raise_for_status()
                
                # For other status codes, check if they're errors
                resp.raise_for_status()
                return resp
                
            except requests.Timeout:
                # Retry transient read/connect timeout failures.
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                raise
            except requests.ConnectionError:
                # Retry transient network/connectivity failures.
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                raise
            except requests.HTTPError as e:
                # Check if it's a 429 error
                if hasattr(e.response, 'status_code') and e.response.status_code == 429:
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                # For other errors or if we've exhausted retries, re-raise
                raise
            except Exception as e:
                # For non-HTTP errors, check if error message contains 429
                error_str = str(e)
                if "429" in error_str or "Too Many Requests" in error_str:
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                raise
        
        # This should never be reached, but just in case
        raise requests.HTTPError("Request failed after retries")

    def get_game(self, game_id: int) -> Dict[str, Any]:
        """GET /Games/{game_id} - with automatic retry on rate limiting"""
        url = f"{self.base_url}/Games/{game_id}"
        resp = self._make_request_with_retry("GET", url, headers=self._headers(), timeout=self.request_timeout)
        return resp.json()

    def get_games(self, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """GET /Games/list with optional query params. Returns list of game dicts.

        Uses `/Games/list` endpoint from SStats OpenAPI. If the API returns the
        standard `ApiResponse` wrapper, the list is returned from `data`.

        Die API liefert höchstens 1000 Spiele pro Abfrage. Ohne eigenes `Offset`/`Limit`
        wird darum weitergeblättert, bis eine Seite kürzer ist (sonst fehlen z.B. an vollen
        Samstagen die Abendspiele in der Today-Liste).
        """
        query = dict(params or {})
        if any(k.lower() in ("offset", "limit") for k in query):
            return self._get_games_page(query)

        out: List[Dict[str, Any]] = []
        seen: set = set()
        offset = 0
        while True:
            page = self._get_games_page({**query, "Offset": offset})
            new = [g for g in page if not isinstance(g, dict) or g.get("id") not in seen]
            seen.update(g.get("id") for g in new if isinstance(g, dict))
            out.extend(new)
            if len(page) < self.GAMES_PAGE_SIZE or not new:
                return out
            offset += len(page)

    GAMES_PAGE_SIZE = 1000

    def _get_games_page(self, query: Dict[str, Any]) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/games/list"
        # API expects API key as query param `apikey` according to OpenAPI
        query = dict(query)
        if self.api_key:
            query.setdefault("apikey", self.api_key)

        resp = self._make_request_with_retry("GET", url, headers=self._headers(), params=query, timeout=self.request_timeout)
        data = resp.json()
        # SStats commonly returns ApiResponse wrapper: {status,count,data: [...]}
        if isinstance(data, dict):
            if "data" in data and isinstance(data["data"], list):
                return data["data"]
            # fallback patterns
            for key in ("games", "results"): 
                if key in data and isinstance(data[key], list):
                    return data[key]
            for v in data.values():
                if isinstance(v, list):
                    return v
            return []
        if isinstance(data, list):
            return data
        return []

    def get_game_glicko(self, game_id: str) -> Dict[str, Any]:
        """GET /games/glicko/{id} - returns Glicko 2 rating and prediction for a match.

        According to the OpenAPI spec this endpoint is `/Games/glicko/{id}`.
        We call `/games/glicko/{id}` (lowercase path used elsewhere) and include
        `apikey` as query param if available.
        """
        url = f"{self.base_url}/games/glicko/{game_id}"
        params = {}
        if self.api_key:
            params["apikey"] = self.api_key
        resp = self._make_request_with_retry("GET", url, headers=self._headers(), params=params, timeout=self.request_timeout)
        data = resp.json()
        # Usually wrapped in ApiResponse: {data: {...}}
        if isinstance(data, dict) and "data" in data:
            return data["data"] or {}
        return data or {}
    
    def get_game_profits(self, game_id: int, this_league: bool = False, home_away: bool = False, 
                         same_games: bool = False, bookie_id: int = 1, limit: int = 25) -> Dict[str, Any]:
        """GET /Games/profits - returns profit data for a game
        
        Args:
            game_id: Game ID
            this_league: Filter by same league
            home_away: Filter by home/away
            same_games: Filter by same games
            bookie_id: Bookie ID (default: 1)
            limit: Limit number of games (default: 25)
        """
        url = f"{self.base_url}/Games/profits"
        params = {
            "gameId": game_id,
            "thisLeague": str(this_league).lower(),
            "homeAway": str(home_away).lower(),
            "sameGames": str(same_games).lower(),
            "bookieId": bookie_id,
            "limit": limit
        }
        if self.api_key:
            params["apikey"] = self.api_key
        resp = self._make_request_with_retry("GET", url, headers=self._headers(), params=params, timeout=self.request_timeout)
        return resp.json()
    
    def get_game_odds(self, game_id: int, bookmaker_id: Optional[int] = None, opening: bool = False) -> Dict[str, Any]:
        """GET /Odds/{game_id} - returns odds data for a game
        
        Args:
            game_id: Game ID
            bookmaker_id: Optional bookmaker ID (empty string if None)
            opening: If True, return opening odds (default: False)
        """
        url = f"{self.base_url}/Odds/{game_id}"
        params = {
            "opening": str(opening).lower()
        }
        if bookmaker_id is not None:
            params["bookmakerId"] = bookmaker_id
        else:
            params["bookmakerId"] = ""  # Empty string as per API example
        if self.api_key:
            params["apikey"] = self.api_key
        resp = self._make_request_with_retry("GET", url, headers=self._headers(), params=params, timeout=self.request_timeout)
        return resp.json()