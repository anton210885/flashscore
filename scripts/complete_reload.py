"""Complete reload of all A-League games with full details"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import DatabaseManager
from config import config as cfg
from api.sstats_client import SStatsClient
from services.game_loader_service import GameLoaderService
import sqlite3


def complete_reload():
    """Complete reload - delete existing and reload all with full details"""
    print("=" * 70)
    print("Complete Reload - A-League 2022-2025")
    print("=" * 70)
    print()
    
    league_id = 188
    years = [2022, 2023, 2024, 2025]
    
    # Initialize
    client = SStatsClient(base_url=cfg.BASE_URL, api_key=getattr(cfg, 'API_KEY', None))
    db_manager = DatabaseManager("data/flashscore.db")
    loader_service = GameLoaderService(client, db_manager, rate_limit_ms=1000)
    
    # Check current state
    conn = db_manager.get_connection()
    conn.row_factory = sqlite3.Row
    
    current_count = conn.execute("""
        SELECT COUNT(*) FROM games WHERE league_id = ?
    """, (league_id,)).fetchone()[0]
    
    print(f"Current games in database for League {league_id}: {current_count}")
    print()
    
    # Check what API says
    print("Checking API for available games...")
    api_totals = {}
    for year in years:
        finished = loader_service.fetch_finished_games_list(league_id, year)
        api_totals[year] = len(finished)
        print(f"  Year {year}: {len(finished)} games available in API")
    
    total_expected = sum(api_totals.values())
    print(f"\nTotal expected: {total_expected} games")
    print(f"Current in DB: {current_count} games")
    print(f"Missing: {total_expected - current_count} games")
    print()
    
    # Progress callback
    def progress_callback(current, total, message):
        if total > 0:
            percentage = (current / total) * 100
            print(f"\r{message} ({current}/{total} - {percentage:.1f}%)", end='', flush=True)
        else:
            print(f"\r{message}", end='', flush=True)
    
    print("\n" + "=" * 70)
    print("Reloading all games with FULL DETAILS (including xG)...")
    print("=" * 70)
    print("Note: Existing games will be updated if they're missing xG data")
    print()
    
    # Load each year
    total_loaded = 0
    total_updated = 0
    total_errors = 0
    
    for year in years:
        print(f"\n{'=' * 70}")
        print(f"Year {year} ({api_totals[year]} games expected)")
        print(f"{'=' * 70}")
        
        try:
            stats = loader_service.load_games_for_league(
                league_id, year,
                progress_callback=progress_callback,
                load_details=True  # CRITICAL: Must be True
            )
            
            print(f"\nResults:")
            print(f"  Found: {stats['total_found']}")
            print(f"  Loaded (new): {stats['loaded']}")
            print(f"  Updated (had no xG): {stats['already_exists']}")
            print(f"  Errors: {stats['errors']}")
            
            total_loaded += stats['loaded']
            total_updated += stats['already_exists']
            total_errors += stats['errors']
            
        except Exception as e:
            print(f"\nERROR: {e}")
            import traceback
            traceback.print_exc()
            total_errors += 1
    
    # Final verification
    print("\n" + "=" * 70)
    print("Final Verification:")
    print("=" * 70)
    
    # Count by year
    print("\nGames by Year in Database:")
    for year in years:
        count = conn.execute("""
            SELECT COUNT(*) FROM games 
            WHERE league_id = ? AND season_year = ?
        """, (league_id, year)).fetchone()[0]
        expected = api_totals[year]
        status = "OK" if count == expected else f"MISSING {expected - count}"
        print(f"  {year}: {count}/{expected} - {status}")
    
    # xG statistics
    with_xg = conn.execute("""
        SELECT COUNT(*) FROM games 
        WHERE league_id = ? 
        AND calculated_xg_home IS NOT NULL 
        AND calculated_xg_away IS NOT NULL
    """, (league_id,)).fetchone()[0]
    
    stats_count = conn.execute("""
        SELECT COUNT(*) FROM game_statistics 
        WHERE game_id IN (SELECT id FROM games WHERE league_id = ?)
    """, (league_id,)).fetchone()[0]
    
    total_final = conn.execute("""
        SELECT COUNT(*) FROM games WHERE league_id = ?
    """, (league_id,)).fetchone()[0]
    
    print(f"\nFinal Statistics:")
    print(f"  Total Games: {total_final}")
    print(f"  Games with xG: {with_xg}")
    print(f"  Games with Statistics Table: {stats_count}")
    print(f"  New Games Loaded: {total_loaded}")
    print(f"  Games Updated: {total_updated}")
    print(f"  Errors: {total_errors}")
    
    if with_xg < total_final:
        missing_xg = total_final - with_xg
        print(f"\n  WARNING: {missing_xg} games still missing xG data!")
        print(f"  These games may not have xG data available in the API.")
    
    db_manager.close()
    print("\nDone!")


if __name__ == "__main__":
    complete_reload()























