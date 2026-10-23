"""Script to check database and compare with API to see if games are missing"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import DatabaseManager
from config import config as cfg
from api.sstats_client import SStatsClient
from services.game_loader_service import GameLoaderService
import sqlite3


def check_database():
    """Check database contents and compare with API"""
    print("=" * 70)
    print("Database Check - Comparing with API")
    print("=" * 70)
    print()
    
    db_path = "data/flashscore.db"
    
    if not Path(db_path).exists():
        print(f"ERROR: Database not found at {db_path}")
        return
    
    # Initialize
    db_manager = DatabaseManager(db_path)
    client = SStatsClient(base_url=cfg.BASE_URL, api_key=getattr(cfg, 'API_KEY', None))
    loader_service = GameLoaderService(client, db_manager, rate_limit_ms=1000)
    
    # Get database statistics
    print("DATABASE STATISTICS:")
    print("-" * 70)
    size_info = db_manager.get_database_size()
    print(f"Database Size: {size_info['file_size_mb']} MB")
    print(f"Total Games in DB: {size_info['games']}")
    print(f"Games with Statistics: {size_info['statistics']}")
    print()
    
    # Get games by league and year
    conn = db_manager.get_connection()
    conn.row_factory = sqlite3.Row
    
    print("GAMES BY LEAGUE AND YEAR (in database):")
    print("-" * 70)
    print(f"{'League ID':<12} {'League Name':<30} {'Year':<8} {'Games in DB':<15}")
    print("-" * 70)
    
    db_rows = conn.execute("""
        SELECT league_id, league_name, season_year, COUNT(*) as count
        FROM games
        GROUP BY league_id, season_year
        ORDER BY league_id, season_year DESC
    """).fetchall()
    
    leagues_to_check = []
    for row in db_rows:
        print(f"{row['league_id']:<12} {row['league_name']:<30} {row['season_year']:<8} {row['count']:<15}")
        leagues_to_check.append((row['league_id'], row['season_year']))
    
    if not db_rows:
        print("No games found in database!")
        print("\nChecking A-League 2022-2025 as example...")
        leagues_to_check = [(188, 2022), (188, 2023), (188, 2024), (188, 2025)]
    
    print()
    print("=" * 70)
    print("COMPARING WITH API:")
    print("=" * 70)
    print()
    
    # Compare with API
    for league_id, year in leagues_to_check:
        print(f"Checking League {league_id}, Year {year}...")
        
        # Get count from database
        db_count = conn.execute("""
            SELECT COUNT(*) FROM games 
            WHERE league_id = ? AND season_year = ?
        """, (league_id, year)).fetchone()[0]
        
        # Get count from API
        try:
            finished_games = loader_service.fetch_finished_games_list(league_id, year)
            api_count = len(finished_games)
            
            difference = api_count - db_count
            status = "OK" if difference == 0 else f"MISSING {difference}"
            
            print(f"  Database: {db_count} games")
            print(f"  API:      {api_count} games")
            print(f"  Status:   {status}")
            
            if difference > 0:
                print(f"  WARNING: {difference} games missing from database!")
                print(f"    You may want to reload this league/year.")
            
        except Exception as e:
            print(f"  ERROR checking API: {e}")
        
        print()
    
    # Check for specific league (A-League)
    print("=" * 70)
    print("DETAILED CHECK: A-League (188)")
    print("=" * 70)
    
    for year in [2022, 2023, 2024, 2025]:
        db_count = conn.execute("""
            SELECT COUNT(*) FROM games 
            WHERE league_id = 188 AND season_year = ?
        """, (year,)).fetchone()[0]
        
        try:
            finished_games = loader_service.fetch_finished_games_list(188, year)
            api_count = len(finished_games)
            
            print(f"Year {year}:")
            print(f"  Database: {db_count} games")
            print(f"  API:      {api_count} games")
            
            if api_count > db_count:
                missing = api_count - db_count
                print(f"  MISSING: {missing} games")
                print(f"  Recommendation: Reload League 188, Year {year}")
            elif db_count == 0:
                print(f"  NO GAMES in database for this year!")
            else:
                print(f"  All games loaded")
            
        except Exception as e:
            print(f"  ERROR: {e}")
        
        print()
    
    # Show sample of games in database
    print("=" * 70)
    print("SAMPLE GAMES (last 10):")
    print("=" * 70)
    
    sample = conn.execute("""
        SELECT id, date, home_team_name, away_team_name, 
               home_ft_result, away_ft_result, league_name, season_year
        FROM games
        ORDER BY date DESC
        LIMIT 10
    """).fetchall()
    
    if sample:
        print(f"{'Date':<12} {'Home':<20} {'Away':<20} {'Score':<10} {'League':<20} {'Year':<6}")
        print("-" * 100)
        for row in sample:
            date = row['date'][:10] if row['date'] else 'N/A'
            score = f"{row['home_ft_result']}-{row['away_ft_result']}"
            print(f"{date:<12} {row['home_team_name'][:19]:<20} {row['away_team_name'][:19]:<20} "
                  f"{score:<10} {row['league_name'][:19]:<20} {row['season_year']:<6}")
    else:
        print("No games in database!")
    
    print()
    print("=" * 70)
    print("SUMMARY:")
    print("=" * 70)
    print(f"Total games in database: {size_info['games']}")
    print(f"Database file: {Path(db_path).absolute()}")
    print()
    print("If games are missing, you can:")
    print("1. Use the Database Tab in the GUI to reload specific leagues")
    print("2. Run: python load_australia_2022.py (for A-League)")
    print("3. Use the Auto-Loader to automatically load new games")
    
    db_manager.close()


if __name__ == "__main__":
    check_database()

