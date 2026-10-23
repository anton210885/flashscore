"""Check league data by league_id and year"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import DatabaseManager
import sqlite3

db = DatabaseManager("data/flashscore.db")
conn = db.get_connection()
conn.row_factory = sqlite3.Row

# Check League 183 (Scotland League One) for different years
league_id = 183
print("=" * 70)
print(f"Checking League {league_id} (Scotland League One)")
print("=" * 70)
print()

# Get all years for this league
years = conn.execute("""
    SELECT DISTINCT season_year, COUNT(*) as count
    FROM games 
    WHERE league_id = ?
    GROUP BY season_year
    ORDER BY season_year DESC
""", (league_id,)).fetchall()

print(f"Years found in database for League {league_id}:")
for row in years:
    print(f"  Year {row['season_year']}: {row['count']} games")

print()

# Check specifically for 2025
result_2025 = conn.execute("""
    SELECT 
        COUNT(*) as total,
        MIN(date) as min_date,
        MAX(date) as max_date
    FROM games 
    WHERE league_id = ? AND season_year = 2025
""", (league_id,)).fetchone()

print(f"League {league_id} (2025):")
print(f"  Total games: {result_2025['total']}")
print(f"  Date range: {result_2025['min_date']} to {result_2025['max_date']}")
print()

# Check if there are games with wrong year
wrong_year = conn.execute("""
    SELECT COUNT(*) as count
    FROM games 
    WHERE league_id = ?
      AND date LIKE '2025%'
      AND season_year != 2025
""", (league_id,)).fetchone()

print(f"Games with date in 2025 but season_year != 2025: {wrong_year['count']}")

conn.close()


















