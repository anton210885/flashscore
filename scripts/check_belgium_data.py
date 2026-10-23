"""Python Script zum Überprüfen der belgischen Ligen-Daten in der Datenbank"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import DatabaseManager

def check_belgium_data():
    """Überprüfe belgische Ligen-Daten in der Datenbank"""
    print("=" * 70)
    print("Überprüfung der belgischen Ligen-Daten")
    print("=" * 70)
    print()
    
    db_manager = DatabaseManager("data/flashscore.db")
    conn = db_manager.get_connection()
    
    # Übersicht: Anzahl Spiele pro Liga
    print("1. Übersicht: Anzahl Spiele pro Liga")
    print("-" * 70)
    rows = conn.execute("""
        SELECT 
            league_id,
            CASE 
                WHEN league_id = 144 THEN 'Jupiler Pro League'
                WHEN league_id = 145 THEN 'Challenger Pro League'
                ELSE 'Unknown'
            END AS league_name,
            COUNT(*) AS total_games,
            COUNT(CASE WHEN status IN (7, 8, 9, 10) THEN 1 END) AS finished_games,
            MIN(date) AS earliest_game,
            MAX(date) AS latest_game
        FROM games
        WHERE league_id IN (144, 145)
        GROUP BY league_id
    """).fetchall()
    
    for row in rows:
        print(f"  {row[1]} (ID: {row[0]}): {row[2]} Spiele ({row[3]} beendet)")
        print(f"    Von {row[4]} bis {row[5]}")
    print()
    
    # Spiele pro Jahr
    print("2. Spiele pro Jahr")
    print("-" * 70)
    rows = conn.execute("""
        SELECT 
            league_id,
            CASE 
                WHEN league_id = 144 THEN 'Jupiler Pro League'
                WHEN league_id = 145 THEN 'Challenger Pro League'
                ELSE 'Unknown'
            END AS league_name,
            season_year,
            COUNT(*) AS games_count
        FROM games
        WHERE league_id IN (144, 145)
        GROUP BY league_id, season_year
        ORDER BY league_id, season_year DESC
    """).fetchall()
    
    for row in rows:
        print(f"  {row[1]} {row[2]}: {row[3]} Spiele")
    print()
    
    # Spiele mit xG Daten
    print("3. Spiele mit xG Daten")
    print("-" * 70)
    rows = conn.execute("""
        SELECT 
            league_id,
            CASE 
                WHEN league_id = 144 THEN 'Jupiler Pro League'
                WHEN league_id = 145 THEN 'Challenger Pro League'
                ELSE 'Unknown'
            END AS league_name,
            COUNT(*) AS total_games,
            COUNT(calculated_xg_home) AS games_with_xg_home,
            COUNT(calculated_xg_away) AS games_with_xg_away,
            COUNT(CASE WHEN calculated_xg_home IS NOT NULL AND calculated_xg_away IS NOT NULL THEN 1 END) AS games_with_both_xg
        FROM games
        WHERE league_id IN (144, 145)
        GROUP BY league_id
    """).fetchall()
    
    for row in rows:
        print(f"  {row[1]}: {row[2]} Spiele total")
        print(f"    Mit xG Home: {row[3]}, Mit xG Away: {row[4]}, Mit beiden: {row[5]}")
    print()
    
    # Spiele mit Glicko Daten
    print("4. Spiele mit Glicko Daten")
    print("-" * 70)
    rows = conn.execute("""
        SELECT 
            g.league_id,
            CASE 
                WHEN g.league_id = 144 THEN 'Jupiler Pro League'
                WHEN g.league_id = 145 THEN 'Challenger Pro League'
                ELSE 'Unknown'
            END AS league_name,
            COUNT(DISTINCT g.id) AS total_games,
            COUNT(DISTINCT gl.game_id) AS games_with_glicko
        FROM games g
        LEFT JOIN game_glicko gl ON g.id = gl.game_id
        WHERE g.league_id IN (144, 145)
        GROUP BY g.league_id
    """).fetchall()
    
    for row in rows:
        print(f"  {row[1]}: {row[2]} Spiele total, {row[3]} mit Glicko")
    print()
    
    # Spiele mit Odds Daten
    print("5. Spiele mit Odds Daten")
    print("-" * 70)
    rows = conn.execute("""
        SELECT 
            g.league_id,
            CASE 
                WHEN g.league_id = 144 THEN 'Jupiler Pro League'
                WHEN g.league_id = 145 THEN 'Challenger Pro League'
                ELSE 'Unknown'
            END AS league_name,
            COUNT(DISTINCT g.id) AS total_games,
            COUNT(DISTINCT o.game_id) AS games_with_odds
        FROM games g
        LEFT JOIN game_odds o ON g.id = o.game_id
        WHERE g.league_id IN (144, 145)
        GROUP BY g.league_id
    """).fetchall()
    
    for row in rows:
        print(f"  {row[1]}: {row[2]} Spiele total, {row[3]} mit Odds")
    print()
    
    # Spiele mit Profit Daten
    print("6. Spiele mit Profit Daten")
    print("-" * 70)
    rows = conn.execute("""
        SELECT 
            g.league_id,
            CASE 
                WHEN g.league_id = 144 THEN 'Jupiler Pro League'
                WHEN g.league_id = 145 THEN 'Challenger Pro League'
                ELSE 'Unknown'
            END AS league_name,
            COUNT(DISTINCT g.id) AS total_games,
            COUNT(DISTINCT p.game_id) AS games_with_profits
        FROM games g
        LEFT JOIN game_profits p ON g.id = p.game_id
        WHERE g.league_id IN (144, 145)
        GROUP BY g.league_id
    """).fetchall()
    
    for row in rows:
        print(f"  {row[1]}: {row[2]} Spiele total, {row[3]} mit Profits")
    print()
    
    # Beispiel: Letzte 10 Spiele mit Details
    print("7. Letzte 10 Spiele mit Details")
    print("-" * 70)
    rows = conn.execute("""
        SELECT 
            g.id,
            g.date,
            g.home_team_name,
            g.away_team_name,
            g.home_ft_result || '-' || g.away_ft_result AS score,
            g.calculated_xg_home,
            g.calculated_xg_away,
            CASE 
                WHEN g.league_id = 144 THEN 'Jupiler Pro League'
                WHEN g.league_id = 145 THEN 'Challenger Pro League'
                ELSE 'Unknown'
            END AS league_name
        FROM games g
        WHERE g.league_id IN (144, 145)
        ORDER BY g.date DESC
        LIMIT 10
    """).fetchall()
    
    for row in rows:
        print(f"  {row[1]} | {row[2]} vs {row[3]} | {row[4]} | xG: {row[5] or 'N/A'}-{row[6] or 'N/A'} | {row[7]}")
    print()
    
    print("Überprüfung abgeschlossen!")

if __name__ == "__main__":
    check_belgium_data()





















