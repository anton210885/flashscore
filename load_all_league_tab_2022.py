"""Script to load all games from leagues shown in League Tab for year 2022 with xG data"""
import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from config import config as cfg
from api.sstats_client import SStatsClient
from database import DatabaseManager
from services.game_loader_service import GameLoaderService


def get_all_league_ids():
    """Get all league IDs that should be loaded - from database and target list"""
    db_manager = DatabaseManager("data/flashscore.db")
    conn = db_manager.get_connection()
    
    # Target leagues that should always be shown (even if no games yet)
    target_league_ids = [145, 144, 39, 40, 41, 42, 135, 136, 307, 308, 303, 301, 188]
    
    # Get ALL distinct leagues from database
    leagues_data = conn.execute("""
        SELECT DISTINCT league_id
        FROM games
        WHERE league_id IS NOT NULL
    """).fetchall()
    
    # Combine all league IDs
    all_league_ids = set(target_league_ids)
    for row in leagues_data:
        all_league_ids.add(row[0])
    
    # Convert to sorted list
    league_ids = sorted(list(all_league_ids))
    
    # Get league names for display
    league_info = {}
    for league_id in league_ids:
        row = conn.execute("""
            SELECT league_name, country_name 
            FROM games 
            WHERE league_id = ? 
            LIMIT 1
        """, (league_id,)).fetchone()
        if row:
            league_info[league_id] = {
                "name": row[0] or f"League {league_id}",
                "country": row[1] or "Unknown"
            }
        else:
            # Use default names for target leagues
            league_names_map = {
                145: "Challenger Pro League",
                144: "Jupiler Pro League",
                39: "Premier League",
                40: "Championship",
                41: "League One",
                42: "League Two",
                135: "Serie A",
                136: "Serie B",
                307: "Saudi Arabia Division 1",
                308: "Saudi Arabia Division 1",
                303: "UAE Division 1",
                301: "UAE Pro League",
                188: "A-League"
            }
            country_map = {
                145: "Belgium", 144: "Belgium",
                39: "Great Britain", 40: "Great Britain", 41: "Great Britain", 42: "Great Britain",
                135: "Italy", 136: "Italy",
                307: "Saudi Arabia", 308: "Saudi Arabia",
                303: "United Arab Emirates", 301: "United Arab Emirates",
                188: "Australia"
            }
            league_info[league_id] = {
                "name": league_names_map.get(league_id, f"League {league_id}"),
                "country": country_map.get(league_id, "Unknown")
            }
    
    return league_ids, league_info


def main():
    """Load all games from leagues shown in League Tab for year 2022 with xG data"""
    print("=" * 70)
    print("Loading All League Tab Leagues - Year 2022 with xG Data")
    print("=" * 70)
    print()
    
    # Get all league IDs
    print("Getting list of leagues from database...")
    league_ids, league_info = get_all_league_ids()
    print(f"Found {len(league_ids)} leagues to load")
    print()
    
    # Show leagues that will be loaded
    print("Leagues to load:")
    for league_id in league_ids:
        info = league_info[league_id]
        print(f"  {league_id}: {info['name']} ({info['country']})")
    print()
    
    year = 2022
    load_details = True  # Load full details including xG
    
    print(f"Year: {year}")
    print(f"Load full details (xG): {load_details}")
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
            print(f"\r{message} ({current}/{total} - {percentage:.1f}%)", end='', flush=True)
        else:
            print(f"\r{message}", end='', flush=True)
    
    # Load games for each league
    overall_stats = {
        "total_loaded": 0,
        "total_skipped": 0,
        "total_errors": 0,
        "total_already_exists": 0,
        "league_stats": {}
    }
    
    print("Starting to load games...")
    print("-" * 70)
    
    try:
        for idx, league_id in enumerate(league_ids, 1):
            info = league_info[league_id]
            league_name = info['name']
            country = info['country']
            
            print(f"\n{'=' * 70}")
            print(f"[{idx}/{len(league_ids)}] Loading {league_name} ({country}) - ID: {league_id}")
            print(f"{'=' * 70}")
            
            try:
                stats = loader_service.load_games_for_league(
                    league_id, year,
                    progress_callback=progress_callback,
                    load_details=load_details
                )
                
                overall_stats["total_loaded"] += stats['loaded']
                overall_stats["total_skipped"] += stats['skipped']
                overall_stats["total_errors"] += stats['errors']
                overall_stats["total_already_exists"] += stats['already_exists']
                overall_stats["league_stats"][league_id] = {
                    "name": league_name,
                    "stats": stats
                }
                
                print(f"\n{league_name} ({country}) Results:")
                print(f"  Total Games Found: {stats['total_found']}")
                print(f"  Successfully Loaded: {stats['loaded']}")
                print(f"  Already Existed: {stats['already_exists']}")
                print(f"  Errors: {stats['errors']}")
                print()
                
            except Exception as e:
                print(f"\nError loading {league_name} ({country}): {e}")
                import traceback
                traceback.print_exc()
                overall_stats["total_errors"] += 1
                print()
            
            # Small delay between leagues to avoid rate limiting
            if idx < len(league_ids):
                import time
                time.sleep(1)
        
        print("\n" + "=" * 70)
        print("All Leagues Loading Completed!")
        print("=" * 70)
        print()
        print("Overall Results:")
        print(f"  Total Games Loaded: {overall_stats['total_loaded']}")
        print(f"  Total Already Existed: {overall_stats['total_already_exists']}")
        print(f"  Total Errors: {overall_stats['total_errors']}")
        print()
        
        # Show results by league
        print("Results by League:")
        for league_id, data in sorted(overall_stats["league_stats"].items()):
            stats = data["stats"]
            print(f"  {data['name']} (ID: {league_id}): {stats['loaded']} loaded, {stats['already_exists']} existed, {stats['errors']} errors")
        print()
        
        # Show updated database info
        size_info = db_manager.get_database_size()
        print("Database Statistics:")
        print(f"  Total Games: {size_info['games']}")
        print(f"  Games with Statistics: {size_info['statistics']}")
        print(f"  Total Events: {size_info['events']}")
        print(f"  Database Size: {size_info['file_size_mb']} MB")
        print()
        
        # Verify games with xG data
        conn = db_manager.get_connection()
        games_with_xg = conn.execute("""
            SELECT COUNT(*) FROM games 
            WHERE season_year = 2022
            AND calculated_xg_home IS NOT NULL 
            AND calculated_xg_away IS NOT NULL
        """).fetchone()[0]
        total_2022 = conn.execute("""
            SELECT COUNT(*) FROM games 
            WHERE season_year = 2022
        """).fetchone()[0]
        
        print(f"Year 2022 Statistics:")
        print(f"  Total Games: {total_2022}")
        print(f"  Games with xG data: {games_with_xg}")
        print()
        print("=" * 70)
        print("Done! Database is ready.")
        print("=" * 70)
        
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















