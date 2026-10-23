"""Check League 188 data in database"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import DatabaseManager
import sqlite3

db = DatabaseManager("data/flashscore.db")
conn = db.get_connection()
conn.row_factory = sqlite3.Row

# Check League 188
row = conn.execute("""
    SELECT DISTINCT league_id, league_name, country_name, country_code
    FROM games 
    WHERE league_id = 188
    LIMIT 1
""").fetchone()

if row:
    print(f"League 188 in database:")
    print(f"  League Name: {row['league_name']}")
    print(f"  Country: {row['country_name']}")
    print(f"  Country Code: {row['country_code']}")
else:
    print("League 188 not found in database")

conn.close()


















