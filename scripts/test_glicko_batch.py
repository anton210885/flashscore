"""Test loading Glicko data for a few games"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import DatabaseManager
from config import config as cfg
from api.sstats_client import SStatsClient
import sqlite3

def test_glicko_batch():
    """Test loading Glicko data for a few games"""
    print("=" * 70)
    print("Testing Glicko Data Loading (Batch)")
    print("=" * 70)
    print()
    
    db_manager = DatabaseManager("data/flashscore.db")
    client = SStatsClient(base_url=cfg.BASE_URL, api_key=getattr(cfg, 'API_KEY', None))
    
    conn = db_manager.get_connection()
    conn.row_factory = sqlite3.Row
    
    # Get first 5 games
    games = conn.execute("SELECT id FROM games ORDER BY date DESC LIMIT 5").fetchall()
    
    print(f"Testing with {len(games)} games")
    print()
    
    loaded = 0
    errors = 0
    no_data = 0
    
    for idx, row in enumerate(games):
        game_id = row[0]
        print(f"Game {idx + 1}/{len(games)}: {game_id}")
        
        # Rate limiting
        if idx > 0:
            time.sleep(1.0)
        
        try:
            # Fetch Glicko data
            glicko_data = client.get_game_glicko(str(game_id))
            
            print(f"  API Response keys: {list(glicko_data.keys()) if isinstance(glicko_data, dict) else 'Not a dict'}")
            
            # Check if glicko exists
            if isinstance(glicko_data, dict) and "glicko" in glicko_data:
                glicko = glicko_data["glicko"]
                print(f"  Glicko found: homeRating={glicko.get('homeRating')}, awayRating={glicko.get('awayRating')}")
            else:
                print(f"  [WARNING] No 'glicko' key in response")
                no_data += 1
                continue
            
            # Save to database
            result = db_manager.save_glicko(game_id, glicko_data)
            print(f"  save_glicko returned: {result}")
            
            # Verify it was saved
            check = conn.execute("SELECT COUNT(*) FROM game_glicko WHERE game_id = ?", (game_id,)).fetchone()[0]
            if check > 0:
                loaded += 1
                print(f"  [OK] Saved successfully!")
            else:
                print(f"  [ERROR] save_glicko returned True but data not in database")
                errors += 1
                
        except Exception as e:
            errors += 1
            print(f"  [ERROR] Exception: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 70)
    print("Summary:")
    print("=" * 70)
    print(f"Successfully loaded: {loaded}")
    print(f"No data available: {no_data}")
    print(f"Errors: {errors}")
    
    # Check total
    total = conn.execute("SELECT COUNT(*) FROM game_glicko").fetchone()[0]
    print(f"\nTotal games with Glicko data in database: {total}")
    
    db_manager.close()


if __name__ == "__main__":
    test_glicko_batch()























