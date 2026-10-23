"""Python script to check number of games per league and per year"""
import sys
from pathlib import Path
import sqlite3

sys.path.insert(0, str(Path(__file__).parent))

from database import DatabaseManager


def main():
    """Check games per league and year"""
    print("=" * 80)
    print("Games per League and Year Report")
    print("=" * 80)
    print()
    
    # Initialize database
    db_manager = DatabaseManager("data/flashscore.db")
    conn = db_manager.get_connection()
    conn.row_factory = sqlite3.Row
    
    # 1. Total games per league and year
    print("1. Games per League and Year:")
    print("-" * 80)
    print(f"{'League ID':<12} {'League Name':<35} {'Country':<20} {'Year':<8} {'Total':<8} {'Finished':<10} {'Unfinished':<12} {'With xG':<10}")
    print("-" * 80)
    
    rows = conn.execute("""
        SELECT 
            league_id,
            COALESCE(league_name, 'Unknown League') as league_name,
            COALESCE(country_name, 'Unknown') as country_name,
            season_year,
            COUNT(*) as total_games,
            COUNT(CASE WHEN home_ft_result IS NOT NULL AND away_ft_result IS NOT NULL THEN 1 END) as finished_games,
            COUNT(CASE WHEN home_ft_result IS NULL OR away_ft_result IS NULL THEN 1 END) as unfinished_games,
            COUNT(CASE WHEN calculated_xg_home IS NOT NULL AND calculated_xg_away IS NOT NULL THEN 1 END) as games_with_xg
        FROM games
        WHERE league_id IS NOT NULL
        GROUP BY league_id, league_name, country_name, season_year
        ORDER BY country_name, league_name, season_year DESC
    """).fetchall()
    
    for row in rows:
        season_year = row['season_year'] if row['season_year'] is not None else 'NULL'
        print(f"{row['league_id']:<12} {row['league_name']:<35} {row['country_name']:<20} {str(season_year):<8} {row['total_games']:<8} {row['finished_games']:<10} {row['unfinished_games']:<12} {row['games_with_xg']:<10}")
    
    print()
    print("=" * 80)
    print()
    
    # 2. Summary: Total games per league (all years combined)
    print("2. Summary: Total Games per League (All Years Combined):")
    print("-" * 80)
    print(f"{'League ID':<12} {'League Name':<35} {'Country':<20} {'Total':<8} {'Finished':<10} {'With xG':<10} {'First Year':<12} {'Last Year':<10}")
    print("-" * 80)
    
    rows = conn.execute("""
        SELECT 
            league_id,
            COALESCE(league_name, 'Unknown League') as league_name,
            COALESCE(country_name, 'Unknown') as country_name,
            COUNT(*) as total_games_all_years,
            COUNT(CASE WHEN home_ft_result IS NOT NULL AND away_ft_result IS NOT NULL THEN 1 END) as finished_games_all_years,
            COUNT(CASE WHEN calculated_xg_home IS NOT NULL AND calculated_xg_away IS NOT NULL THEN 1 END) as games_with_xg_all_years,
            MIN(season_year) as first_year,
            MAX(season_year) as last_year
        FROM games
        WHERE league_id IS NOT NULL
        GROUP BY league_id, league_name, country_name
        ORDER BY country_name, league_name
    """).fetchall()
    
    for row in rows:
        print(f"{row['league_id']:<12} {row['league_name']:<35} {row['country_name']:<20} {row['total_games_all_years']:<8} {row['finished_games_all_years']:<10} {row['games_with_xg_all_years']:<10} {row['first_year']:<12} {row['last_year']:<10}")
    
    print()
    print("=" * 80)
    print()
    
    # 3. Summary: Total games per year (all leagues combined)
    print("3. Summary: Total Games per Year (All Leagues Combined):")
    print("-" * 80)
    print(f"{'Year':<8} {'Total Games':<15} {'Finished Games':<18} {'Games with xG':<18} {'Number of Leagues':<20}")
    print("-" * 80)
    
    rows = conn.execute("""
        SELECT 
            season_year,
            COUNT(*) as total_games,
            COUNT(CASE WHEN home_ft_result IS NOT NULL AND away_ft_result IS NOT NULL THEN 1 END) as finished_games,
            COUNT(CASE WHEN calculated_xg_home IS NOT NULL AND calculated_xg_away IS NOT NULL THEN 1 END) as games_with_xg,
            COUNT(DISTINCT league_id) as number_of_leagues
        FROM games
        WHERE league_id IS NOT NULL AND season_year IS NOT NULL
        GROUP BY season_year
        ORDER BY season_year DESC
    """).fetchall()
    
    for row in rows:
        print(f"{row['season_year']:<8} {row['total_games']:<15} {row['finished_games']:<18} {row['games_with_xg']:<18} {row['number_of_leagues']:<20}")
    
    print()
    print("=" * 80)
    print("Done!")
    print("=" * 80)
    
    conn.close()


if __name__ == "__main__":
    main()

