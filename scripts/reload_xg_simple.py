"""Reload xG data - simple version without confirmation"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import DatabaseManager
from config import config as cfg
from api.sstats_client import SStatsClient
import sqlite3


def reload_xg_simple():
    """Reload xG data using save_game method - no confirmation"""
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
    print(f"Starting reload... (estimated time: ~{total // 60} minutes)")
    print()
    
    if total == 0:
        print("All games already have xG data!")
        db_manager.close()
        return
    
    # Reload xG data using save_game
    updated = 0
    errors = 0
    no_stats = 0
    last_request_time = 0
    rate_limit = 1.0
    
    print("=" * 70)
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
            
            # Use save_game method which handles the API response structure correctly
            if db_manager.save_game(game_data):
                # Check if xG was actually saved
                check = conn.execute("""
                    SELECT calculated_xg_home, calculated_xg_away 
                    FROM games WHERE id = ?
                """, (game_id,)).fetchone()
                
                if check and (check['calculated_xg_home'] is not None or check['calculated_xg_away'] is not None):
                    updated += 1
                    if updated % 10 == 0 or (idx + 1) % 50 == 0:
                        print(f"Progress: {idx + 1}/{total} (updated: {updated}, no stats: {no_stats}, errors: {errors})")
                else:
                    no_stats += 1
                    if (idx + 1) % 50 == 0:
                        print(f"Progress: {idx + 1}/{total} (updated: {updated}, no stats: {no_stats}, errors: {errors})")
            else:
                errors += 1
                if (idx + 1) % 50 == 0:
                    print(f"Progress: {idx + 1}/{total} (updated: {updated}, no stats: {no_stats}, errors: {errors})")
        
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "Too Many Requests" in error_msg:
                print(f"\nRate limited at game {game_id}, waiting 10 seconds...")
                time.sleep(10)
                # Retry once
                try:
                    game_data = client.get_game(game_id)
                    if db_manager.save_game(game_data):
                        check = conn.execute("""
                            SELECT calculated_xg_home, calculated_xg_away 
                            FROM games WHERE id = ?
                        """, (game_id,)).fetchone()
                        if check and (check['calculated_xg_home'] is not None or check['calculated_xg_away'] is not None):
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
    
    db_manager.close()
    print("\nDone!")


if __name__ == "__main__":
    reload_xg_simple()























