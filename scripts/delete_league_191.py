"""Script to delete all games from League 191 (Brisbane) from the database"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import DatabaseManager

def delete_league_191(confirm=True):
    """Delete all games from League 191"""
    print("=" * 70)
    print("Deleting all games from League 191 (Brisbane)")
    print("=" * 70)
    print()
    
    # Initialize database
    db_manager = DatabaseManager("data/flashscore.db")
    conn = db_manager.get_connection()
    
    # Count games before deletion
    games_count = conn.execute("SELECT COUNT(*) FROM games WHERE league_id = 191").fetchone()[0]
    upcoming_count = conn.execute("SELECT COUNT(*) FROM upcoming_games WHERE league_id = 191").fetchone()[0]
    
    print(f"Games found in 'games' table: {games_count}")
    print(f"Games found in 'upcoming_games' table: {upcoming_count}")
    print()
    
    if games_count == 0 and upcoming_count == 0:
        print("No games found for League 191. Nothing to delete.")
        return
    
    # Confirm deletion
    if confirm:
        try:
            response = input(f"Are you sure you want to delete {games_count + upcoming_count} games? (yes/no): ")
            if response.lower() != 'yes':
                print("Deletion cancelled.")
                return
        except EOFError:
            print("Running in non-interactive mode. Proceeding with deletion...")
            print()
    
    # Delete from games table (CASCADE will delete related data)
    print("Deleting from 'games' table...")
    cursor = conn.execute("DELETE FROM games WHERE league_id = 191")
    games_deleted = cursor.rowcount
    print(f"  Deleted {games_deleted} games from 'games' table")
    
    # Delete from upcoming_games table
    print("Deleting from 'upcoming_games' table...")
    cursor = conn.execute("DELETE FROM upcoming_games WHERE league_id = 191")
    upcoming_deleted = cursor.rowcount
    print(f"  Deleted {upcoming_deleted} games from 'upcoming_games' table")
    
    # Commit changes
    conn.commit()
    
    print()
    print(f"Successfully deleted {games_deleted + upcoming_deleted} games from League 191")
    print("Note: Related data (statistics, events, lineups, etc.) was automatically deleted due to CASCADE constraints.")
    
    # Verify deletion
    remaining_games = conn.execute("SELECT COUNT(*) FROM games WHERE league_id = 191").fetchone()[0]
    remaining_upcoming = conn.execute("SELECT COUNT(*) FROM upcoming_games WHERE league_id = 191").fetchone()[0]
    
    if remaining_games == 0 and remaining_upcoming == 0:
        print("[OK] Verification: All games from League 191 have been deleted.")
    else:
        print(f"[WARNING] {remaining_games + remaining_upcoming} games still remain.")

if __name__ == "__main__":
    # Check for --yes flag to skip confirmation
    confirm = "--yes" not in sys.argv
    delete_league_191(confirm=confirm)

