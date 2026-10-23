"""Script to reload xG data and statistics for games that are missing them"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import DatabaseManager
from config import config as cfg
from api.sstats_client import SStatsClient
import sqlite3


def reload_xg_data():
    """Reload xG data and statistics for games missing them"""
    print("=" * 70)
    print("Reloading xG Data and Statistics for Existing Games")
    print("=" * 70)
    print()
    
    db_path = "data/flashscore.db"
    db_manager = DatabaseManager(db_path)
    client = SStatsClient(base_url=cfg.BASE_URL, api_key=getattr(cfg, 'API_KEY', None))
    
    # Find games without xG data
    conn = db_manager.get_connection()
    conn.row_factory = sqlite3.Row
    
    games_without_xg = conn.execute("""
        SELECT id FROM games 
        WHERE calculated_xg_home IS NULL OR calculated_xg_away IS NULL
        ORDER BY date DESC
    """).fetchall()
    
    total = len(games_without_xg)
    print(f"Found {total} games without xG data")
    print()
    
    if total == 0:
        print("All games already have xG data!")
        db_manager.close()
        return
    
    # Ask for confirmation
    print(f"This will reload full details for {total} games.")
    print("This may take a while due to rate limiting (1 second per game).")
    print(f"Estimated time: ~{total // 60} minutes")
    print()
    
    response = input("Continue? (yes/no): ").strip().lower()
    if response != 'yes':
        print("Cancelled.")
        db_manager.close()
        return
    
    # Reload games
    loaded = 0
    errors = 0
    rate_limited = 0
    last_request_time = 0
    rate_limit = 1.0  # 1 second between requests
    
    print("\n" + "=" * 70)
    print("Reloading games...")
    print("=" * 70)
    
    for idx, row in enumerate(games_without_xg):
        game_id = row[0]
        
        # Rate limiting
        elapsed = time.time() - last_request_time
        if elapsed < rate_limit:
            time.sleep(rate_limit - elapsed)
        last_request_time = time.time()
        
        try:
            # Fetch full game details
            game_data = client.get_game(game_id)
            
            # Handle API response format - check multiple possible structures
            if isinstance(game_data, dict):
                if "data" in game_data:
                    if isinstance(game_data["data"], dict):
                        if "game" in game_data["data"]:
                            game_data = {"game": game_data["data"]["game"]}
                        else:
                            game_data = {"game": game_data["data"]}
                    else:
                        game_data = {"game": game_data["data"]}
                elif "game" not in game_data:
                    game_data = {"game": game_data}
            
            # Save to database (will update existing game)
            if db_manager.save_game(game_data):
                loaded += 1
                if (idx + 1) % 10 == 0:
                    print(f"Progress: {idx + 1}/{total} ({loaded} loaded, {errors} errors)")
            else:
                errors += 1
                print(f"Error saving game {game_id}")
        
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "Too Many Requests" in error_msg:
                rate_limited += 1
                print(f"Rate limited at game {game_id}, waiting 5 seconds...")
                time.sleep(5)
                # Retry once
                try:
                    game_data = client.get_game(game_id)
                    if "data" in game_data and isinstance(game_data["data"], dict):
                        if "game" in game_data["data"]:
                            game_data = {"game": game_data["data"]["game"]}
                        else:
                            game_data = {"game": game_data["data"]}
                    elif "game" not in game_data:
                        game_data = {"game": game_data}
                    
                    if db_manager.save_game(game_data):
                        loaded += 1
                    else:
                        errors += 1
                except:
                    errors += 1
            else:
                errors += 1
                print(f"Error loading game {game_id}: {error_msg[:50]}")
    
    # Final statistics
    print("\n" + "=" * 70)
    print("Reload Complete!")
    print("=" * 70)
    print(f"Successfully reloaded: {loaded}")
    print(f"Errors: {errors}")
    print(f"Rate limited: {rate_limited}")
    print()
    
    # Check results
    with_xg = conn.execute("""
        SELECT COUNT(*) FROM games 
        WHERE calculated_xg_home IS NOT NULL AND calculated_xg_away IS NOT NULL
    """).fetchone()[0]
    
    stats_count = conn.execute("SELECT COUNT(*) FROM game_statistics").fetchone()[0]
    
    print("Updated Statistics:")
    print(f"  Games with xG data: {with_xg}")
    print(f"  Games with statistics: {stats_count}")
    
    db_manager.close()


if __name__ == "__main__":
    reload_xg_data()

