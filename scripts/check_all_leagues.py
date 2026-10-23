"""Check all leagues in database"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import DatabaseManager
import sqlite3

db = DatabaseManager("data/flashscore.db")
conn = db.get_connection()
conn.row_factory = sqlite3.Row

# Get all distinct leagues
rows = conn.execute("""
    SELECT DISTINCT 
        league_id,
        league_name,
        country_name,
        COUNT(*) as game_count
    FROM games
    WHERE league_id IS NOT NULL
    GROUP BY league_id, league_name, country_name
    ORDER BY country_name, league_name
""").fetchall()

print(f"Total leagues in database: {len(rows)}")
print("=" * 70)
for row in rows:
    print(f"ID: {row['league_id']:3d} | {row['league_name']:40s} | {row['country_name']:20s} | {row['game_count']:5d} games")

conn.close()


















