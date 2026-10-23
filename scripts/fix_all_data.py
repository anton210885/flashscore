"""Complete fix: Reload all missing games and add xG data"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import DatabaseManager
from config import config as cfg
from api.sstats_client import SStatsClient
from services.game_loader_service import GameLoaderService


def fix_all():
    """Fix all issues: reload missing games and add xG data"""
    print("=" * 70)
    print("Complete Data Fix for A-League")
    print("=" * 70)
    print()
    
    league_id = 188  # A-League
    years = [2022, 2023, 2024, 2025]
    
    # Initialize
    client = SStatsClient(base_url=cfg.BASE_URL, api_key=getattr(cfg, 'API_KEY', None))
    db_manager = DatabaseManager("data/flashscore.db")
    loader_service = GameLoaderService(client, db_manager, rate_limit_ms=1000)
    
    print("This will:")
    print("1. Reload all games for 2022-2025 with FULL DETAILS (including xG)")
    print("2. This will take approximately 10-15 minutes")
    print("3. Existing games will be updated with full statistics")
    print()
    
    response = input("Continue? (yes/no): ").strip().lower()
    if response != 'yes':
        print("Cancelled.")
        return
    
    # Progress callback
    def progress_callback(current, total, message):
        if total > 0:
            percentage = (current / total) * 100
            print(f"\r{message} ({current}/{total} - {percentage:.1f}%)", end='', flush=True)
        else:
            print(f"\r{message}", end='', flush=True)
    
    # Load each year with FULL DETAILS
    for year in years:
        print(f"\n{'=' * 70}")
        print(f"Loading League {league_id}, Year {year} with FULL DETAILS...")
        print(f"{'=' * 70}")
        
        try:
            # Force reload by not checking existing_ids
            # We'll reload all to ensure they have full details
            stats = loader_service.load_games_for_league(
                league_id, year,
                progress_callback=progress_callback,
                load_details=True  # CRITICAL: Must be True for xG data
            )
            
            print(f"\nYear {year} Results:")
            print(f"  Total Games Found: {stats['total_found']}")
            print(f"  Successfully Loaded: {stats['loaded']}")
            print(f"  Already Existed (updated): {stats['already_exists']}")
            print(f"  Errors: {stats['errors']}")
            
        except Exception as e:
            print(f"\nError loading year {year}: {e}")
            import traceback
            traceback.print_exc()
    
    # Final check
    print("\n" + "=" * 70)
    print("Final Verification:")
    print("=" * 70)
    
    import sqlite3
    conn = db_manager.get_connection()
    conn.row_factory = sqlite3.Row
    
    # Check xG data
    with_xg = conn.execute("""
        SELECT COUNT(*) FROM games 
        WHERE calculated_xg_home IS NOT NULL AND calculated_xg_away IS NOT NULL
    """).fetchone()[0]
    
    stats_count = conn.execute("SELECT COUNT(*) FROM game_statistics").fetchone()[0]
    total_games = conn.execute("SELECT COUNT(*) FROM games").fetchone()[0]
    
    print(f"Total Games: {total_games}")
    print(f"Games with xG data: {with_xg}")
    print(f"Games with statistics: {stats_count}")
    
    # Games by year
    print("\nGames by Year:")
    for year in years:
        count = conn.execute("""
            SELECT COUNT(*) FROM games 
            WHERE league_id = ? AND season_year = ?
        """, (league_id, year)).fetchone()[0]
        print(f"  {year}: {count} games")
    
    db_manager.close()
    print("\nDone!")


if __name__ == "__main__":
    fix_all()























