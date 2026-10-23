"""Script to check how many leagues are loaded in database and show progress"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from database import DatabaseManager
import sqlite3


def main():
    """Check league loading progress"""
    print("=" * 70)
    print("League Loading Progress Report")
    print("=" * 70)
    print()
    
    # Initialize database
    db_manager = DatabaseManager("data/flashscore.db")
    conn = db_manager.get_connection()
    conn.row_factory = sqlite3.Row
    
    # Target leagues that should be loaded
    # Scottish leagues: 179 = Scottish Premiership, 180 = Scottish Championship
    # French leagues: 61 = Ligue 1, 62 = Ligue 2, 63 = National 1
    # Spanish leagues: 140 = La Liga, 141 = Segunda División
    # Indonesian leagues: 274 = Liga 1, 275 = Liga 2
    target_league_ids = [145, 144, 39, 40, 41, 42, 179, 180, 61, 62, 63, 140, 141, 135, 136, 307, 308, 303, 301, 188, 274, 275]
    
    # Get all leagues from database
    leagues_in_db = conn.execute("""
        SELECT DISTINCT 
            league_id,
            COALESCE(league_name, 'Unknown League') as league_name,
            COALESCE(country_name, 'Unknown') as country_name,
            COUNT(*) as game_count,
            SUM(CASE WHEN season_year = 2022 THEN 1 ELSE 0 END) as games_2022,
            SUM(CASE WHEN season_year = 2023 THEN 1 ELSE 0 END) as games_2023,
            SUM(CASE WHEN season_year = 2024 THEN 1 ELSE 0 END) as games_2024,
            SUM(CASE WHEN season_year = 2025 THEN 1 ELSE 0 END) as games_2025,
            SUM(CASE WHEN calculated_xg_home IS NOT NULL AND calculated_xg_away IS NOT NULL THEN 1 ELSE 0 END) as games_with_xg
        FROM games
        WHERE league_id IS NOT NULL
        GROUP BY league_id, league_name, country_name
        ORDER BY country_name, league_name
    """).fetchall()
    
    # Count leagues
    total_leagues_in_db = len(leagues_in_db)
    leagues_with_games = [row for row in leagues_in_db if row['game_count'] > 0]
    leagues_with_xg = [row for row in leagues_in_db if row['games_with_xg'] > 0]
    
    # Check target leagues
    found_target_leagues = set()
    for row in leagues_in_db:
        found_target_leagues.add(row['league_id'])
    
    target_leagues_loaded = len([lid for lid in target_league_ids if lid in found_target_leagues])
    target_leagues_missing = [lid for lid in target_league_ids if lid not in found_target_leagues]
    
    # Calculate progress
    target_progress = (target_leagues_loaded / len(target_league_ids)) * 100 if target_league_ids else 0
    
    print(f"Total Leagues in Database: {total_leagues_in_db}")
    print(f"Leagues with Games: {len(leagues_with_games)}")
    print(f"Leagues with xG Data: {len(leagues_with_xg)}")
    print()
    print(f"Target Leagues Progress: {target_leagues_loaded}/{len(target_league_ids)} ({target_progress:.1f}%)")
    print()
    
    # Show target leagues status
    print("Target Leagues Status:")
    print("-" * 70)
    league_names_map = {
        145: "Challenger Pro League",
        144: "Jupiler Pro League",
        39: "Premier League (GB)",
        40: "Championship (GB)",
        41: "League One (GB)",
        42: "League Two (GB)",
        179: "Scottish Premiership",
        180: "Scottish Championship",
        61: "Ligue 1",
        62: "Ligue 2",
        63: "National 1",
        140: "La Liga",
        141: "Segunda División",
        135: "Serie A",
        136: "Serie B",
        307: "Saudi Pro League",
        308: "Saudi Division 1",
        303: "UAE Division 1",
        301: "UAE Pro League",
        188: "A-League",
        190: "A-League Women",
        274: "Liga 1",
        275: "Liga 2"
    }
    
    country_map = {
        145: "Belgium", 144: "Belgium",
        39: "Great Britain", 40: "Great Britain", 41: "Great Britain", 42: "Great Britain",
        179: "Scotland", 180: "Scotland",
        61: "France", 62: "France", 63: "France",
        140: "Spain", 141: "Spain",
        135: "Italy", 136: "Italy",
        307: "Saudi Arabia", 308: "Saudi Arabia",
        303: "United Arab Emirates", 301: "United Arab Emirates",
        188: "Australia", 190: "Australia",
        274: "Indonesia", 275: "Indonesia"
    }
    
    for league_id in target_league_ids:
        status = "[OK] LOADED" if league_id in found_target_leagues else "[X] MISSING"
        league_name = league_names_map.get(league_id, f"League {league_id}")
        country = country_map.get(league_id, "Unknown")
        
        if league_id in found_target_leagues:
            # Get stats for this league
            league_data = next((row for row in leagues_in_db if row['league_id'] == league_id), None)
            if league_data:
                games = league_data['game_count']
                xg_games = league_data['games_with_xg']
                xg_pct = (xg_games / games * 100) if games > 0 else 0
                games_2022 = league_data['games_2022']
                games_2023 = league_data['games_2023']
                games_2024 = league_data['games_2024']
                games_2025 = league_data['games_2025']
                print(f"  {status} | {country:20} | {league_name:25} | Games: {games:4} | xG: {xg_games:4} ({xg_pct:5.1f}%) | 2022:{games_2022:4} 2023:{games_2023:4} 2024:{games_2024:4} 2025:{games_2025:4}")
            else:
                print(f"  {status} | {country:20} | {league_name:25} | (no data)")
        else:
            print(f"  {status} | {country:20} | {league_name:25}")
    
    print()
    print("=" * 70)
    print("All Leagues in Database:")
    print("=" * 70)
    print(f"{'Country':<20} {'League Name':<30} {'ID':<6} {'Games':<8} {'xG':<8} {'2022':<6} {'2023':<6} {'2024':<6} {'2025':<6}")
    print("-" * 70)
    
    for row in leagues_in_db:
        country = row['country_name'] or "Unknown"
        league_name = row['league_name'] or f"League {row['league_id']}"
        league_id = row['league_id']
        games = row['game_count']
        xg_games = row['games_with_xg']
        xg_pct = (xg_games / games * 100) if games > 0 else 0
        games_2022 = row['games_2022']
        games_2023 = row['games_2023']
        games_2024 = row['games_2024']
        games_2025 = row['games_2025']
        
        print(f"{country:<20} {league_name:<30} {league_id:<6} {games:<8} {xg_games:<8} ({xg_pct:5.1f}%) {games_2022:<6} {games_2023:<6} {games_2024:<6} {games_2025:<6}")
    
    print()
    print("=" * 70)
    print("Summary Statistics:")
    print("=" * 70)
    
    # Total games
    total_games = conn.execute("SELECT COUNT(*) FROM games").fetchone()[0]
    total_games_2022 = conn.execute("SELECT COUNT(*) FROM games WHERE season_year = 2022").fetchone()[0]
    total_games_with_xg = conn.execute("""
        SELECT COUNT(*) FROM games 
        WHERE calculated_xg_home IS NOT NULL AND calculated_xg_away IS NOT NULL
    """).fetchone()[0]
    
    xg_progress = (total_games_with_xg / total_games * 100) if total_games > 0 else 0
    
    print(f"Total Games in Database: {total_games}")
    print(f"Games with xG Data: {total_games_with_xg} ({xg_progress:.1f}%)")
    print(f"Games from 2022: {total_games_2022}")
    print()
    
    # Database size
    size_info = db_manager.get_database_size()
    print(f"Database Size: {size_info['file_size_mb']:.2f} MB")
    print(f"Games with Statistics: {size_info['statistics']}")
    print(f"Total Events: {size_info['events']}")
    print()
    
    print("=" * 70)
    print("Done!")
    print("=" * 70)


if __name__ == "__main__":
    main()


from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from database import DatabaseManager
import sqlite3


def main():
    """Check league loading progress"""
    print("=" * 70)
    print("League Loading Progress Report")
    print("=" * 70)
    print()
    
    # Initialize database
    db_manager = DatabaseManager("data/flashscore.db")
    conn = db_manager.get_connection()
    conn.row_factory = sqlite3.Row
    
    # Target leagues that should be loaded
    # Scottish leagues: 179 = Scottish Premiership, 180 = Scottish Championship
    # French leagues: 61 = Ligue 1, 62 = Ligue 2, 63 = National 1
    # Spanish leagues: 140 = La Liga, 141 = Segunda División
    # Indonesian leagues: 274 = Liga 1, 275 = Liga 2
    target_league_ids = [145, 144, 39, 40, 41, 42, 179, 180, 61, 62, 63, 140, 141, 135, 136, 307, 308, 303, 301, 188, 274, 275]
    
    # Get all leagues from database
    leagues_in_db = conn.execute("""
        SELECT DISTINCT 
            league_id,
            COALESCE(league_name, 'Unknown League') as league_name,
            COALESCE(country_name, 'Unknown') as country_name,
            COUNT(*) as game_count,
            SUM(CASE WHEN season_year = 2022 THEN 1 ELSE 0 END) as games_2022,
            SUM(CASE WHEN season_year = 2023 THEN 1 ELSE 0 END) as games_2023,
            SUM(CASE WHEN season_year = 2024 THEN 1 ELSE 0 END) as games_2024,
            SUM(CASE WHEN season_year = 2025 THEN 1 ELSE 0 END) as games_2025,
            SUM(CASE WHEN calculated_xg_home IS NOT NULL AND calculated_xg_away IS NOT NULL THEN 1 ELSE 0 END) as games_with_xg
        FROM games
        WHERE league_id IS NOT NULL
        GROUP BY league_id, league_name, country_name
        ORDER BY country_name, league_name
    """).fetchall()
    
    # Count leagues
    total_leagues_in_db = len(leagues_in_db)
    leagues_with_games = [row for row in leagues_in_db if row['game_count'] > 0]
    leagues_with_xg = [row for row in leagues_in_db if row['games_with_xg'] > 0]
    
    # Check target leagues
    found_target_leagues = set()
    for row in leagues_in_db:
        found_target_leagues.add(row['league_id'])
    
    target_leagues_loaded = len([lid for lid in target_league_ids if lid in found_target_leagues])
    target_leagues_missing = [lid for lid in target_league_ids if lid not in found_target_leagues]
    
    # Calculate progress
    target_progress = (target_leagues_loaded / len(target_league_ids)) * 100 if target_league_ids else 0
    
    print(f"Total Leagues in Database: {total_leagues_in_db}")
    print(f"Leagues with Games: {len(leagues_with_games)}")
    print(f"Leagues with xG Data: {len(leagues_with_xg)}")
    print()
    print(f"Target Leagues Progress: {target_leagues_loaded}/{len(target_league_ids)} ({target_progress:.1f}%)")
    print()
    
    # Show target leagues status
    print("Target Leagues Status:")
    print("-" * 70)
    league_names_map = {
        145: "Challenger Pro League",
        144: "Jupiler Pro League",
        39: "Premier League",
        40: "Championship",
        41: "League One",
        42: "League Two",
        50: "Scottish Premiership",
        51: "Scottish Championship",
        135: "Serie A",
        136: "Serie B",
        307: "Saudi Pro League",
        308: "Saudi Division 1",
        303: "UAE Division 1",
        301: "UAE Pro League",
        188: "A-League",
        190: "A-League Women"
    }
    
    country_map = {
        145: "Belgium", 144: "Belgium",
        39: "Great Britain", 40: "Great Britain", 41: "Great Britain", 42: "Great Britain",
        50: "Scotland", 51: "Scotland",
        135: "Italy", 136: "Italy",
        307: "Saudi Arabia", 308: "Saudi Arabia",
        303: "United Arab Emirates", 301: "United Arab Emirates",
        188: "Australia"
    }
    
    for league_id in target_league_ids:
        status = "[OK] LOADED" if league_id in found_target_leagues else "[X] MISSING"
        league_name = league_names_map.get(league_id, f"League {league_id}")
        country = country_map.get(league_id, "Unknown")
        
        if league_id in found_target_leagues:
            # Get stats for this league
            league_data = next((row for row in leagues_in_db if row['league_id'] == league_id), None)
            if league_data:
                games = league_data['game_count']
                xg_games = league_data['games_with_xg']
                xg_pct = (xg_games / games * 100) if games > 0 else 0
                games_2022 = league_data['games_2022']
                games_2023 = league_data['games_2023']
                games_2024 = league_data['games_2024']
                games_2025 = league_data['games_2025']
                print(f"  {status} | {country:20} | {league_name:25} | Games: {games:4} | xG: {xg_games:4} ({xg_pct:5.1f}%) | 2022:{games_2022:4} 2023:{games_2023:4} 2024:{games_2024:4} 2025:{games_2025:4}")
            else:
                print(f"  {status} | {country:20} | {league_name:25} | (no data)")
        else:
            print(f"  {status} | {country:20} | {league_name:25}")
    
    print()
    print("=" * 70)
    print("All Leagues in Database:")
    print("=" * 70)
    print(f"{'Country':<20} {'League Name':<30} {'ID':<6} {'Games':<8} {'xG':<8} {'2022':<6} {'2023':<6} {'2024':<6} {'2025':<6}")
    print("-" * 70)
    
    for row in leagues_in_db:
        country = row['country_name'] or "Unknown"
        league_name = row['league_name'] or f"League {row['league_id']}"
        league_id = row['league_id']
        games = row['game_count']
        xg_games = row['games_with_xg']
        xg_pct = (xg_games / games * 100) if games > 0 else 0
        games_2022 = row['games_2022']
        games_2023 = row['games_2023']
        games_2024 = row['games_2024']
        games_2025 = row['games_2025']
        
        print(f"{country:<20} {league_name:<30} {league_id:<6} {games:<8} {xg_games:<8} ({xg_pct:5.1f}%) {games_2022:<6} {games_2023:<6} {games_2024:<6} {games_2025:<6}")
    
    print()
    print("=" * 70)
    print("Summary Statistics:")
    print("=" * 70)
    
    # Total games
    total_games = conn.execute("SELECT COUNT(*) FROM games").fetchone()[0]
    total_games_2022 = conn.execute("SELECT COUNT(*) FROM games WHERE season_year = 2022").fetchone()[0]
    total_games_with_xg = conn.execute("""
        SELECT COUNT(*) FROM games 
        WHERE calculated_xg_home IS NOT NULL AND calculated_xg_away IS NOT NULL
    """).fetchone()[0]
    
    xg_progress = (total_games_with_xg / total_games * 100) if total_games > 0 else 0
    
    print(f"Total Games in Database: {total_games}")
    print(f"Games with xG Data: {total_games_with_xg} ({xg_progress:.1f}%)")
    print(f"Games from 2022: {total_games_2022}")
    print()
    
    # Database size
    size_info = db_manager.get_database_size()
    print(f"Database Size: {size_info['file_size_mb']:.2f} MB")
    print(f"Games with Statistics: {size_info['statistics']}")
    print(f"Total Events: {size_info['events']}")
    print()
    
    print("=" * 70)
    print("Done!")
    print("=" * 70)


if __name__ == "__main__":
    main()


