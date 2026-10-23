"""Create the game_odds_pivoted view in existing database"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import DatabaseManager

def create_odds_view():
    """Create the game_odds_pivoted view"""
    print("=" * 70)
    print("Creating game_odds_pivoted view")
    print("=" * 70)
    print()
    
    db_path = "data/flashscore.db"
    db_manager = DatabaseManager(db_path)
    
    # Read the view SQL
    view_file = Path(__file__).parent.parent / "database" / "create_odds_view.sql"
    if not view_file.exists():
        print(f"[ERROR] View file not found: {view_file}")
        return
    
    with open(view_file, 'r', encoding='utf-8') as f:
        view_sql = f.read()
    
    try:
        conn = db_manager.get_connection()
        conn.executescript(view_sql)
        conn.commit()
        print("[SUCCESS] game_odds_pivoted view created successfully!")
        print()
        print("The view transforms game_odds from rows to columns:")
        print("  - odd_home, odd_draw, odd_away, odd_under_15")
        print("  - odd_over_25, odd_under_25")
        print("  - odd_over_35, odd_under_35")
        print("  - odd_over_45, odd_under_45")
        print("  - odd_open_home, odd_open_draw, odd_open_away")
        print("  - odd_open_over_25, odd_open_under_25")
        print()
        print("You can now query odds like:")
        print("  SELECT odd_home, odd_draw, odd_away FROM game_odds_pivoted WHERE game_id = ?")
    except Exception as e:
        print(f"[ERROR] Failed to create view: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    create_odds_view()






















