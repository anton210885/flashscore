"""Service for loading finished games into the database"""
import time
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
import requests


class GameLoaderService:
    """Service to load finished games from API into database"""
    
    def __init__(self, api_client, db_manager, rate_limit_ms: int = 1000):
        """
        Initialize game loader service
        
        Args:
            api_client: SStatsClient instance
            db_manager: DatabaseManager instance
            rate_limit_ms: Milliseconds to wait between API requests
        """
        self.api_client = api_client
        self.db_manager = db_manager
        self.rate_limit_ms = rate_limit_ms / 1000.0  # Convert to seconds
        self.last_request_time = 0
    
    def _rate_limit(self):
        """Enforce rate limiting between API requests"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit_ms:
            time.sleep(self.rate_limit_ms - elapsed)
        self.last_request_time = time.time()
    
    def _is_finished(self, game: Dict[str, Any]) -> bool:
        """Check if a game is finished"""
        status = game.get("status")
        status_name = game.get("statusName", "")
        return (status in [7, 8, 9, 10] or 
                status_name == "Finished" or 
                "Finished" in str(status_name))
    
    def detect_current_season_year(self, league_id: int) -> Optional[int]:
        """
        Automatically detect the current season year for a league by checking recent games
        
        Args:
            league_id: League ID
            
        Returns:
            The most recent season year found, or None if no games found
        """
        current_year = datetime.now().year
        
        # Check current year, next year, and previous year (some leagues start early)
        years_to_check = [current_year + 1, current_year, current_year - 1]
        
        for year in years_to_check:
            try:
                params = {"leagueid": league_id, "year": year}
                self._rate_limit()
                all_games = self.api_client.get_games(params)
                
                if all_games:
                    # Check if there are finished games for this year
                    finished_count = 0
                    for game in all_games:
                        if self._is_finished(game):
                            finished_count += 1
                    
                    # If we found finished games, this is likely the current season
                    if finished_count > 0:
                        return year
            except Exception as e:
                # Continue to next year if this one fails
                continue
        
        # Fallback: try without year parameter to get latest games
        try:
            params = {"leagueid": league_id}
            self._rate_limit()
            all_games = self.api_client.get_games(params)
            
            if all_games:
                # Find the most recent season year from games
                season_years = set()
                for game in all_games:
                    if self._is_finished(game):
                        # Check season.year field
                        season = game.get("season")
                        if season and isinstance(season, dict):
                            season_year = season.get("year")
                            if season_year:
                                season_years.add(season_year)
                        
                        # Check date field
                        game_date = game.get("date") or game.get("gameDate") or ""
                        if game_date:
                            try:
                                if "T" in str(game_date):
                                    dt = datetime.fromisoformat(str(game_date).replace("Z", "+00:00"))
                                    season_years.add(dt.year)
                            except:
                                pass
                
                if season_years:
                    return max(season_years)
        except Exception as e:
            pass
        
        return None
    
    def fetch_finished_games_list(self, league_id: int, year: int) -> List[Dict[str, Any]]:
        """
        Fetch list of finished games for a league and year
        
        Args:
            league_id: League ID
            year: Year to fetch games for
            
        Returns:
            List of finished game summaries (without full details)
        """
        params = {"leagueid": league_id, "year": year}
        self._rate_limit()
        all_games = self.api_client.get_games(params)
        
        # Filter finished games by date
        finished_games = []
        year_int = int(year)
        
        for game in all_games:
            if not self._is_finished(game):
                continue
            
            # Check date field
            game_date = game.get("date") or game.get("gameDate") or ""
            if game_date:
                try:
                    if "T" in str(game_date):
                        dt = datetime.fromisoformat(str(game_date).replace("Z", "+00:00"))
                        if dt.year == year_int:
                            finished_games.append(game)
                            continue
                except:
                    pass
            
            # Fallback: check season.year field
            season = game.get("season")
            if season and isinstance(season, dict):
                season_year = season.get("year")
                if season_year == year_int:
                    finished_games.append(game)
        
        return finished_games
    
    def load_games_for_league(
        self, 
        league_id: int, 
        year: int,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        load_details: bool = True,
        skip_existing: bool = True
    ) -> Dict[str, Any]:
        """
        Load all finished games for a league and year into database
        
        Args:
            league_id: League ID
            year: Year to load
            progress_callback: Optional callback(current, total, message)
            load_details: If True, fetch full game details. If False, only save basic info.
            
        Returns:
            Dictionary with loading statistics
        """
        stats = {
            "total_found": 0,
            "loaded": 0,
            "skipped": 0,
            "errors": 0,
            "already_exists": 0
        }
        
        # Check if games already exist in DB and which ones have xG data
        # Convert year to int if it's a string
        year_int = int(year) if isinstance(year, str) else year
        existing_games = self.db_manager.get_games_by_league(league_id, year_int)
        existing_ids_with_xg = {
            g["id"] for g in existing_games 
            if g.get("calculated_xg_home") is not None and g.get("calculated_xg_away") is not None
        }
        existing_ids = {g["id"] for g in existing_games}
        
        # Fetch list of finished games
        if progress_callback:
            progress_callback(0, 0, f"Fetching games list for league {league_id}, year {year}...")
        
        finished_games = self.fetch_finished_games_list(league_id, year_int)
        stats["total_found"] = len(finished_games)
        
        if not finished_games:
            if progress_callback:
                progress_callback(0, 0, f"No finished games found for league {league_id}, year {year}")
            return stats
        
        # Load each game
        for idx, game_summary in enumerate(finished_games):
            game_id = game_summary.get("id")
            if not game_id:
                stats["errors"] += 1
                continue
            
            # Check if already exists
            if game_id in existing_ids:
                if skip_existing:
                    # "Load Latest Games" mode - skip ALL existing games (regardless of xG)
                    stats["already_exists"] += 1
                    if progress_callback:
                        if game_id in existing_ids_with_xg:
                            progress_callback(idx + 1, len(finished_games), 
                                            f"Skipping {game_id} (already exists)")
                        else:
                            progress_callback(idx + 1, len(finished_games), 
                                            f"Skipping {game_id} (already exists, no xG)")
                    continue
                else:
                    # Update mode - reload if missing xG
                    if game_id in existing_ids_with_xg:
                        # Has xG - skip
                        stats["already_exists"] += 1
                        if progress_callback:
                            progress_callback(idx + 1, len(finished_games), 
                                            f"Skipping {game_id} (already has xG data)")
                        continue
                    else:
                        # Exists but no xG - reload if load_details is True
                        if load_details:
                            if progress_callback:
                                progress_callback(idx + 1, len(finished_games), 
                                                f"Updating {game_id} (missing xG data)...")
                        else:
                            # Summary mode - skip
                            stats["already_exists"] += 1
                            if progress_callback:
                                progress_callback(idx + 1, len(finished_games), 
                                                f"Skipping {game_id} (already exists)")
                            continue
            
            try:
                if load_details:
                    # Fetch full game details
                    if progress_callback:
                        progress_callback(idx + 1, len(finished_games), 
                                        f"Loading game {game_id}...")
                    
                    self._rate_limit()
                    
                    # Retry logic for rate limiting
                    max_retries = 3
                    retry_delay = 5  # seconds
                    game_data = None
                    
                    for retry in range(max_retries):
                        try:
                            game_data = self.api_client.get_game(game_id)
                            break
                        except Exception as e:
                            if "429" in str(e) or "Too Many Requests" in str(e):
                                if retry < max_retries - 1:
                                    if progress_callback:
                                        progress_callback(idx + 1, len(finished_games), 
                                                        f"Rate limited, waiting {retry_delay}s...")
                                    time.sleep(retry_delay)
                                    retry_delay *= 2  # Exponential backoff
                                    continue
                            raise
                    
                    if game_data is None:
                        raise Exception("Failed to fetch game data after retries")
                    
                    # API returns: {"status": "OK", "data": {"game": {...}, "statistics": {...}}}
                    # Pass the full response to save_game - it will extract game and statistics correctly
                    # No transformation needed - save_game handles the structure
                else:
                    # Use summary data only (limited statistics)
                    game_data = {"game": game_summary}
                
                # Save to database
                if self.db_manager.save_game(game_data):
                    stats["loaded"] += 1
                    if progress_callback:
                        progress_callback(idx + 1, len(finished_games), 
                                        f"Saved game {game_id}")
                else:
                    stats["errors"] += 1
                    if progress_callback:
                        progress_callback(idx + 1, len(finished_games), 
                                        f"Error saving game {game_id}")
                        
            except Exception as e:
                stats["errors"] += 1
                error_msg = str(e)
                if "429" in error_msg or "Too Many Requests" in error_msg:
                    error_msg = "Rate limited"
                if progress_callback:
                    progress_callback(idx + 1, len(finished_games), 
                                    f"Error loading game {game_id}: {error_msg}")
        
        return stats
    
    def load_games_for_multiple_leagues(
        self,
        leagues: List[Dict[str, Any]],
        years: List[int],
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        load_details: bool = True
    ) -> Dict[str, Any]:
        """
        Load finished games for multiple leagues and years
        
        Args:
            leagues: List of league dicts with 'id' key
            years: List of years to load
            progress_callback: Optional callback(current, total, message)
            load_details: If True, fetch full game details
            
        Returns:
            Dictionary with overall statistics
        """
        total_combinations = len(leagues) * len(years)
        current = 0
        overall_stats = {
            "total_loaded": 0,
            "total_skipped": 0,
            "total_errors": 0,
            "total_already_exists": 0,
            "league_stats": {}
        }
        
        for league in leagues:
            league_id = league.get("id")
            league_name = league.get("name", f"League {league_id}")
            
            for year in years:
                current += 1
                if progress_callback:
                    progress_callback(current, total_combinations, 
                                    f"Loading {league_name} {year}...")
                
                stats = self.load_games_for_league(
                    league_id, year, 
                    progress_callback=None,  # Don't show individual game progress
                    load_details=load_details
                )
                
                overall_stats["total_loaded"] += stats["loaded"]
                overall_stats["total_skipped"] += stats["skipped"]
                overall_stats["total_errors"] += stats["errors"]
                overall_stats["total_already_exists"] += stats["already_exists"]
                
                key = f"{league_name} {year}"
                overall_stats["league_stats"][key] = stats
        
        return overall_stats

