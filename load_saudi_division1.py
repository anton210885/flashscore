"""Script to load Saudi Arabia Division 1 games from 2022-2025 with xG data"""
import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from config import config as cfg
from api.sstats_client import SStatsClient
from database import DatabaseManager
from services.game_loader_service import GameLoaderService


def main():
    """Load Saudi Arabia Division 1 2022, 2023, 2024, 2025 games with xG data"""
    print("=" * 60)
    print("Loading Saudi Arabia Division 1 Games (2022, 2023, 2024, 2025) with xG Data")
    print("=" * 60)
    print()
    
    # Configuration
    league_id = 308  # Saudi Arabia Division 1
    years = [2022, 2023, 2024, 2025]
    load_details = True  # Load full details including xG
    
    print(f"League: Saudi Arabia Division 1 (ID: {league_id})")
    print(f"Years: {', '.join(map(str, years))}")
    print(f"Load full details (xG): {load_details}")
    print()
    
    # Initialize services
    print("Initializing services...")
    client = SStatsClient(base_url=cfg.BASE_URL, api_key=getattr(cfg, 'API_KEY', None))
    
    # Initialize database (will create if doesn't exist)
    print("Creating/initializing database...")
    db_manager = DatabaseManager("data/flashscore.db")
    print(f"Database location: {db_manager.db_path.absolute()}")
    
    # Check current database size
    size_info = db_manager.get_database_size()
    print(f"Current database: {size_info['games']} games, {size_info['file_size_mb']} MB")
    print()
    
    # Initialize loader service
    loader_service = GameLoaderService(client, db_manager, rate_limit_ms=1000)
    print("Loader service initialized (1000ms rate limit)")
    print()
    
    # Progress callback
    def progress_callback(current, total, message):
        if total > 0:
            percentage = (current / total) * 100
            print(f"\r{message} ({current}/{total} - {percentage:.1f}%)", end='', flush=True)
        else:
            print(f"\r{message}", end='', flush=True)
    
    # Load games for each year
    overall_stats = {
        "total_loaded": 0,
        "total_skipped": 0,
        "total_errors": 0,
        "total_already_exists": 0,
        "year_stats": {}
    }
    
    print("Starting to load games...")
    print("-" * 60)
    
    try:
        for year in years:
            print(f"\n{'=' * 60}")
            print(f"Loading Year {year}...")
            print(f"{'=' * 60}")
            
            stats = loader_service.load_games_for_league(
                league_id, year,
                progress_callback=progress_callback,
                load_details=load_details
            )
            
            overall_stats["total_loaded"] += stats['loaded']
            overall_stats["total_skipped"] += stats['skipped']
            overall_stats["total_errors"] += stats['errors']
            overall_stats["total_already_exists"] += stats['already_exists']
            overall_stats["year_stats"][year] = stats
            
            print(f"\nYear {year} Results:")
            print(f"  Total Games Found: {stats['total_found']}")
            print(f"  Successfully Loaded: {stats['loaded']}")
            print(f"  Already Existed: {stats['already_exists']}")
            print(f"  Errors: {stats['errors']}")
            print()
        
        print("\n" + "=" * 60)
        print("All Years Loading Completed!")
        print("=" * 60)
        print()
        print("Overall Results:")
        print(f"  Total Games Loaded: {overall_stats['total_loaded']}")
        print(f"  Total Already Existed: {overall_stats['total_already_exists']}")
        print(f"  Total Errors: {overall_stats['total_errors']}")
        print()
        
        # Show updated database info
        size_info = db_manager.get_database_size()
        print("Database Statistics:")
        print(f"  Total Games: {size_info['games']}")
        print(f"  Games with Statistics: {size_info['statistics']}")
        print(f"  Total Events: {size_info['events']}")
        print(f"  Database Size: {size_info['file_size_mb']} MB")
        print(f"  Average Size per Game: {size_info['avg_size_per_game_mb']} MB")
        print()
        
        # Verify games with xG data for each year
        conn = db_manager.get_connection()
        conn.row_factory = lambda cursor, row: row[0]
        print("Games with xG data by year:")
        for year in years:
            games_with_xg = conn.execute("""
                SELECT COUNT(*) FROM games 
                WHERE league_id = ? AND season_year = ? 
                AND calculated_xg_home IS NOT NULL 
                AND calculated_xg_away IS NOT NULL
            """, (league_id, year)).fetchone()
            print(f"  {year}: {games_with_xg} games")
        print()
        print("=" * 60)
        print("Done! Database is ready.")
        print("=" * 60)
        
    except KeyboardInterrupt:
        print("\n\nLoading interrupted by user")
        print("Partial data may have been saved.")
    except Exception as e:
        print(f"\n\nError occurred: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db_manager.close()
        print("\nDatabase connection closed.")


if __name__ == "__main__":
    main()















