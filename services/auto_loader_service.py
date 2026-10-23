"""Automatic background service to load finished games into database"""
import time
import threading
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime


class AutoLoaderService:
    """Background service to automatically load finished games"""
    
    def __init__(self, api_client, db_manager, rate_limit_ms: int = 1000):
        """
        Initialize auto loader service
        
        Args:
            api_client: SStatsClient instance
            db_manager: DatabaseManager instance
            rate_limit_ms: Milliseconds to wait between API requests
        """
        self.api_client = api_client
        self.db_manager = db_manager
        self.rate_limit_ms = rate_limit_ms / 1000.0
        self.last_request_time = 0
        self.running = False
        self.thread = None
        self.check_interval = 300  # Check every 5 minutes
        self.leagues_to_monitor = []  # List of league IDs to monitor
        self.status_callback = None
    
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
    
    def _game_exists_in_db(self, game_id: int) -> bool:
        """Check if game already exists in database"""
        game = self.db_manager.get_game(game_id)
        return game is not None
    
    def _load_new_finished_games(self, league_id: int, year: int) -> Dict[str, Any]:
        """
        Load only new finished games for a league and year
        
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
        
        try:
            # Fetch list of finished games
            params = {"leagueid": league_id, "year": year}
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
            
            stats["total_found"] = len(finished_games)
            
            # Load only new games
            for game_summary in finished_games:
                game_id = game_summary.get("id")
                if not game_id:
                    stats["errors"] += 1
                    continue
                
                # Check if already exists
                if self._game_exists_in_db(game_id):
                    stats["already_exists"] += 1
                    continue
                
                try:
                    # Fetch full game details with retry logic
                    self._rate_limit()
                    
                    # Retry logic for rate limiting with exponential backoff
                    max_retries = 3
                    retry_delay = 5  # seconds
                    game_data = None
                    
                    for retry in range(max_retries):
                        try:
                            game_data = self.api_client.get_game(game_id)
                            break
                        except Exception as e:
                            error_msg = str(e)
                            if "429" in error_msg or "Too Many Requests" in error_msg:
                                if retry < max_retries - 1:
                                    if self.status_callback:
                                        self.status_callback(f"Rate limit erreicht, warte {retry_delay}s vor erneutem Versuch für Spiel {game_id}...")
                                    time.sleep(retry_delay)
                                    retry_delay *= 2  # Exponential backoff
                                    continue
                            raise
                    
                    if game_data is None:
                        raise Exception("Failed to fetch game data after retries")
                    
                    # Handle API response format
                    if "data" in game_data and isinstance(game_data["data"], dict):
                        if "game" in game_data["data"]:
                            game_data = {"game": game_data["data"]["game"]}
                        else:
                            game_data = {"game": game_data["data"]}
                    elif "game" not in game_data:
                        game_data = {"game": game_data}
                    
                    # Save to database
                    if self.db_manager.save_game(game_data):
                        stats["loaded"] += 1
                        if self.status_callback:
                            self.status_callback(f"Loaded new game {game_id} ({game_summary.get('homeTeam', {}).get('name', '?')} vs {game_summary.get('awayTeam', {}).get('name', '?')})")
                    else:
                        stats["errors"] += 1
                        
                except Exception as e:
                    error_msg = str(e)
                    stats["errors"] += 1
                    if self.status_callback:
                        self.status_callback(f"Error loading game {game_id}: {error_msg[:100]}")
        
        except Exception as e:
            if self.status_callback:
                self.status_callback(f"Error checking league {league_id}: {str(e)}")
            stats["errors"] += 1
        
        return stats
    
    def add_league_to_monitor(self, league_id: int, years: List[int]):
        """
        Add a league to monitor for new finished games
        
        Args:
            league_id: League ID to monitor
            years: List of years to check
        """
        for year in years:
            key = (league_id, year)
            if key not in self.leagues_to_monitor:
                self.leagues_to_monitor.append(key)
    
    def set_status_callback(self, callback: Callable[[str], None]):
        """Set callback function for status updates"""
        self.status_callback = callback
    
    def _monitor_loop(self):
        """Main monitoring loop that runs in background thread"""
        while self.running:
            try:
                if self.status_callback:
                    self.status_callback("Checking for new finished games...")
                
                total_loaded = 0
                for league_id, year in self.leagues_to_monitor:
                    stats = self._load_new_finished_games(league_id, year)
                    total_loaded += stats["loaded"]
                    
                    if stats["loaded"] > 0 and self.status_callback:
                        self.status_callback(f"League {league_id} {year}: Loaded {stats['loaded']} new games")
                
                if total_loaded == 0 and self.status_callback:
                    self.status_callback(f"No new games found. Next check in {self.check_interval // 60} minutes")
                
            except Exception as e:
                if self.status_callback:
                    self.status_callback(f"Error in monitor loop: {str(e)}")
            
            # Wait before next check
            for _ in range(self.check_interval):
                if not self.running:
                    break
                time.sleep(1)
    
    def start(self, check_interval_seconds: int = 300):
        """
        Start the automatic monitoring service
        
        Args:
            check_interval_seconds: How often to check for new games (default: 5 minutes)
        """
        if self.running:
            return
        
        self.check_interval = check_interval_seconds
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        
        if self.status_callback:
            self.status_callback(f"Auto-loader started. Checking every {check_interval_seconds // 60} minutes")
    
    def stop(self):
        """Stop the automatic monitoring service"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        if self.status_callback:
            self.status_callback("Auto-loader stopped")
    
    def is_running(self) -> bool:
        """Check if the service is currently running"""
        return self.running











