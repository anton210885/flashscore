"""Test Glicko data saving"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import DatabaseManager
from config import config as cfg
from api.sstats_client import SStatsClient
import sqlite3

def test_glicko_save():
    """Test saving Glicko data"""
    print("=" * 70)
    print("Testing Glicko Data Saving")
    print("=" * 70)
    print()
    
    db_manager = DatabaseManager("data/flashscore.db")
    client = SStatsClient(base_url=cfg.BASE_URL, api_key=getattr(cfg, 'API_KEY', None))
    
    # Test with a known game ID
    test_game_id = 924516
    
    print(f"Testing with Game ID: {test_game_id}")
    print()
    
    # Check if table exists
    conn = db_manager.get_connection()
    try:
        conn.execute("SELECT COUNT(*) FROM game_glicko").fetchone()
        print("[OK] game_glicko table exists")
    except sqlite3.OperationalError as e:
        print(f"[ERROR] Table does not exist: {e}")
        print("Creating table...")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS game_glicko (
                game_id INTEGER PRIMARY KEY,
                home_rating REAL,
                home_rd REAL,
                home_volatility REAL,
                away_rating REAL,
                away_rd REAL,
                away_volatility REAL,
                home_xg REAL,
                away_xg REAL,
                home_win_probability REAL,
                away_win_probability REAL,
                draw_probability REAL,
                updated TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE
            )
        """)
        conn.commit()
        print("[OK] Table created")
    
    # Check current state
    before = conn.execute("""
        SELECT * FROM game_glicko WHERE game_id = ?
    """, (test_game_id,)).fetchone()
    
    print(f"\nBefore save:")
    if before:
        print(f"  Glicko data exists in database")
    else:
        print(f"  No Glicko data in database")
    
    # Fetch from API
    print(f"\nFetching Glicko data from API...")
    try:
        glicko_data = client.get_game_glicko(str(test_game_id))
        print(f"  API Response keys: {list(glicko_data.keys()) if isinstance(glicko_data, dict) else 'Not a dict'}")
        
        # Check structure
        if isinstance(glicko_data, dict):
            if "data" in glicko_data:
                data = glicko_data["data"]
                glicko = data.get("glicko", {}) if isinstance(data, dict) else {}
                print(f"  Found 'data.glicko': {bool(glicko)}")
                if glicko:
                    print(f"  Glicko keys: {list(glicko.keys())[:10]}")
                    print(f"  homeRating: {glicko.get('homeRating')}")
                    print(f"  awayRating: {glicko.get('awayRating')}")
                    print(f"  homeXg: {glicko.get('homeXg')}")
                    print(f"  awayXg: {glicko.get('awayXg')}")
            elif "glicko" in glicko_data:
                glicko = glicko_data["glicko"]
                print(f"  Found 'glicko' at root: {bool(glicko)}")
            else:
                print(f"  No 'glicko' found in response")
                print(f"  Full response: {glicko_data}")
        else:
            print(f"  Response is not a dict: {type(glicko_data)}")
        
        # Try to save
        print(f"\nAttempting to save...")
        result = db_manager.save_glicko(test_game_id, glicko_data)
        print(f"  save_glicko returned: {result}")
        
        # Check after save
        after = conn.execute("""
            SELECT * FROM game_glicko WHERE game_id = ?
        """, (test_game_id,)).fetchone()
        
        print(f"\nAfter save:")
        if after:
            conn.row_factory = sqlite3.Row
            row = conn.execute("""
                SELECT * FROM game_glicko WHERE game_id = ?
            """, (test_game_id,)).fetchone()
            print(f"  [OK] Glicko data saved!")
            print(f"  home_rating: {row['home_rating']}")
            print(f"  away_rating: {row['away_rating']}")
            print(f"  home_xg: {row['home_xg']}")
            print(f"  away_xg: {row['away_xg']}")
        else:
            print(f"  [ERROR] No data saved")
            
    except Exception as e:
        print(f"  [ERROR] Exception: {e}")
        import traceback
        traceback.print_exc()
    
    db_manager.close()


if __name__ == "__main__":
    test_glicko_save()























