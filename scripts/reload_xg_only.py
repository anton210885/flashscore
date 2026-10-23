"""Reload only xG data for existing games"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import DatabaseManager
from config import config as cfg
from api.sstats_client import SStatsClient
import sqlite3


def reload_xg_only():
    """Reload xG data for games that are missing it"""
    print("=" * 70)
    print("Reloading xG Data for Existing Games")
    print("=" * 70)
    print()
    
    db_path = "data/flashscore.db"
    db_manager = DatabaseManager(db_path)
    client = SStatsClient(base_url=cfg.BASE_URL, api_key=getattr(cfg, 'API_KEY', None))
    
    conn = db_manager.get_connection()
    conn.row_factory = sqlite3.Row
    
    # Find games without xG
    games_without_xg = conn.execute("""
        SELECT id FROM games 
        WHERE calculated_xg_home IS NULL OR calculated_xg_away IS NULL
        ORDER BY date DESC
    """).fetchall()
    
    total = len(games_without_xg)
    print(f"Found {total} games without xG data")
    print()
    
    if total == 0:
        print("All games already have xG data!")
        db_manager.close()
        return
    
    print(f"This will reload xG data for {total} games.")
    print(f"Estimated time: ~{total // 60} minutes (1 second per game)")
    print()
    
    response = input("Continue? (yes/no): ").strip().lower()
    if not response == 'yes':
        print("Cancelled.")
        db_manager.close()
        return
    
    # Reload xG data
    updated = 0
    errors = 0
    no_stats = 0
    last_request_time = 0
    rate_limit = 1.0
    
    print("\n" + "=" * 70)
    print("Reloading xG data...")
    print("=" * 70)
    
    for idx, row in enumerate(games_without_xg):
        game_id = row[0]
        
        # Rate limiting
        elapsed = time.time() - last_request_time
        if elapsed < rate_limit:
            time.sleep(rate_limit - elapsed)
        last_request_time = time.time()
        
        try:
            # Fetch game details
            game_data = client.get_game(game_id)
            
            # Handle API response format: {"status": "OK", "data": {"game": {...}, "statistics": {...}}}
            if isinstance(game_data, dict):
                if "data" in game_data and isinstance(game_data["data"], dict):
                    # API returns {"data": {"game": {...}, "statistics": {...}}}
                    data = game_data["data"]
                    stats = data.get("statistics", {})
                elif "statistics" in game_data:
                    stats = game_data["statistics"]
                elif "game" in game_data:
                    stats = game_data.get("statistics", game_data["game"].get("statistics", {}))
                else:
                    stats = game_data.get("statistics", {})
            else:
                stats = {}
            
            # Extract xG
            calculated_xg_home = stats.get("calculatedXgHome")
            calculated_xg_away = stats.get("calculatedXgAway")
            
            if calculated_xg_home is None and calculated_xg_away is None:
                no_stats += 1
                if (idx + 1) % 50 == 0:
                    print(f"Progress: {idx + 1}/{total} (updated: {updated}, no stats: {no_stats}, errors: {errors})")
                continue
            
            # Update database
            conn.execute("""
                UPDATE games 
                SET calculated_xg_home = ?, 
                    calculated_xg_away = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (calculated_xg_home, calculated_xg_away, game_id))
            
            conn.commit()
            updated += 1
            
            if (idx + 1) % 10 == 0:
                print(f"Progress: {idx + 1}/{total} (updated: {updated}, no stats: {no_stats}, errors: {errors})")
        
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "Too Many Requests" in error_msg:
                print(f"\nRate limited at game {game_id}, waiting 10 seconds...")
                time.sleep(10)
                # Retry once
                try:
                    game_data = client.get_game(game_id)
                    if isinstance(game_data, dict):
                        if "data" in game_data:
                            if isinstance(game_data["data"], dict):
                                if "game" in game_data["data"]:
                                    game = game_data["data"]["game"]
                                else:
                                    game = game_data["data"]
                            else:
                                game = game_data["data"]
                        elif "game" in game_data:
                            game = game_data["game"]
                        else:
                            game = game_data
                    
                    stats = game.get("statistics", {})
                    if stats:
                        calculated_xg_home = stats.get("calculatedXgHome")
                        calculated_xg_away = stats.get("calculatedXgAway")
                        if calculated_xg_home is not None or calculated_xg_away is not None:
                            conn.execute("""
                                UPDATE games 
                                SET calculated_xg_home = ?, 
                                    calculated_xg_away = ?,
                                    updated_at = CURRENT_TIMESTAMP
                                WHERE id = ?
                            """, (calculated_xg_home, calculated_xg_away, game_id))
                            conn.commit()
                            updated += 1
                except:
                    errors += 1
            else:
                errors += 1
                if (idx + 1) % 50 == 0:
                    print(f"Error at game {game_id}: {error_msg[:50]}")
    
    # Final statistics
    print("\n" + "=" * 70)
    print("Reload Complete!")
    print("=" * 70)
    print(f"Successfully updated: {updated}")
    print(f"No statistics available: {no_stats}")
    print(f"Errors: {errors}")
    print()
    
    # Check results
    with_xg = conn.execute("""
        SELECT COUNT(*) FROM games 
        WHERE calculated_xg_home IS NOT NULL AND calculated_xg_away IS NOT NULL
    """).fetchone()[0]
    
    total_games = conn.execute("SELECT COUNT(*) FROM games").fetchone()[0]
    
    print("Final Statistics:")
    print(f"  Total Games: {total_games}")
    print(f"  Games with xG: {with_xg}")
    print(f"  Games without xG: {total_games - with_xg}")
    
    if no_stats > 0:
        print(f"\n  Note: {no_stats} games don't have xG data available in the API.")
        print(f"  This is normal for some leagues or older games.")
    
    db_manager.close()
    print("\nDone!")


if __name__ == "__main__":
    reload_xg_only()

