"""Setup AutoLoader to monitor A-League 2025"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import DatabaseManager
from config import config as cfg
from api.sstats_client import SStatsClient
from services.auto_loader_service import AutoLoaderService

def setup_auto_loader():
    """Setup AutoLoader to monitor A-League 2025"""
    print("=" * 70)
    print("Setting up AutoLoader for A-League 2025")
    print("=" * 70)
    print()
    
    # Initialize
    client = SStatsClient(base_url=cfg.BASE_URL, api_key=getattr(cfg, 'API_KEY', None))
    db_manager = DatabaseManager("data/flashscore.db")
    auto_loader = AutoLoaderService(client, db_manager, rate_limit_ms=1000)
    
    # Configure to monitor A-League (188) for 2025
    league_id = 188
    years = [2025]
    
    print(f"Adding League {league_id} (A-League) for years {years}...")
    auto_loader.add_league_to_monitor(league_id, years)
    
    print(f"Configured leagues: {auto_loader.leagues_to_monitor}")
    print()
    
    # Check if running
    if auto_loader.is_running():
        print("AutoLoader is already running.")
    else:
        print("AutoLoader is not running.")
        print("To start it, use the GUI or run:")
        print("  auto_loader.start(check_interval_seconds=300)")
        print()
        print("Or start it now? (y/n): ", end="")
        response = input().strip().lower()
        if response == 'y':
            auto_loader.start(check_interval_seconds=300)
            print("AutoLoader started! Checking every 5 minutes.")
        else:
            print("AutoLoader configured but not started.")

if __name__ == "__main__":
    setup_auto_loader()























