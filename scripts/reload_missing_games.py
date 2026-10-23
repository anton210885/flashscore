"""Script to reload missing games for A-League"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import DatabaseManager
from config import config as cfg
from api.sstats_client import SStatsClient
from services.game_loader_service import GameLoaderService


def reload_missing():
    """Reload missing games for A-League"""
    print("=" * 70)
    print("Reloading Missing Games for A-League")
    print("=" * 70)
    print()
    
    league_id = 188  # A-League
    years = [2023, 2024, 2025]  # Years with missing games
    
    # Initialize
    client = SStatsClient(base_url=cfg.BASE_URL, api_key=getattr(cfg, 'API_KEY', None))
    db_manager = DatabaseManager("data/flashscore.db")
    loader_service = GameLoaderService(client, db_manager, rate_limit_ms=1000)
    
    # Progress callback
    def progress_callback(current, total, message):
        if total > 0:
            percentage = (current / total) * 100
            print(f"\r{message} ({current}/{total} - {percentage:.1f}%)", end='', flush=True)
        else:
            print(f"\r{message}", end='', flush=True)
    
    # Load each year
    for year in years:
        print(f"\n{'=' * 70}")
        print(f"Loading League {league_id}, Year {year}...")
        print(f"{'=' * 70}")
        
        try:
            stats = loader_service.load_games_for_league(
                league_id, year,
                progress_callback=progress_callback,
                load_details=True
            )
            
            print(f"\nYear {year} Results:")
            print(f"  Total Games Found: {stats['total_found']}")
            print(f"  Successfully Loaded: {stats['loaded']}")
            print(f"  Already Existed: {stats['already_exists']}")
            print(f"  Errors: {stats['errors']}")
            
        except Exception as e:
            print(f"\nError loading year {year}: {e}")
            import traceback
            traceback.print_exc()
    
    # Final statistics
    print("\n" + "=" * 70)
    print("Final Database Statistics:")
    print("=" * 70)
    
    size_info = db_manager.get_database_size()
    print(f"Total Games: {size_info['games']}")
    print(f"Database Size: {size_info['file_size_mb']} MB")
    
    db_manager.close()
    print("\nDone!")


if __name__ == "__main__":
    reload_missing()























