import sqlite3
from datetime import datetime, timezone

c = sqlite3.connect("data/flashscore.db")
c.row_factory = sqlite3.Row
print("cols upcoming", [r[1] for r in c.execute("PRAGMA table_info(upcoming_games)")])
rows = c.execute(
    "SELECT id, date, date_utc, status, status_name, home_team_name, away_team_name FROM upcoming_games ORDER BY id DESC LIMIT 15"
).fetchall()
for r in rows:
    utc = r["date_utc"]
    decoded = None
    if utc:
        try:
            decoded = datetime.fromtimestamp(int(utc), tz=timezone.utc).isoformat()
        except Exception as e:
            decoded = str(e)
    print(dict(r), "decoded_utc", decoded)

# finished games have proper dates
print("--- finished sample ---")
for r in c.execute(
    "SELECT id, date, date_utc, status_name, home_team_name FROM games ORDER BY date DESC LIMIT 5"
).fetchall():
    print(dict(r))
