"""Script to calculate max, min, and median streaks for Under 2.5 goals and store in leagues table"""
import sys
from pathlib import Path
import statistics

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import DatabaseManager
from datetime import datetime

def calculate_streak_stats(games, threshold='25'):
    """
    Calculate streak statistics for Over X.5 goals from a list of games.
    Games should be ordered by date (oldest first).
    
    Args:
        games: List of game dictionaries
        threshold: '25', '35', or '45' for Over 2.5, 3.5, or 4.5
    
    Returns: (max_streak, min_streak, median_streak, all_streaks)
    - max_streak: Maximum consecutive Over X.5 streak
    - min_streak: Minimum consecutive Over X.5 streak (shortest streak > 0)
    - median_streak: Median of all Over X.5 streaks
    - all_streaks: List of all streak lengths
    """
    if not games:
        return 0, 0, 0, []
    
    all_streaks = []
    current_streak = 0
    
    for game in games:
        if threshold == '25':
            over_value = game.get('over_25', 0)
        elif threshold == '35':
            over_value = game.get('over_35', 0)
        elif threshold == '45':
            over_value = game.get('over_45', 0)
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
    min_streak = min(all_streaks)  # Minimum of all streaks (shortest streak > 0)
    median_streak = statistics.median(all_streaks) if all_streaks else 0.0
    
    return max_streak, min_streak, median_streak, all_streaks

def calculate_league_streaks():
    """Calculate max, min, and median streaks for Over 2.5, 3.5, and 4.5 goals for all leagues"""
    print("=" * 70)
    print("Calculating Streak Statistics for Over 2.5, 3.5, and 4.5 Goals")
    print("=" * 70)
    print()
    
    # Initialize database
    db_manager = DatabaseManager("data/flashscore.db")
    conn = db_manager.get_connection()
    
    # Create leagues table if it doesn't exist (with new columns)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS leagues (
            league_id INTEGER PRIMARY KEY,
            league_name TEXT,
            country_name TEXT,
            country_code TEXT,
            max_streak_current_season INTEGER DEFAULT 0,
            min_streak_current_season INTEGER DEFAULT 0,
            median_streak_current_season REAL DEFAULT 0,
            max_streak_all_seasons INTEGER DEFAULT 0,
            min_streak_all_seasons INTEGER DEFAULT 0,
            median_streak_all_seasons REAL DEFAULT 0,
            max_streak_current_season_35 INTEGER DEFAULT 0,
            median_streak_current_season_35 REAL DEFAULT 0,
            max_streak_all_seasons_35 INTEGER DEFAULT 0,
            median_streak_all_seasons_35 REAL DEFAULT 0,
            max_streak_current_season_45 INTEGER DEFAULT 0,
            median_streak_current_season_45 REAL DEFAULT 0,
            max_streak_all_seasons_45 INTEGER DEFAULT 0,
            median_streak_all_seasons_45 REAL DEFAULT 0,
            max_streak_2022_25 INTEGER DEFAULT 0,
            max_streak_2023_25 INTEGER DEFAULT 0,
            max_streak_2024_25 INTEGER DEFAULT 0,
            max_streak_2025_25 INTEGER DEFAULT 0,
            max_streak_2026_25 INTEGER DEFAULT 0,
            max_streak_2022_35 INTEGER DEFAULT 0,
            max_streak_2023_35 INTEGER DEFAULT 0,
            max_streak_2024_35 INTEGER DEFAULT 0,
            max_streak_2025_35 INTEGER DEFAULT 0,
            max_streak_2026_35 INTEGER DEFAULT 0,
            max_streak_2022_45 INTEGER DEFAULT 0,
            max_streak_2023_45 INTEGER DEFAULT 0,
            max_streak_2024_45 INTEGER DEFAULT 0,
            max_streak_2025_45 INTEGER DEFAULT 0,
            max_streak_2026_45 INTEGER DEFAULT 0,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Add new columns if they don't exist (for existing tables)
    columns_to_add = [
        ("min_streak_current_season", "INTEGER DEFAULT 0"),
        ("median_streak_current_season", "REAL DEFAULT 0"),
        ("min_streak_all_seasons", "INTEGER DEFAULT 0"),
        ("median_streak_all_seasons", "REAL DEFAULT 0"),
        ("max_streak_current_season_35", "INTEGER DEFAULT 0"),
        ("median_streak_current_season_35", "REAL DEFAULT 0"),
        ("max_streak_all_seasons_35", "INTEGER DEFAULT 0"),
        ("median_streak_all_seasons_35", "REAL DEFAULT 0"),
        ("max_streak_current_season_45", "INTEGER DEFAULT 0"),
        ("median_streak_current_season_45", "REAL DEFAULT 0"),
        ("max_streak_all_seasons_45", "INTEGER DEFAULT 0"),
        ("median_streak_all_seasons_45", "REAL DEFAULT 0"),
        ("max_streak_2026_25", "INTEGER DEFAULT 0"),
        ("max_streak_2026_35", "INTEGER DEFAULT 0"),
        ("max_streak_2026_45", "INTEGER DEFAULT 0"),
    ]
    
    for col_name, col_type in columns_to_add:
        try:
            conn.execute(f"ALTER TABLE leagues ADD COLUMN {col_name} {col_type}")
        except:
            pass  # Column already exists
    
    conn.execute("CREATE INDEX IF NOT EXISTS idx_leagues_league_id ON leagues(league_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_leagues_country ON leagues(country_name)")
    conn.commit()
    
    # Get all distinct leagues from games table
    leagues = conn.execute("""
        SELECT DISTINCT 
            league_id,
            league_name,
            country_name,
            country_code
        FROM games
        WHERE league_id IS NOT NULL
        ORDER BY league_id
    """).fetchall()
    
    print(f"Found {len(leagues)} leagues to process")
    print()
    
    current_season = 2022  # Season year for current_season stats
    
    for league in leagues:
        league_id = league[0]
        league_name = league[1] or "Unknown"
        country_name = league[2] or "Unknown"
        country_code = league[3]
        
        print(f"Processing League {league_id}: {league_name} ({country_name})")
        
        # Get all games for all seasons, ordered by date (with all over values)
        all_seasons_games = conn.execute("""
            SELECT id, date, over_25, over_35, over_45, season_year
            FROM games
            WHERE league_id = ?
            AND status IN (7, 8, 9, 10)  -- Finished games only
            ORDER BY date ASC
        """, (league_id,)).fetchall()
        
        # Calculate streak stats for each season (2022-2026) and all seasons
        seasons = [2022, 2023, 2024, 2025, 2026]
        
        # Initialize dictionaries to store max streaks per season
        max_streaks_25 = {}
        max_streaks_35 = {}
        max_streaks_45 = {}
        
        # Calculate for each season
        for season in seasons:
            season_games = [row for row in all_seasons_games if row[5] == season]
            
            if season_games:
                # 2.5
                games_list = [{'over_25': row[2]} for row in season_games]
                max_streak, _, _, _ = calculate_streak_stats(games_list, '25')
                max_streaks_25[season] = max_streak
                
                # 3.5
                games_list = [{'over_35': row[3]} for row in season_games]
                max_streak, _, _, _ = calculate_streak_stats(games_list, '35')
                max_streaks_35[season] = max_streak
                
                # 4.5
                games_list = [{'over_45': row[4]} for row in season_games]
                max_streak, _, _, _ = calculate_streak_stats(games_list, '45')
                max_streaks_45[season] = max_streak
            else:
                max_streaks_25[season] = 0
                max_streaks_35[season] = 0
                max_streaks_45[season] = 0
        
        # Calculate streak stats for season 2022 (for current_season columns)
        season_2022_games = [row for row in all_seasons_games if row[5] == 2022]
        
        # Calculate streak stats for 2.5
        max_2022_25 = max_streaks_25.get(2022, 0)
        min_2022_25 = 0
        median_2022_25 = 0.0
        max_all_25 = 0
        min_all_25 = 0
        median_all_25 = 0.0
        
        # Calculate max streak over ALL seasons (the largest streak across all seasons combined)
        if all_seasons_games:
            games_list = [{'over_25': row[2]} for row in all_seasons_games]
            max_all_25, min_all_25, median_all_25, _ = calculate_streak_stats(games_list, '25')
            # Also check if any individual season has a larger max streak
            # (in case seasons are separated and we want the absolute maximum)
            max_from_seasons = max(max_streaks_25.values()) if max_streaks_25 else 0
            # Take the maximum of: streak across all seasons vs max from individual seasons
            max_all_25 = max(max_all_25, max_from_seasons)
        
        if season_2022_games:
            games_list = [{'over_25': row[2]} for row in season_2022_games]
            _, min_2022_25, median_2022_25, _ = calculate_streak_stats(games_list, '25')
        
        # Calculate streak stats for 3.5
        max_2022_35 = max_streaks_35.get(2022, 0)
        median_2022_35 = 0.0
        max_all_35 = 0
        median_all_35 = 0.0
        
        # Calculate max streak over ALL seasons (the largest streak across all seasons combined)
        if all_seasons_games:
            games_list = [{'over_35': row[3]} for row in all_seasons_games]
            max_all_35, _, median_all_35, _ = calculate_streak_stats(games_list, '35')
            # Also check if any individual season has a larger max streak
            max_from_seasons = max(max_streaks_35.values()) if max_streaks_35 else 0
            # Take the maximum of: streak across all seasons vs max from individual seasons
            max_all_35 = max(max_all_35, max_from_seasons)
        
        if season_2022_games:
            games_list = [{'over_35': row[3]} for row in season_2022_games]
            _, _, median_2022_35, _ = calculate_streak_stats(games_list, '35')
        
        # Calculate streak stats for 4.5
        max_2022_45 = max_streaks_45.get(2022, 0)
        median_2022_45 = 0.0
        max_all_45 = 0
        median_all_45 = 0.0
        
        # Calculate max streak over ALL seasons (the largest streak across all seasons combined)
        if all_seasons_games:
            games_list = [{'over_45': row[4]} for row in all_seasons_games]
            max_all_45, _, median_all_45, _ = calculate_streak_stats(games_list, '45')
            # Also check if any individual season has a larger max streak
            max_from_seasons = max(max_streaks_45.values()) if max_streaks_45 else 0
            # Take the maximum of: streak across all seasons vs max from individual seasons
            max_all_45 = max(max_all_45, max_from_seasons)
        
        if season_2022_games:
            games_list = [{'over_45': row[4]} for row in season_2022_games]
            _, _, median_2022_45, _ = calculate_streak_stats(games_list, '45')
        
        print(f"  2.5 - Season 2022: Max={max_2022_25}, Min={min_2022_25}, Median={median_2022_25:.1f}")
        print(f"  2.5 - All Seasons: Max={max_all_25}, Min={min_all_25}, Median={median_all_25:.1f}")
        print(f"  2.5 - Per Season: 2022={max_streaks_25.get(2022, 0)}, 2023={max_streaks_25.get(2023, 0)}, 2024={max_streaks_25.get(2024, 0)}, 2025={max_streaks_25.get(2025, 0)}, 2026={max_streaks_25.get(2026, 0)}")
        print(f"  3.5 - Season 2022: Max={max_2022_35}, Median={median_2022_35:.1f}")
        print(f"  3.5 - All Seasons: Max={max_all_35}, Median={median_all_35:.1f}")
        print(f"  3.5 - Per Season: 2022={max_streaks_35.get(2022, 0)}, 2023={max_streaks_35.get(2023, 0)}, 2024={max_streaks_35.get(2024, 0)}, 2025={max_streaks_35.get(2025, 0)}, 2026={max_streaks_35.get(2026, 0)}")
        print(f"  4.5 - Season 2022: Max={max_2022_45}, Median={median_2022_45:.1f}")
        print(f"  4.5 - All Seasons: Max={max_all_45}, Median={median_all_45:.1f}")
        print(f"  4.5 - Per Season: 2022={max_streaks_45.get(2022, 0)}, 2023={max_streaks_45.get(2023, 0)}, 2024={max_streaks_45.get(2024, 0)}, 2025={max_streaks_45.get(2025, 0)}, 2026={max_streaks_45.get(2026, 0)}")
        
        # Insert or update in leagues table
        conn.execute("""
            INSERT OR REPLACE INTO leagues 
            (league_id, league_name, country_name, country_code, 
             max_streak_current_season, min_streak_current_season, median_streak_current_season,
             max_streak_all_seasons, min_streak_all_seasons, median_streak_all_seasons,
             max_streak_current_season_35, median_streak_current_season_35,
             max_streak_all_seasons_35, median_streak_all_seasons_35,
             max_streak_current_season_45, median_streak_current_season_45,
             max_streak_all_seasons_45, median_streak_all_seasons_45,
             max_streak_2022_25, max_streak_2023_25, max_streak_2024_25, max_streak_2025_25, max_streak_2026_25,
             max_streak_2022_35, max_streak_2023_35, max_streak_2024_35, max_streak_2025_35, max_streak_2026_35,
             max_streak_2022_45, max_streak_2023_45, max_streak_2024_45, max_streak_2025_45, max_streak_2026_45,
             updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (league_id, league_name, country_name, country_code,
              max_2022_25, min_2022_25, median_2022_25,
              max_all_25, min_all_25, median_all_25,
              max_2022_35, median_2022_35,
              max_all_35, median_all_35,
              max_2022_45, median_2022_45,
              max_all_45, median_all_45,
              max_streaks_25.get(2022, 0), max_streaks_25.get(2023, 0), max_streaks_25.get(2024, 0), max_streaks_25.get(2025, 0), max_streaks_25.get(2026, 0),
              max_streaks_35.get(2022, 0), max_streaks_35.get(2023, 0), max_streaks_35.get(2024, 0), max_streaks_35.get(2025, 0), max_streaks_35.get(2026, 0),
              max_streaks_45.get(2022, 0), max_streaks_45.get(2023, 0), max_streaks_45.get(2024, 0), max_streaks_45.get(2025, 0), max_streaks_45.get(2026, 0),
              datetime.now().isoformat()))
        
        print()
    
    conn.commit()
    
    print("=" * 70)
    print("Calculation complete!")
    print("=" * 70)
    
    # Show summary
    summary = conn.execute("""
        SELECT 
            COUNT(*) as total_leagues,
            AVG(max_streak_current_season) as avg_max_2022_25,
            AVG(min_streak_current_season) as avg_min_2022_25,
            AVG(median_streak_current_season) as avg_median_2022_25,
            AVG(max_streak_all_seasons) as avg_max_all_25,
            AVG(min_streak_all_seasons) as avg_min_all_25,
            AVG(median_streak_all_seasons) as avg_median_all_25,
            AVG(max_streak_current_season_35) as avg_max_2022_35,
            AVG(median_streak_current_season_35) as avg_median_2022_35,
            AVG(max_streak_all_seasons_35) as avg_max_all_35,
            AVG(median_streak_all_seasons_35) as avg_median_all_35,
            AVG(max_streak_current_season_45) as avg_max_2022_45,
            AVG(median_streak_current_season_45) as avg_median_2022_45,
            AVG(max_streak_all_seasons_45) as avg_max_all_45,
            AVG(median_streak_all_seasons_45) as avg_median_all_45
        FROM leagues
    """).fetchone()
    
    print(f"\nSummary:")
    print(f"  Total leagues processed: {summary[0]}")
    print(f"  2.5 - Season 2022 - Avg Max: {summary[1]:.2f}, Avg Min: {summary[2]:.2f}, Avg Median: {summary[3]:.2f}")
    print(f"  2.5 - All Seasons - Avg Max: {summary[4]:.2f}, Avg Min: {summary[5]:.2f}, Avg Median: {summary[6]:.2f}")
    print(f"  3.5 - Season 2022 - Avg Max: {summary[7]:.2f}, Avg Median: {summary[8]:.2f}")
    print(f"  3.5 - All Seasons - Avg Max: {summary[9]:.2f}, Avg Median: {summary[10]:.2f}")
    print(f"  4.5 - Season 2022 - Avg Max: {summary[11]:.2f}, Avg Median: {summary[12]:.2f}")
    print(f"  4.5 - All Seasons - Avg Max: {summary[13]:.2f}, Avg Median: {summary[14]:.2f}")

if __name__ == "__main__":
    calculate_league_streaks()
