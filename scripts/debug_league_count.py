"""Debug league count for specific leagues"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import DatabaseManager
import sqlite3

db = DatabaseManager("data/flashscore.db")
conn = db.get_connection()
conn.row_factory = sqlite3.Row

def get_games_count_for_league(league_id, year):
    """Same function as in league_tab.py"""
    try:
        count = conn.execute("""
            SELECT COUNT(*) as count
            FROM games 
            WHERE league_id = ? AND season_year = ?
        """, (league_id, int(year))).fetchone()
        
        if count and count['count'] > 0:
            stats = conn.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN (COALESCE(home_ft_result, 0) + COALESCE(away_ft_result, 0)) > 2.5 THEN 1 ELSE 0 END) as over25,
                    SUM(CASE WHEN (COALESCE(home_ft_result, 0) + COALESCE(away_ft_result, 0)) > 3.5 THEN 1 ELSE 0 END) as over35,
                    SUM(CASE WHEN (COALESCE(home_ft_result, 0) + COALESCE(away_ft_result, 0)) > 4.5 THEN 1 ELSE 0 END) as over45
                FROM games 
                WHERE league_id = ? AND season_year = ? 
                  AND (status IN (7, 8, 9, 10) OR (home_ft_result IS NOT NULL AND away_ft_result IS NOT NULL))
            """, (league_id, int(year))).fetchone()
            
            total = stats['total'] or 0
            return {"total": total}
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    return {"total": 0}

print("=" * 70)
print("Debug League Count")
print("=" * 70)
print()

for league_id in [145, 188]:
    print(f"League {league_id} (2025):")
    result = get_games_count_for_league(league_id, 2025)
    print(f"  Function returns: {result['total']} games")
    
    # Also check raw query
    raw_count = conn.execute("""
        SELECT COUNT(*) as count
        FROM games 
        WHERE league_id = ? AND season_year = 2025
    """, (league_id,)).fetchone()
    print(f"  Raw count (all games): {raw_count['count']}")
    
    raw_finished = conn.execute("""
        SELECT COUNT(*) as count
        FROM games 
        WHERE league_id = ? AND season_year = 2025
          AND (status IN (7, 8, 9, 10) OR (home_ft_result IS NOT NULL AND away_ft_result IS NOT NULL))
    """, (league_id,)).fetchone()
    print(f"  Raw count (finished): {raw_finished['count']}")
    print()

conn.close()


















