"""Test saving xG data to database"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import DatabaseManager
from config import config as cfg
from api.sstats_client import SStatsClient

def test_save_xg():
    """Test saving xG data"""
    client = SStatsClient(base_url=cfg.BASE_URL, api_key=getattr(cfg, 'API_KEY', None))
    db_manager = DatabaseManager("data/flashscore.db")
    
    # Test with game ID 924516
    game_id = 924516
    print(f"Testing save xG for Game ID: {game_id}")
    print("=" * 70)
    
    # Check current state
    conn = db_manager.get_connection()
    import sqlite3
    conn.row_factory = sqlite3.Row
    
    before = conn.execute("""
        SELECT calculated_xg_home, calculated_xg_away 
        FROM games WHERE id = ?
    """, (game_id,)).fetchone()
    
    print(f"\nBefore update:")
    print(f"  calculated_xg_home: {before['calculated_xg_home'] if before else 'Game not found'}")
    print(f"  calculated_xg_away: {before['calculated_xg_away'] if before else 'N/A'}")
    
    # Fetch from API
    print(f"\nFetching from API...")
    game_data = client.get_game(game_id)
    
    # Save to database
    print(f"Saving to database...")
    result = db_manager.save_game(game_data)
    print(f"Save result: {result}")
    
    # Check after
    after = conn.execute("""
        SELECT calculated_xg_home, calculated_xg_away 
        FROM games WHERE id = ?
    """, (game_id,)).fetchone()
    
    print(f"\nAfter update:")
    print(f"  calculated_xg_home: {after['calculated_xg_home'] if after else 'Game not found'}")
    print(f"  calculated_xg_away: {after['calculated_xg_away'] if after else 'N/A'}")
    
    if after and after['calculated_xg_home'] is not None:
        print("\n✓ SUCCESS: xG data saved correctly!")
    else:
        print("\n✗ FAILED: xG data not saved")
    
    db_manager.close()

if __name__ == "__main__":
    test_save_xg()























