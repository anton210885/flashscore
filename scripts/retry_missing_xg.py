"""Retry loading xG data for specific games"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import DatabaseManager
from config import config as cfg
from api.sstats_client import SStatsClient
import sqlite3
import json

def retry_missing_xg():
    """Retry loading xG data for specific games"""
    game_ids = [1123552, 1280751, 1280773, 1280789, 1280790, 1280823, 1280824, 
                1374036, 1375034, 1375203, 1469570, 1469571, 1469572, 1469587, 
                1469588, 1469600]
    
    print("=" * 70)
    print("Retrying xG Data Load for Specific Games")
    print("=" * 70)
    print()
    
    db_manager = DatabaseManager("data/flashscore.db")
    client = SStatsClient(base_url=cfg.BASE_URL, api_key=getattr(cfg, 'API_KEY', None))
    
    conn = db_manager.get_connection()
    conn.row_factory = sqlite3.Row
    
    updated = 0
    no_data = 0
    errors = 0
    
    for idx, game_id in enumerate(game_ids):
        print(f"\nGame {idx + 1}/{len(game_ids)}: {game_id}")
        
        # Rate limiting
        if idx > 0:
            time.sleep(1.0)
        
        try:
            # Fetch from API
            print(f"  Fetching from API...")
            game_data = client.get_game(game_id)
            
            # Debug: Print full response structure
            print(f"  API Response keys: {list(game_data.keys()) if isinstance(game_data, dict) else 'Not a dict'}")
            
            # Extract statistics manually to debug
            if isinstance(game_data, dict):
                if "data" in game_data and isinstance(game_data["data"], dict):
                    data = game_data["data"]
                    stats = data.get("statistics", {})
                    print(f"  Found 'data.statistics': {bool(stats)}")
                    if stats:
                        print(f"  Statistics keys: {list(stats.keys())[:10]}")
                        print(f"  calculatedXgHome: {stats.get('calculatedXgHome')}")
                        print(f"  calculatedXgAway: {stats.get('calculatedXgAway')}")
                else:
                    stats = game_data.get("statistics", {})
                    print(f"  Found 'statistics' at root: {bool(stats)}")
            else:
                stats = {}
            
            # Try to save
            print(f"  Attempting to save...")
            if db_manager.save_game(game_data):
                # Check if xG was actually saved
                check = conn.execute("""
                    SELECT calculated_xg_home, calculated_xg_away 
                    FROM games WHERE id = ?
                """, (game_id,)).fetchone()
                
                if check:
                    xg_home = check['calculated_xg_home']
                    xg_away = check['calculated_xg_away']
                    print(f"  After save - xG Home: {xg_home}, xG Away: {xg_away}")
                    
                    if xg_home is not None or xg_away is not None:
                        updated += 1
                        print(f"  [OK] xG data saved successfully!")
                    else:
                        no_data += 1
                        print(f"  [WARNING] Save returned True but xG still NULL")
                else:
                    no_data += 1
                    print(f"  [ERROR] Game not found after save")
            else:
                errors += 1
                print(f"  [ERROR] save_game returned False")
                
        except Exception as e:
            errors += 1
            print(f"  [ERROR] Exception: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 70)
    print("Summary:")
    print("=" * 70)
    print(f"Successfully updated: {updated}")
    print(f"No data available: {no_data}")
    print(f"Errors: {errors}")
    
    db_manager.close()


if __name__ == "__main__":
    retry_missing_xg()























