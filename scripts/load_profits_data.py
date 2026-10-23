"""Load profit data for games in database"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import DatabaseManager
from config import config as cfg
from api.sstats_client import SStatsClient
import sqlite3


def load_profits_data():
    """Load profit data for all games in database"""
    print("=" * 70)
    print("Loading Profit Data for Games")
    print("=" * 70)
    print()
    
    db_path = "data/flashscore.db"
    db_manager = DatabaseManager(db_path)
    client = SStatsClient(base_url=cfg.BASE_URL, api_key=getattr(cfg, 'API_KEY', None))
    
    conn = db_manager.get_connection()
    conn.row_factory = sqlite3.Row
    
    # Get all games
    all_games = conn.execute("SELECT id FROM games ORDER BY date DESC").fetchall()
    total = len(all_games)
    
    print(f"Found {total} games in database")
    print(f"Starting load... (estimated time: ~{total // 60} minutes)")
    print()
    
    # Load profit data
    loaded = 0
    errors = 0
    no_data = 0
    last_request_time = 0
    rate_limit = 1.0
    
    print("=" * 70)
    print("Loading profit data...")
    print("=" * 70)
    
    for idx, row in enumerate(all_games):
        game_id = row[0]
        
        # Rate limiting
        elapsed = time.time() - last_request_time
        if elapsed < rate_limit:
            time.sleep(rate_limit - elapsed)
        last_request_time = time.time()
        
        try:
            # Fetch profit data
            profits_data = client.get_game_profits(
                game_id, 
                this_league=False, 
                home_away=False, 
                same_games=False, 
                bookie_id=1, 
                limit=25
            )
            
            # Save to database
            if db_manager.save_profits(game_id, profits_data):
                # Verify it was saved
                check = conn.execute("SELECT COUNT(*) FROM game_profits WHERE game_id = ?", (game_id,)).fetchone()[0]
                if check > 0:
                    loaded += 1
                    if loaded % 10 == 0 or (idx + 1) % 50 == 0:
                        print(f"Progress: {idx + 1}/{total} (loaded: {loaded}, no data: {no_data}, errors: {errors})")
                else:
                    no_data += 1
                    if (idx + 1) % 50 == 0:
                        print(f"Progress: {idx + 1}/{total} (loaded: {loaded}, no data: {no_data}, errors: {errors})")
            else:
                no_data += 1
                if (idx + 1) % 50 == 0:
                    print(f"Progress: {idx + 1}/{total} (loaded: {loaded}, no data: {no_data}, errors: {errors})")
        
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "Too Many Requests" in error_msg:
                print(f"\nRate limited at game {game_id}, waiting 10 seconds...")
                time.sleep(10)
                # Retry once
                try:
                    profits_data = client.get_game_profits(
                        game_id, 
                        this_league=False, 
                        home_away=False, 
                        same_games=False, 
                        bookie_id=1, 
                        limit=25
                    )
                    if db_manager.save_profits(game_id, profits_data):
                        check = conn.execute("SELECT COUNT(*) FROM game_profits WHERE game_id = ?", (game_id,)).fetchone()[0]
                        if check > 0:
                            loaded += 1
                except:
                    errors += 1
            else:
                errors += 1
                if (idx + 1) % 50 == 0:
                    print(f"Error at game {game_id}: {error_msg[:50]}")
    
    # Final statistics
    print("\n" + "=" * 70)
    print("Loading Complete!")
    print("=" * 70)
    print(f"Successfully loaded: {loaded}")
    print(f"No data available: {no_data}")
    print(f"Errors: {errors}")
    print()
    
    # Check results
    profits_count = conn.execute("SELECT COUNT(*) FROM game_profits").fetchone()[0]
    games_with_profits = conn.execute("SELECT COUNT(DISTINCT game_id) FROM game_profits").fetchone()[0]
    print(f"Total profit records: {profits_count}")
    print(f"Games with profit data: {games_with_profits}")
    
    db_manager.close()
    print("\nDone!")


if __name__ == "__main__":
    load_profits_data()























