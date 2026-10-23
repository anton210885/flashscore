"""Load British League games (Premier League, Championship, League One, League Two) from 2022 to today with all details"""
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import config as cfg
from api.sstats_client import SStatsClient
from database import DatabaseManager
from services.game_loader_service import GameLoaderService
import time

def load_british_leagues():
    """Load British League games from 2022 to today with all details"""
    print("=" * 70)
    print("Loading British Leagues Games (2022-2025) with All Details")
    print("=" * 70)
    print()
    
    # Configuration
    leagues = [
        {"id": 39, "name": "Premier League"},
        {"id": 40, "name": "Championship"},
        {"id": 41, "name": "League One"},
        {"id": 42, "name": "League Two"}
    ]
    years = [2022, 2023, 2024, 2025]
    
    league_names = [f"{l['name']} (ID: {l['id']})" for l in leagues]
    print(f"Leagues: {', '.join(league_names)}")
    print(f"Years: {', '.join(map(str, years))}")
    print(f"Load full details: Yes (xG, Glicko, Profits, etc.)")
    print()
    
    # Initialize services
    print("Initializing services...")
    client = SStatsClient(base_url=cfg.BASE_URL, api_key=getattr(cfg, 'API_KEY', None))
    
    # Initialize database
    print("Connecting to database...")
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
            print(f"[{current}/{total} ({percentage:.1f}%)] {message}")
        else:
            print(f"[?/?] {message}")
    
    # Load games for each league and year
    total_loaded = 0
    total_errors = 0
    
    for league in leagues:
        league_id = league["id"]
        league_name = league["name"]
        
        print(f"\n{'='*70}")
        print(f"Loading {league_name} (ID: {league_id})")
        print(f"{'='*70}")
        print()
        
        for year in years:
            print(f"\n{'-'*70}")
            print(f"Loading {league_name} {year}")
            print(f"{'-'*70}")
            print()
            
            try:
                stats = loader_service.load_games_for_league(
                    league_id, 
                    year,
                    progress_callback=progress_callback,
                    load_details=True  # Load full details including xG
                )
                
                total_loaded += stats["loaded"]
                total_errors += stats["errors"]
                
                print()
                print(f"{league_name} {year} Summary:")
                print(f"  Total found: {stats['total_found']}")
                print(f"  Loaded: {stats['loaded']}")
                print(f"  Already existed: {stats['already_exists']}")
                print(f"  Errors: {stats['errors']}")
                print()
                
            except Exception as e:
                print(f"Error loading {league_name} {year}: {e}")
                import traceback
                traceback.print_exc()
                total_errors += 1
                print()
            
            # Rate limiting between years
            if year < years[-1]:  # Don't wait after last year
                time.sleep(2)
        
        # Rate limiting between leagues
        if league != leagues[-1]:  # Don't wait after last league
            time.sleep(3)
    
    # Final summary
    print()
    print("=" * 70)
    print("Loading Complete!")
    print("=" * 70)
    print(f"Total games loaded: {total_loaded}")
    print(f"Total errors: {total_errors}")
    print()
    
    # Check final database size
    size_info = db_manager.get_database_size()
    print(f"Final database: {size_info['games']} games, {size_info['file_size_mb']} MB")
    print()

if __name__ == "__main__":
    load_british_leagues()


















