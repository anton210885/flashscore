"""Load Italy Serie B games from 2022 to today with all details"""
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import config as cfg
from api.sstats_client import SStatsClient
from database import DatabaseManager
from services.game_loader_service import GameLoaderService
import time

def load_serie_b():
    """Load Italy Serie B games from 2022 to today with all details"""
    print("=" * 70)
    print("Loading Italy Serie B Games (2022-2025) with All Details")
    print("=" * 70)
    print()
    
    # Configuration
    league_id = 136  # Serie B
    years = [2022, 2023, 2024, 2025]
    
    print(f"League: Serie B (ID: {league_id})")
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
    
    # Load games for each year
    total_loaded = 0
    total_errors = 0
    
    for year in years:
        print(f"\n{'='*70}")
        print(f"Loading Serie B {year}")
        print(f"{'='*70}")
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
            print(f"Year {year} Summary:")
            print(f"  Total found: {stats['total_found']}")
            print(f"  Loaded: {stats['loaded']}")
            print(f"  Already existed: {stats['already_exists']}")
            print(f"  Errors: {stats['errors']}")
            print()
            
        except Exception as e:
            print(f"Error loading year {year}: {e}")
            import traceback
            traceback.print_exc()
            total_errors += 1
    
    # Load Glicko data for all Serie B games
    print(f"\n{'='*70}")
    print("Loading Glicko Data for Serie B Games")
    print(f"{'='*70}")
    print()
    
    try:
        conn = db_manager.get_connection()
        serie_b_games = conn.execute("""
            SELECT id FROM games 
            WHERE league_id = ? 
            AND status IN (7, 8, 9, 10)
            ORDER BY id
        """, (league_id,)).fetchall()
        
        total_games = len(serie_b_games)
        print(f"Found {total_games} Serie B games in database")
        print("Loading Glicko data...")
        print()
        
        glicko_loaded = 0
        glicko_errors = 0
        
        for idx, (game_id,) in enumerate(serie_b_games, 1):
            try:
                # Check if Glicko data already exists
                existing = conn.execute(
                    "SELECT game_id FROM game_glicko WHERE game_id = ?",
                    (game_id,)
                ).fetchone()
                
                if existing:
                    if idx % 50 == 0:
                        print(f"  [{idx}/{total_games}] Skipping {game_id} (Glicko already exists)")
                    continue
                
                # Load Glicko data
                time.sleep(1.0)  # Rate limit
                glicko_data = client.get_game_glicko(game_id)
                
                if glicko_data:
                    if db_manager.save_glicko(game_id, glicko_data):
                        glicko_loaded += 1
                        if idx % 10 == 0:
                            print(f"  [{idx}/{total_games}] Loaded Glicko for game {game_id}")
                    else:
                        glicko_errors += 1
                else:
                    glicko_errors += 1
                    
            except Exception as e:
                glicko_errors += 1
                if idx % 10 == 0:
                    print(f"  [{idx}/{total_games}] Error loading Glicko for game {game_id}: {e}")
        
        print()
        print(f"Glicko Summary:")
        print(f"  Loaded: {glicko_loaded}")
        print(f"  Errors: {glicko_errors}")
        print()
        
    except Exception as e:
        print(f"Error loading Glicko data: {e}")
        import traceback
        traceback.print_exc()
    
    # Load Profit data for all Serie B games
    print(f"\n{'='*70}")
    print("Loading Profit Data for Serie B Games")
    print(f"{'='*70}")
    print()
    
    try:
        serie_b_games = conn.execute("""
            SELECT id FROM games 
            WHERE league_id = ? 
            AND status IN (7, 8, 9, 10)
            ORDER BY id
        """, (league_id,)).fetchall()
        
        total_games = len(serie_b_games)
        print(f"Found {total_games} Serie B games in database")
        print("Loading Profit data...")
        print()
        
        profit_loaded = 0
        profit_errors = 0
        
        for idx, (game_id,) in enumerate(serie_b_games, 1):
            try:
                # Check if Profit data already exists
                existing = conn.execute(
                    "SELECT COUNT(*) FROM game_profits WHERE game_id = ?",
                    (game_id,)
                ).fetchone()[0]
                
                if existing > 0:
                    if idx % 50 == 0:
                        print(f"  [{idx}/{total_games}] Skipping {game_id} (Profit already exists)")
                    continue
                
                # Load Profit data
                time.sleep(1.0)  # Rate limit
                profit_data = client.get_game_profits(game_id, bookie_id=1, limit=25)
                
                if profit_data:
                    if db_manager.save_profits(game_id, profit_data):
                        profit_loaded += 1
                        if idx % 10 == 0:
                            print(f"  [{idx}/{total_games}] Loaded Profit for game {game_id}")
                    else:
                        profit_errors += 1
                else:
                    profit_errors += 1
                    
            except Exception as e:
                profit_errors += 1
                if idx % 10 == 0:
                    print(f"  [{idx}/{total_games}] Error loading Profit for game {game_id}: {e}")
        
        print()
        print(f"Profit Summary:")
        print(f"  Loaded: {profit_loaded}")
        print(f"  Errors: {profit_errors}")
        print()
        
    except Exception as e:
        print(f"Error loading Profit data: {e}")
        import traceback
        traceback.print_exc()
    
    # Final summary
    print(f"\n{'='*70}")
    print("Final Summary")
    print(f"{'='*70}")
    print()
    
    final_size = db_manager.get_database_size()
    serie_b_count = conn.execute(
        "SELECT COUNT(*) FROM games WHERE league_id = ?",
        (league_id,)
    ).fetchone()[0]
    
    print(f"Total Serie B games in database: {serie_b_count}")
    print(f"Total games loaded in this session: {total_loaded}")
    print(f"Total errors: {total_errors}")
    print(f"Final database size: {final_size['games']} games, {final_size['file_size_mb']} MB")
    print()
    print("Loading complete!")

if __name__ == "__main__":
    load_serie_b()






















