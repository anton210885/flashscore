"""Script to show max streaks for season 2022 (2.5, 3.5, 4.5) per league"""
import sys
from pathlib import Path
import statistics

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import DatabaseManager

def calculate_streak_stats(games, threshold='25'):
    """
    Calculate streak statistics for Over X.5 goals from a list of games.
    Games should be ordered by date (oldest first).
    
    Args:
        games: List of game dictionaries or tuples with over_25, over_35, over_45 values
        threshold: '25', '35', or '45' for Over 2.5, 3.5, or 4.5
    
    Returns: (max_streak, min_streak, median_streak, all_streaks)
    """
    if not games:
        return 0, 0, 0, []
    
    all_streaks = []
    current_streak = 0
    
    for game in games:
        # Handle both dict and tuple formats
        if isinstance(game, dict):
            if threshold == '25':
                over_value = game.get('over_25', 0)
            elif threshold == '35':
                over_value = game.get('over_35', 0)
            elif threshold == '45':
                over_value = game.get('over_45', 0)
            else:
                over_value = 0
        else:
            # Tuple format: (over_25, over_35, over_45)
            if threshold == '25':
                over_value = game[0] if len(game) > 0 else 0
            elif threshold == '35':
                over_value = game[1] if len(game) > 1 else 0
            elif threshold == '45':
                over_value = game[2] if len(game) > 2 else 0
            else:
                over_value = 0
        
        if over_value == 1:  # Over X.5 - continue streak
            current_streak += 1
        else:  # Under X.5 - streak ends
            if current_streak > 0:
                all_streaks.append(current_streak)
            current_streak = 0
    
    # Don't forget the last streak if it ends with Over
    if current_streak > 0:
        all_streaks.append(current_streak)
    
    if not all_streaks:
        return 0, 0, 0, []
    
    max_streak = max(all_streaks)
    min_streak = min(all_streaks)
    median_streak = statistics.median(all_streaks) if all_streaks else 0.0
    
    return max_streak, min_streak, median_streak, all_streaks

def show_max_streaks_2022():
    """Show max streaks for season 2022 for all leagues"""
    print("=" * 100)
    print("Max Streaks für Season 2022 (2.5, 3.5, 4.5 Goals) pro Liga")
    print("=" * 100)
    print()
    
    # Initialize database
    db_manager = DatabaseManager("data/flashscore.db")
    conn = db_manager.get_connection()
    
    # Get all distinct leagues
    leagues = conn.execute("""
        SELECT DISTINCT 
            league_id,
            COALESCE(league_name, 'Unknown League') as league_name,
            COALESCE(country_name, 'Unknown') as country_name
        FROM games
        WHERE league_id IS NOT NULL
          AND season_year = 2022
        ORDER BY country_name, league_name
    """).fetchall()
    
    if not leagues:
        print("Keine Ligen mit Spielen für Season 2022 gefunden.")
        return
    
    # Print header
    print(f"{'ID':<5} | {'Land':<20} | {'Liga':<35} | {'Max 2.5':<10} | {'Min 2.5':<10} | {'Max 3.5':<10} | {'Min 3.5':<10} | {'Max 4.5':<10} | {'Min 4.5':<10}")
    print("-" * 120)
    
    results = []
    
    # Calculate streaks for each league
    for league in leagues:
        league_id, league_name, country_name = league
        
        # Get all games for this league in 2022, ordered by date
        games_data = conn.execute("""
            SELECT over_25, over_35, over_45, total_goals
            FROM games
            WHERE league_id = ?
              AND season_year = 2022
              AND status IN (7, 8, 9, 10)  -- Finished games only
            ORDER BY date ASC
        """, (league_id,)).fetchall()
        
        if not games_data:
            continue
        
        # Calculate streaks for each threshold
        # Convert to dict format for calculate_streak_stats
        # Handle NULL values by converting them to 0
        games_list_25 = [{'over_25': (row[0] if row[0] is not None else 0)} for row in games_data]
        games_list_35 = [{'over_35': (row[1] if row[1] is not None else 0)} for row in games_data]
        games_list_45 = [{'over_45': (row[2] if row[2] is not None else 0)} for row in games_data]
        
        max_25, min_25, _, _ = calculate_streak_stats(games_list_25, '25')
        max_35, min_35, _, _ = calculate_streak_stats(games_list_35, '35')
        max_45, min_45, _, _ = calculate_streak_stats(games_list_45, '45')
        
        results.append((league_id, league_name, country_name, max_25, min_25, max_35, min_35, max_45, min_45))
        
        print(f"{league_id:<5} | {country_name:<20} | {league_name:<35} | {max_25:<10} | {min_25:<10} | {max_35:<10} | {min_35:<10} | {max_45:<10} | {min_45:<10}")
    
    print()
    print("=" * 100)
    
    # Statistics
    if results:
        print(f"\nStatistik:")
        print(f"  Gesamt Ligen: {len(results)}")
        
        # Find leagues with highest and lowest streaks
        max_25_league = max(results, key=lambda x: x[3] or 0)
        max_35_league = max(results, key=lambda x: x[5] or 0)
        max_45_league = max(results, key=lambda x: x[7] or 0)
        
        # Find leagues with lowest streaks (excluding 0)
        min_25_leagues = [r for r in results if r[4] > 0]
        min_35_leagues = [r for r in results if r[6] > 0]
        min_45_leagues = [r for r in results if r[8] > 0]
        
        min_25_league = min(min_25_leagues, key=lambda x: x[4]) if min_25_leagues else None
        min_35_league = min(min_35_leagues, key=lambda x: x[6]) if min_35_leagues else None
        min_45_league = min(min_45_leagues, key=lambda x: x[8]) if min_45_leagues else None
        
        print(f"\nHöchste Streaks für Season 2022:")
        if max_25_league[3] and max_25_league[3] > 0:
            print(f"  2.5 Goals: {max_25_league[3]} - {max_25_league[2]} - {max_25_league[1]} (ID: {max_25_league[0]})")
        if max_35_league[5] and max_35_league[5] > 0:
            print(f"  3.5 Goals: {max_35_league[5]} - {max_35_league[2]} - {max_35_league[1]} (ID: {max_35_league[0]})")
        if max_45_league[7] and max_45_league[7] > 0:
            print(f"  4.5 Goals: {max_45_league[7]} - {max_45_league[2]} - {max_45_league[1]} (ID: {max_45_league[0]})")
        
        print(f"\nNiedrigste Streaks für Season 2022 (min > 0):")
        if min_25_league:
            print(f"  2.5 Goals: {min_25_league[4]} - {min_25_league[2]} - {min_25_league[1]} (ID: {min_25_league[0]})")
        if min_35_league:
            print(f"  3.5 Goals: {min_35_league[6]} - {min_35_league[2]} - {min_35_league[1]} (ID: {min_35_league[0]})")
        if min_45_league:
            print(f"  4.5 Goals: {min_45_league[8]} - {min_45_league[2]} - {min_45_league[1]} (ID: {min_45_league[0]})")

if __name__ == "__main__":
    show_max_streaks_2022()

