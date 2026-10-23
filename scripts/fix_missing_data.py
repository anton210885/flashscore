"""Script to reload missing xG data and statistics for all games"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import DatabaseManager
from config import config as cfg
from api.sstats_client import SStatsClient
import sqlite3


def fix_missing_data():
    """Reload xG data and statistics for games missing them"""
    print("=" * 70)
    print("Fixing Missing xG Data and Statistics")
    print("=" * 70)
    print()
    
    db_path = "data/flashscore.db"
    db_manager = DatabaseManager(db_path)
    client = SStatsClient(base_url=cfg.BASE_URL, api_key=getattr(cfg, 'API_KEY', None))
    
    conn = db_manager.get_connection()
    conn.row_factory = sqlite3.Row
    
    # Find all games (we'll reload all to ensure they have full data)
    all_games = conn.execute("SELECT id FROM games ORDER BY date DESC").fetchall()
    total = len(all_games)
    
    print(f"Total games in database: {total}")
    print()
    
    # Check how many are missing xG
    missing_xg = conn.execute("""
        SELECT COUNT(*) FROM games 
        WHERE calculated_xg_home IS NULL OR calculated_xg_away IS NULL
    """).fetchone()[0]
    
    print(f"Games missing xG data: {missing_xg}")
    print(f"Estimated time: ~{total // 60} minutes (1 second per game)")
    print()
    
    response = input("Reload all games with full details? (yes/no): ").strip().lower()
    if response != 'yes':
        print("Cancelled.")
        db_manager.close()
        return
    
    # Reload games
    loaded = 0
    errors = 0
    skipped = 0
    last_request_time = 0
    rate_limit = 1.0  # 1 second
    
    print("\n" + "=" * 70)
    print("Reloading games with full details...")
    print("=" * 70)
    
    for idx, row in enumerate(all_games):
        game_id = row[0]
        
        # Rate limiting
        elapsed = time.time() - last_request_time
        if elapsed < rate_limit:
            time.sleep(rate_limit - elapsed)
        last_request_time = time.time()
        
        try:
            # Fetch full game details
            game_data = client.get_game(game_id)
            
            # Handle API response format
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
            
            # Check if game has statistics
            game = game_data.get("game", game_data)
            stats = game.get("statistics", {})
            
            if not stats:
                skipped += 1
                if (idx + 1) % 50 == 0:
                    print(f"Progress: {idx + 1}/{total} (loaded: {loaded}, skipped: {skipped}, errors: {errors})")
                continue
            
            # Save to database
            if db_manager.save_game(game_data):
                loaded += 1
                if (idx + 1) % 10 == 0:
                    print(f"Progress: {idx + 1}/{total} (loaded: {loaded}, skipped: {skipped}, errors: {errors})")
            else:
                errors += 1
        
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "Too Many Requests" in error_msg:
                print(f"\nRate limited at game {game_id}, waiting 10 seconds...")
                time.sleep(10)
                # Retry once
                try:
                    game_data = client.get_game(game_id)
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
                    
                    if db_manager.save_game(game_data):
                        loaded += 1
                    else:
                        errors += 1
                except:
                    errors += 1
            else:
                errors += 1
                if (idx + 1) % 50 == 0:
                    print(f"Error at game {game_id}: {error_msg[:50]}")
    
    # Final statistics
    print("\n" + "=" * 70)
    print("Reload Complete!")
    print("=" * 70)
    print(f"Successfully reloaded: {loaded}")
    print(f"Skipped (no stats): {skipped}")
    print(f"Errors: {errors}")
    print()
    
    # Check results
    with_xg = conn.execute("""
        SELECT COUNT(*) FROM games 
        WHERE calculated_xg_home IS NOT NULL AND calculated_xg_away IS NOT NULL
    """).fetchone()[0]
    
    stats_count = conn.execute("SELECT COUNT(*) FROM game_statistics").fetchone()[0]
    events_count = conn.execute("SELECT COUNT(DISTINCT game_id) FROM game_events").fetchone()[0]
    
    print("Updated Statistics:")
    print(f"  Games with xG data: {with_xg}")
    print(f"  Games with statistics table: {stats_count}")
    print(f"  Games with events: {events_count}")
    
    db_manager.close()


if __name__ == "__main__":
    fix_missing_data()























