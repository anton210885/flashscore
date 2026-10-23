"""Check league data for specific leagues"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import DatabaseManager
import sqlite3

db = DatabaseManager("data/flashscore.db")
conn = db.get_connection()
conn.row_factory = sqlite3.Row

# Check League 145 and 188
result = conn.execute("""
    SELECT 
        league_id, 
        season_year, 
        COUNT(*) as count,
        MIN(date) as min_date, 
        MAX(date) as max_date,
        SUM(CASE WHEN (home_ft_result IS NOT NULL AND away_ft_result IS NOT NULL) THEN 1 ELSE 0 END) as finished_games
    FROM games 
    WHERE league_id IN (145, 188) 
    GROUP BY league_id, season_year 
    ORDER BY league_id, season_year
""").fetchall()

print("=" * 70)
print("League Data Check")
print("=" * 70)
print()

for league_id in [145, 188]:
    print(f"League {league_id}:")
    league_data = [r for r in result if r['league_id'] == league_id]
    if not league_data:
        print("  No data found!")
    else:
        for r in league_data:
            print(f"  Year {r['season_year']}: {r['count']} total games, {r['finished_games']} finished games")
            print(f"    Date range: {r['min_date']} to {r['max_date']}")
    print()

# Check specifically for 2025
print("=" * 70)
print("2025 Data Check")
print("=" * 70)
print()

for league_id in [145, 188]:
    result_2025 = conn.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN (status IN (7, 8, 9, 10) OR (home_ft_result IS NOT NULL AND away_ft_result IS NOT NULL)) THEN 1 ELSE 0 END) as finished,
            SUM(CASE WHEN (COALESCE(home_ft_result, 0) + COALESCE(away_ft_result, 0)) > 2.5 THEN 1 ELSE 0 END) as over25
        FROM games 
        WHERE league_id = ? AND season_year = 2025
    """, (league_id,)).fetchone()
    
    print(f"League {league_id} (2025):")
    print(f"  Total games in DB: {result_2025['total']}")
    print(f"  Finished games: {result_2025['finished']}")
    print(f"  Over 2.5: {result_2025['over25']}")
    print()

conn.close()

