"""Debug script to check database and xG data issues"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import DatabaseManager
from config import config as cfg
from api.sstats_client import SStatsClient
import sqlite3
import json


def debug_database():
    """Debug database issues"""
    print("=" * 70)
    print("Database Debug - Checking xG Data and Game Count")
    print("=" * 70)
    print()
    
    db_path = "data/flashscore.db"
    db_manager = DatabaseManager(db_path)
    conn = db_manager.get_connection()
    conn.row_factory = sqlite3.Row
    
    # Total games
    total = conn.execute("SELECT COUNT(*) FROM games").fetchone()[0]
    print(f"Total Games in Database: {total}")
    print()
    
    # Games by league and year
    print("Games by League and Year:")
    print("-" * 70)
    rows = conn.execute("""
        SELECT league_id, league_name, season_year, COUNT(*) as count
        FROM games
        GROUP BY league_id, season_year
        ORDER BY league_id, season_year DESC
    """).fetchall()
    
    for row in rows:
        print(f"League {row['league_id']} ({row['league_name']}), Year {row['season_year']}: {row['count']} games")
    print()
    
    # Check xG data
    print("=" * 70)
    print("xG Data Analysis:")
    print("=" * 70)
    
    # Games with xG
    with_xg = conn.execute("""
        SELECT COUNT(*) FROM games 
        WHERE calculated_xg_home IS NOT NULL AND calculated_xg_away IS NOT NULL
    """).fetchone()[0]
    
    # Games without xG
    without_xg = conn.execute("""
        SELECT COUNT(*) FROM games 
        WHERE calculated_xg_home IS NULL OR calculated_xg_away IS NULL
    """).fetchone()[0]
    
    print(f"Games WITH xG data: {with_xg}")
    print(f"Games WITHOUT xG data: {without_xg}")
    print()
    
    # Check if statistics table has data
    stats_count = conn.execute("SELECT COUNT(*) FROM game_statistics").fetchone()[0]
    print(f"Games with statistics table entries: {stats_count}")
    print()
    
    # Sample games without xG
    print("Sample games WITHOUT xG:")
    print("-" * 70)
    sample = conn.execute("""
        SELECT id, date, home_team_name, away_team_name, 
               calculated_xg_home, calculated_xg_away
        FROM games
        WHERE calculated_xg_home IS NULL OR calculated_xg_away IS NULL
        LIMIT 5
    """).fetchall()
    
    for row in sample:
        print(f"Game {row['id']}: {row['home_team_name']} vs {row['away_team_name']}")
        print(f"  Date: {row['date']}")
        print(f"  xG Home: {row['calculated_xg_home']}, xG Away: {row['calculated_xg_away']}")
        print()
    
    # Check a specific game from API
    print("=" * 70)
    print("Testing API Response for a Game:")
    print("=" * 70)
    
    # Get a game ID from database
    test_game = conn.execute("SELECT id FROM games LIMIT 1").fetchone()
    if test_game:
        game_id = test_game[0]
        print(f"Testing Game ID: {game_id}")
        
        try:
            client = SStatsClient(base_url=cfg.BASE_URL, api_key=getattr(cfg, 'API_KEY', None))
            game_data = client.get_game(game_id)
            
            # Check structure
            print("\nAPI Response Structure:")
            if "data" in game_data:
                if "game" in game_data["data"]:
                    game = game_data["data"]["game"]
                    print("  Format: {'data': {'game': {...}}}")
                else:
                    game = game_data["data"]
                    print("  Format: {'data': {...}}")
            elif "game" in game_data:
                game = game_data["game"]
                print("  Format: {'game': {...}}")
            else:
                game = game_data
                print("  Format: {...}")
            
            # Check for statistics
            stats = game.get("statistics", {})
            print(f"\nStatistics present: {bool(stats)}")
            
            if stats:
                print(f"  calculatedXgHome: {stats.get('calculatedXgHome')}")
                print(f"  calculatedXgAway: {stats.get('calculatedXgAway')}")
                print(f"  expectedGoalsHome: {stats.get('expectedGoalsHome')}")
                print(f"  expectedGoalsAway: {stats.get('expectedGoalsAway')}")
                
                # Check all keys
                print(f"\n  Statistics keys: {list(stats.keys())[:10]}...")
            else:
                print("  WARNING: No statistics in API response!")
            
        except Exception as e:
            print(f"Error fetching game from API: {e}")
            import traceback
            traceback.print_exc()
    
    # Check if games were loaded with details
    print("\n" + "=" * 70)
    print("Checking if games have full details:")
    print("=" * 70)
    
    # Check for events, lineups, etc.
    events_count = conn.execute("SELECT COUNT(DISTINCT game_id) FROM game_events").fetchone()[0]
    lineups_count = conn.execute("SELECT COUNT(DISTINCT game_id) FROM game_lineups").fetchone()[0]
    player_stats_count = conn.execute("SELECT COUNT(DISTINCT game_id) FROM player_statistics").fetchone()[0]
    
    print(f"Games with events: {events_count}")
    print(f"Games with lineups: {lineups_count}")
    print(f"Games with player statistics: {player_stats_count}")
    print()
    
    if stats_count == 0:
        print("WARNING: No statistics table entries found!")
        print("This suggests games were loaded WITHOUT full details.")
        print("You need to reload games with 'load_details=True'")
    
    db_manager.close()


if __name__ == "__main__":
    debug_database()























