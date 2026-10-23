"""Script to query and retrieve data from the database"""
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import DatabaseManager
import sqlite3


def print_separator():
    """Print a separator line"""
    print("=" * 70)


def query_games_by_league(db_manager, league_id, year=None):
    """Query games by league and optionally year"""
    print_separator()
    if year:
        print(f"Games for League {league_id}, Year {year}:")
    else:
        print(f"Games for League {league_id} (all years):")
    print_separator()
    
    games = db_manager.get_games_by_league(league_id, year)
    
    if not games:
        print("No games found.")
        return
    
    print(f"\nTotal games: {len(games)}\n")
    print(f"{'Date':<12} {'Home Team':<25} {'Away Team':<25} {'Score':<10} {'xG Home':<10} {'xG Away':<10}")
    print("-" * 100)
    
    for game in games[:20]:  # Show first 20
        date = game.get('date', '')[:10] if game.get('date') else 'N/A'
        home = game.get('home_team_name', 'N/A')[:24]
        away = game.get('away_team_name', 'N/A')[:24]
        score = f"{game.get('home_ft_result', 0)}-{game.get('away_ft_result', 0)}"
        xg_h = game.get('calculated_xg_home', 'N/A')
        xg_a = game.get('calculated_xg_away', 'N/A')
        
        if xg_h is not None:
            xg_h = f"{xg_h:.2f}"
        if xg_a is not None:
            xg_a = f"{xg_a:.2f}"
        
        print(f"{date:<12} {home:<25} {away:<25} {score:<10} {xg_h:<10} {xg_a:<10}")
    
    if len(games) > 20:
        print(f"\n... and {len(games) - 20} more games")


def query_statistics(db_manager):
    """Show database statistics"""
    print_separator()
    print("Database Statistics:")
    print_separator()
    
    size_info = db_manager.get_database_size()
    print(f"Database Size: {size_info['file_size_mb']} MB")
    print(f"Total Games: {size_info['games']}")
    print(f"Games with Statistics: {size_info['statistics']}")
    print(f"Total Events: {size_info['events']}")
    print(f"Average Size per Game: {size_info['avg_size_per_game_mb']} MB")
    
    # Games by league
    conn = db_manager.get_connection()
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT league_id, league_name, season_year, COUNT(*) as count
        FROM games
        GROUP BY league_id, season_year
        ORDER BY league_id, season_year DESC
    """).fetchall()
    
    if rows:
        print("\nGames by League and Year:")
        print("-" * 70)
        print(f"{'League ID':<12} {'League Name':<30} {'Year':<8} {'Count':<8}")
        print("-" * 70)
        for row in rows:
            print(f"{row['league_id']:<12} {row['league_name']:<30} {row['season_year']:<8} {row['count']:<8}")


def query_custom_sql(db_manager, sql_query):
    """Execute custom SQL query"""
    print_separator()
    print("Custom SQL Query Result:")
    print_separator()
    print(f"Query: {sql_query}\n")
    
    try:
        conn = db_manager.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(sql_query)
        rows = cursor.fetchall()
        
        if not rows:
            print("No results found.")
            return
        
        # Get column names
        columns = [description[0] for description in cursor.description]
        
        # Print header
        header = " | ".join([f"{col:<20}" for col in columns])
        print(header)
        print("-" * len(header))
        
        # Print rows (limit to 50)
        for row in rows[:50]:
            values = [str(row[col])[:20] if row[col] is not None else 'NULL' for col in columns]
            print(" | ".join([f"{val:<20}" for val in values]))
        
        if len(rows) > 50:
            print(f"\n... and {len(rows) - 50} more rows")
        
    except Exception as e:
        print(f"Error executing query: {e}")


def main():
    """Main function"""
    db_path = "data/flashscore.db"
    
    print("=" * 70)
    print("Database Query Tool")
    print("=" * 70)
    print(f"\nDatabase Location: {Path(db_path).absolute()}")
    print()
    
    # Check if database exists
    if not Path(db_path).exists():
        print(f"ERROR: Database not found at {db_path}")
        print("Please load some games first using the Database Tab or load scripts.")
        return
    
    # Initialize database manager
    db_manager = DatabaseManager(db_path)
    
    # Show menu
    while True:
        print("\n" + "=" * 70)
        print("Options:")
        print("1. Show database statistics")
        print("2. Query games by league")
        print("3. Query games with xG data")
        print("4. Query games by date range")
        print("5. Query Over/Under statistics")
        print("6. Execute custom SQL query")
        print("7. Exit")
        print("=" * 70)
        
        choice = input("\nEnter your choice (1-7): ").strip()
        
        if choice == "1":
            query_statistics(db_manager)
        
        elif choice == "2":
            league_id = input("Enter League ID (e.g., 188 for A-League): ").strip()
            year = input("Enter Year (or press Enter for all years): ").strip()
            year = int(year) if year else None
            try:
                query_games_by_league(db_manager, int(league_id), year)
            except ValueError:
                print("Invalid League ID or Year")
        
        elif choice == "3":
            print_separator()
            print("Games with xG Data:")
            print_separator()
            conn = db_manager.get_connection()
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT g.id, g.date, g.home_team_name, g.away_team_name, 
                       g.home_ft_result, g.away_ft_result,
                       g.calculated_xg_home, g.calculated_xg_away,
                       g.league_name, g.season_year
                FROM games g
                WHERE g.calculated_xg_home IS NOT NULL 
                  AND g.calculated_xg_away IS NOT NULL
                ORDER BY g.date DESC
                LIMIT 20
            """).fetchall()
            
            if rows:
                print(f"{'Date':<12} {'Home':<20} {'Away':<20} {'Score':<8} {'xG':<15}")
                print("-" * 80)
                for row in rows:
                    date = row['date'][:10] if row['date'] else 'N/A'
                    score = f"{row['home_ft_result']}-{row['away_ft_result']}"
                    xg = f"{row['calculated_xg_home']:.2f}-{row['calculated_xg_away']:.2f}"
                    print(f"{date:<12} {row['home_team_name'][:19]:<20} {row['away_team_name'][:19]:<20} {score:<8} {xg:<15}")
            else:
                print("No games with xG data found.")
        
        elif choice == "4":
            start_date = input("Enter start date (YYYY-MM-DD): ").strip()
            end_date = input("Enter end date (YYYY-MM-DD): ").strip()
            query_custom_sql(db_manager, f"""
                SELECT date, home_team_name, away_team_name, 
                       home_ft_result, away_ft_result, league_name
                FROM games
                WHERE date >= '{start_date}' AND date <= '{end_date}'
                ORDER BY date DESC
                LIMIT 50
            """)
        
        elif choice == "5":
            print_separator()
            print("Over/Under Statistics by League:")
            print_separator()
            conn = db_manager.get_connection()
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT league_id, league_name, season_year,
                       COUNT(*) as total_games,
                       SUM(over_25) as over_25_count,
                       ROUND(SUM(over_25) * 100.0 / COUNT(*), 2) as over_25_pct,
                       SUM(over_35) as over_35_count,
                       ROUND(SUM(over_35) * 100.0 / COUNT(*), 2) as over_35_pct
                FROM games
                GROUP BY league_id, season_year
                ORDER BY league_id, season_year DESC
            """).fetchall()
            
            if rows:
                print(f"{'League':<30} {'Year':<8} {'Games':<8} {'Over 2.5':<12} {'Over 3.5':<12}")
                print("-" * 80)
                for row in rows:
                    league = f"{row['league_name']} (ID: {row['league_id']})"
                    print(f"{league[:29]:<30} {row['season_year']:<8} {row['total_games']:<8} "
                          f"{row['over_25_pct']}% ({row['over_25_count']}){'':<4} "
                          f"{row['over_35_pct']}% ({row['over_35_count']})")
            else:
                print("No data found.")
        
        elif choice == "6":
            print("\nEnter SQL query (or 'back' to return to menu):")
            print("Example: SELECT * FROM games WHERE league_id = 188 LIMIT 10")
            sql = input("SQL: ").strip()
            if sql.lower() != 'back':
                query_custom_sql(db_manager, sql)
        
        elif choice == "7":
            print("\nExiting...")
            break
        
        else:
            print("Invalid choice. Please try again.")
    
    db_manager.close()


if __name__ == "__main__":
    main()























