"""Check if leagues are in the list"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import DatabaseManager
import sqlite3

db = DatabaseManager("data/flashscore.db")
conn = db.get_connection()
conn.row_factory = sqlite3.Row

# Get all leagues that have games
leagues = conn.execute("""
    SELECT DISTINCT 
        league_id as id,
        league_name as name,
        country_name as country
    FROM games
    WHERE league_id IN (145, 188)
    ORDER BY league_id
""").fetchall()

print("=" * 70)
print("Leagues in Database")
print("=" * 70)
print()

for league in leagues:
    print(f"ID: {league['id']}, Name: {league['name']}, Country: {league['country']}")
    
    # Check if it has 2025 games
    count_2025 = conn.execute("""
        SELECT COUNT(*) as count
        FROM games
        WHERE league_id = ? AND season_year = 2025
    """, (league['id'],)).fetchone()
    print(f"  2025 games: {count_2025['count']}")
    print()

conn.close()


















