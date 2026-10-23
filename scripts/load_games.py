"""CLI script to load finished games into database"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import config as cfg
from api.sstats_client import SStatsClient
from database import DatabaseManager
from services.game_loader_service import GameLoaderService


def main():
    """Main function to load games"""
    if len(sys.argv) < 3:
        print("Usage: python load_games.py <league_id> <year> [load_details]")
        print("Example: python load_games.py 188 2025 true")
        print("  league_id: League ID to load")
        print("  year: Year to load")
        print("  load_details: 'true' to load full details (default), 'false' for basic info only")
        sys.exit(1)
    
    league_id = int(sys.argv[1])
    year = int(sys.argv[2])
    load_details = sys.argv[3].lower() == 'true' if len(sys.argv) > 3 else True
    
    print(f"Loading games for League {league_id}, Year {year}")
    print(f"Load full details: {load_details}")
    print("-" * 50)
    
    # Initialize services
    client = SStatsClient(base_url=cfg.BASE_URL, api_key=getattr(cfg, 'API_KEY', None))
    db_manager = DatabaseManager("data/flashscore.db")
    loader_service = GameLoaderService(client, db_manager, rate_limit_ms=300)
    
    # Progress callback
    def progress_callback(current, total, message):
        if total > 0:
            percentage = (current / total) * 100
            print(f"\r{message} ({current}/{total} - {percentage:.1f}%)", end='', flush=True)
        else:
            print(f"\r{message}", end='', flush=True)
    
    # Load games
    try:
        stats = loader_service.load_games_for_league(
            league_id, year,
            progress_callback=progress_callback,
            load_details=load_details
        )
        
        print("\n" + "=" * 50)
        print("Loading completed!")
        print(f"Total Games Found: {stats['total_found']}")
        print(f"Successfully Loaded: {stats['loaded']}")
        print(f"Already Existed: {stats['already_exists']}")
        print(f"Errors: {stats['errors']}")
        
        # Show database info
        size_info = db_manager.get_database_size()
        print("\nDatabase Statistics:")
        print(f"  Total Games: {size_info['games']}")
        print(f"  Database Size: {size_info['file_size_mb']} MB")
        print(f"  Average per Game: {size_info['avg_size_per_game_mb']} MB")
        
    except KeyboardInterrupt:
        print("\n\nLoading interrupted by user")
    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db_manager.close()


if __name__ == "__main__":
    main()























