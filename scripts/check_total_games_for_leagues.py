"""Check and calculate total games for specific leagues"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import DatabaseManager
import sqlite3

# Target leagues
target_leagues = [145, 144, 39, 40, 41, 42, 135, 136, 307, 308, 303, 301]

db = DatabaseManager("data/flashscore.db")
conn = db.get_connection()
conn.row_factory = sqlite3.Row

print("=" * 70)
print("Checking Total Games for Specific Leagues")
print("=" * 70)
print()

for league_id in target_leagues:
    # Get league name
    league_info = conn.execute("""
        SELECT DISTINCT league_name, country_name
        FROM games 
        WHERE league_id = ?
        LIMIT 1
    """, (league_id,)).fetchone()
    
    league_name = league_info['league_name'] if league_info else "Unknown"
    country_name = league_info['country_name'] if league_info else "Unknown"
    
    print(f"League {league_id}: {league_name} ({country_name})")
    print("-" * 70)
    
    # Check for each year
    for year in [2022, 2023, 2024, 2025]:
        # Count total games with results
        total = conn.execute("""
            SELECT COUNT(*) as total
            FROM games 
            WHERE league_id = ? AND season_year = ?
              AND home_ft_result IS NOT NULL 
              AND away_ft_result IS NOT NULL
        """, (league_id, year)).fetchone()['total']
        
        # Count all games (including without results)
        total_all = conn.execute("""
            SELECT COUNT(*) as total
            FROM games 
            WHERE league_id = ? AND season_year = ?
        """, (league_id, year)).fetchone()['total']
        
        # Count over 2.5
        over25 = conn.execute("""
            SELECT COUNT(*) as total
            FROM games 
            WHERE league_id = ? AND season_year = ?
              AND home_ft_result IS NOT NULL 
              AND away_ft_result IS NOT NULL
              AND (home_ft_result + away_ft_result) > 2.5
        """, (league_id, year)).fetchone()['total']
        
        if total > 0:
            over25_pct = (over25 / total) * 100
            print(f"  {year}: Total Games (finished): {total} | Total (all): {total_all} | Over 2.5: {over25} ({over25_pct:.1f}%)")
        elif total_all > 0:
            print(f"  {year}: Total Games (finished): {total} | Total (all): {total_all} | Over 2.5: N/A")
        else:
            print(f"  {year}: No games found")
    
    print()

conn.close()


















