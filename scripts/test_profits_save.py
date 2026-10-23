"""Test profit data saving"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import DatabaseManager
from config import config as cfg
from api.sstats_client import SStatsClient
import sqlite3

def test_profits_save():
    """Test saving profit data"""
    print("=" * 70)
    print("Testing Profit Data Saving")
    print("=" * 70)
    print()
    
    db_manager = DatabaseManager("data/flashscore.db")
    client = SStatsClient(base_url=cfg.BASE_URL, api_key=getattr(cfg, 'API_KEY', None))
    
    # Test with a known game ID
    test_game_id = 1469600
    
    print(f"Testing with Game ID: {test_game_id}")
    print()
    
    # Check if table exists
    conn = db_manager.get_connection()
    try:
        conn.execute("SELECT COUNT(*) FROM game_profits").fetchone()
        print("[OK] game_profits table exists")
    except sqlite3.OperationalError as e:
        print(f"[ERROR] Table does not exist: {e}")
        return
    
    # Check current state
    before = conn.execute("""
        SELECT COUNT(*) FROM game_profits WHERE game_id = ?
    """, (test_game_id,)).fetchone()[0]
    
    print(f"\nBefore save:")
    print(f"  Profit records: {before}")
    
    # Fetch from API
    print(f"\nFetching profit data from API...")
    try:
        profits_data = client.get_game_profits(
            test_game_id,
            this_league=False,
            home_away=False,
            same_games=False,
            bookie_id=1,
            limit=25
        )
        print(f"  API Response keys: {list(profits_data.keys()) if isinstance(profits_data, dict) else 'Not a dict'}")
        
        # Check structure
        if isinstance(profits_data, dict):
            if "data" in profits_data:
                data = profits_data["data"]
                print(f"  Found 'data' key")
                print(f"  Data keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
                if isinstance(data, dict):
                    for key in ["home", "away", "homeFirstHalf", "awayFirstHalf"]:
                        if key in data:
                            markets = data[key]
                            if isinstance(markets, list):
                                print(f"  {key}: {len(markets)} markets")
                            else:
                                print(f"  {key}: Not a list")
        
        # Try to save
        print(f"\nAttempting to save...")
        result = db_manager.save_profits(test_game_id, profits_data)
        print(f"  save_profits returned: {result}")
        
        # Check after save
        after = conn.execute("""
            SELECT COUNT(*) FROM game_profits WHERE game_id = ?
        """, (test_game_id,)).fetchone()[0]
        
        print(f"\nAfter save:")
        print(f"  Profit records: {after}")
        
        if after > before:
            print(f"  [OK] Profit data saved successfully!")
            
            # Show sample data
            conn.row_factory = sqlite3.Row
            sample = conn.execute("""
                SELECT team_type, market, outcome_name, profit, games_count, win_count
                FROM game_profits 
                WHERE game_id = ? 
                LIMIT 5
            """, (test_game_id,)).fetchall()
            
            print(f"\n  Sample records:")
            for row in sample:
                print(f"    {row['team_type']} - {row['market']} - {row['outcome_name']}: profit={row['profit']}, games={row['games_count']}, wins={row['win_count']}")
        else:
            print(f"  [ERROR] No data saved")
            
    except Exception as e:
        print(f"  [ERROR] Exception: {e}")
        import traceback
        traceback.print_exc()
    
    db_manager.close()


if __name__ == "__main__":
    test_profits_save()























