"""Check why specific games don't have xG data"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import DatabaseManager
from config import config as cfg
from api.sstats_client import SStatsClient
import sqlite3

def check_missing_xg():
    """Check why specific games don't have xG data"""
    game_ids = [1123552, 1280751, 1280773, 1280789, 1280790, 1280823, 1280824, 
                1374036, 1375034, 1375203, 1469570, 1469571, 1469572, 1469587, 
                1469588, 1469600]
    
    print("=" * 70)
    print("Checking Missing xG Data for Specific Games")
    print("=" * 70)
    print()
    
    db_manager = DatabaseManager("data/flashscore.db")
    client = SStatsClient(base_url=cfg.BASE_URL, api_key=getattr(cfg, 'API_KEY', None))
    
    conn = db_manager.get_connection()
    conn.row_factory = sqlite3.Row
    
    for game_id in game_ids:
        print(f"\n{'=' * 70}")
        print(f"Game ID: {game_id}")
        print(f"{'=' * 70}")
        
        # Check if game exists in database
        game_row = conn.execute("""
            SELECT id, home_team_name, away_team_name, date, 
                   calculated_xg_home, calculated_xg_away
            FROM games WHERE id = ?
        """, (game_id,)).fetchone()
        
        if not game_row:
            print(f"  [ERROR] Game NOT FOUND in database")
            continue
        
        print(f"  [OK] Game found in database:")
        print(f"    {game_row['home_team_name']} vs {game_row['away_team_name']}")
        print(f"    Date: {game_row['date']}")
        print(f"    xG Home: {game_row['calculated_xg_home']}")
        print(f"    xG Away: {game_row['calculated_xg_away']}")
        
        # Check API response
        try:
            print(f"\n  Checking API response...")
            game_data = client.get_game(game_id)
            
            # Extract statistics
            if isinstance(game_data, dict):
                if "data" in game_data and isinstance(game_data["data"], dict):
                    data = game_data["data"]
                    stats = data.get("statistics", {})
                    game = data.get("game", {})
                elif "statistics" in game_data:
                    stats = game_data["statistics"]
                    game = game_data.get("game", {})
                else:
                    stats = {}
                    game = game_data
            else:
                stats = {}
                game = {}
            
            if stats:
                calculated_xg_home = stats.get("calculatedXgHome")
                calculated_xg_away = stats.get("calculatedXgAway")
                
                print(f"    Statistics found in API:")
                print(f"      calculatedXgHome: {calculated_xg_home}")
                print(f"      calculatedXgAway: {calculated_xg_away}")
                
                if calculated_xg_home is None and calculated_xg_away is None:
                    print(f"    [WARNING] API returns NULL for both xG values")
                else:
                    print(f"    [OK] API has xG data - should be saved!")
                    
                    # Try to save
                    print(f"    Attempting to save...")
                    if db_manager.save_game(game_data):
                        # Check if saved
                        check = conn.execute("""
                            SELECT calculated_xg_home, calculated_xg_away 
                            FROM games WHERE id = ?
                        """, (game_id,)).fetchone()
                        if check and (check['calculated_xg_home'] is not None or check['calculated_xg_away'] is not None):
                            print(f"    [OK] Successfully saved xG data!")
                        else:
                            print(f"    [ERROR] Save returned True but xG still NULL")
                    else:
                        print(f"    [ERROR] Save failed")
            else:
                print(f"    [ERROR] No statistics in API response")
                print(f"    Response structure: {list(game_data.keys()) if isinstance(game_data, dict) else 'Not a dict'}")
                
        except Exception as e:
            print(f"    [ERROR] Error fetching from API: {e}")
            import traceback
            traceback.print_exc()
    
    db_manager.close()
    print("\n" + "=" * 70)
    print("Check Complete!")
    print("=" * 70)


if __name__ == "__main__":
    check_missing_xg()

