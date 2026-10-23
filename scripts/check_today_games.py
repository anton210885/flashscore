"""Check for games from today and load them if finished"""
import sys
from pathlib import Path
from datetime import datetime, timezone

# Fix encoding for Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import DatabaseManager
from config import config as cfg
from api.sstats_client import SStatsClient
from services.game_loader_service import GameLoaderService

def check_today_games():
    """Check for games from today"""
    print("=" * 70)
    print("Checking for games from today")
    print("=" * 70)
    print()
    
    # Initialize
    client = SStatsClient(base_url=cfg.BASE_URL, api_key=getattr(cfg, 'API_KEY', None))
    db_manager = DatabaseManager("data/flashscore.db")
    loader_service = GameLoaderService(client, db_manager, rate_limit_ms=1000)
    
    # Check A-League (188) for 2025
    league_id = 188
    year = 2025
    
    print(f"Checking League {league_id} ({year})...")
    print()
    
    # Fetch all finished games
    finished_games = loader_service.fetch_finished_games_list(league_id, year)
    
    # Filter games from today
    today = datetime.now(timezone.utc).date()
    today_games = []
    
    for game in finished_games:
        game_date_str = game.get("date")
        if game_date_str:
            try:
                # Parse date (format: "2025-12-27T08:15:00+00:00")
                game_date = datetime.fromisoformat(game_date_str.replace('Z', '+00:00')).date()
                if game_date == today:
                    today_games.append(game)
            except:
                pass
    
    print(f"Total finished games in API: {len(finished_games)}")
    print(f"Games from today ({today}): {len(today_games)}")
    print()
    
    if today_games:
        print("Today's games:")
        for game in today_games:
            game_id = game.get("id")
            home = game.get("homeTeam", {}).get("name", "?")
            away = game.get("awayTeam", {}).get("name", "?")
            status = game.get("status")
            status_name = game.get("statusName", "?")
            date = game.get("date", "?")
            
            # Check if already in DB
            existing = db_manager.get_game(game_id)
            in_db = "[OK]" if existing else "[MISSING]"
            
            print(f"  {in_db} ID {game_id}: {home} vs {away}")
            print(f"      Date: {date}")
            print(f"      Status: {status} ({status_name})")
            print()
        
        # Ask to load missing games
        missing = [g for g in today_games if not db_manager.get_game(g.get("id"))]
        if missing:
            print(f"\n{len(missing)} games not in database. Loading...")
            print()
            
            for game in missing:
                game_id = game.get("id")
                home = game.get("homeTeam", {}).get("name", "?")
                away = game.get("awayTeam", {}).get("name", "?")
                
                print(f"Loading game {game_id}: {home} vs {away}...")
                try:
                    # Load full game details
                    game_data = client.get_game(game_id)
                    if game_data:
                        db_manager.save_game(game_data)
                        print(f"  [OK] Loaded successfully")
                    else:
                        print(f"  [ERROR] Failed to load game data")
                except Exception as e:
                    print(f"  [ERROR] Error: {e}")
                print()
        else:
            print("\nAll today's games are already in the database.")
    else:
        print("No games from today found in the API.")
        print()
        print("Checking recent games (last 7 days)...")
        
        # Check last 7 days
        from datetime import timedelta
        week_ago = today - timedelta(days=7)
        
        recent_games = []
        for game in finished_games:
            game_date_str = game.get("date")
            if game_date_str:
                try:
                    game_date = datetime.fromisoformat(game_date_str.replace('Z', '+00:00')).date()
                    if game_date >= week_ago:
                        recent_games.append(game)
                except:
                    pass
        
        print(f"Recent games (last 7 days): {len(recent_games)}")
        if recent_games:
            print("\nMost recent games:")
            for game in sorted(recent_games, key=lambda g: g.get("date", ""), reverse=True)[:5]:
                game_id = game.get("id")
                home = game.get("homeTeam", {}).get("name", "?")
                away = game.get("awayTeam", {}).get("name", "?")
                date = game.get("date", "?")
                existing = db_manager.get_game(game_id)
                in_db = "[OK]" if existing else "[MISSING]"
                print(f"  {in_db} {date[:10]}: {home} vs {away} (ID: {game_id})")

if __name__ == "__main__":
    check_today_games()

