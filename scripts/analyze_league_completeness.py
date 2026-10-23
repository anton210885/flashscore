"""
Analyze if all games for a selected league and season are loaded in the database.
Compares API data with database data to find missing games.
"""
import sqlite3
import sys
import os
from typing import Dict, List, Set, Optional
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.sstats_client import SStatsClient
from config import config as cfg
from database import DatabaseManager


def get_games_from_api(client: SStatsClient, league_id: int, year: int) -> List[Dict]:
    """Fetch all games for a league and year from API"""
    print(f"[API] Fetching games from API for league {league_id}, year {year}...")
    
    try:
        # Try different parameter combinations
        all_games = []
        
        # Try with year parameter
        params = {"leagueid": league_id, "year": year}
        games = client.get_games(params)
        if games:
            all_games.extend(games)
        
        # Also try without year to get all games for the league
        if not all_games:
            params = {"leagueid": league_id}
            games = client.get_games(params)
            if games:
                all_games.extend(games)
        
        if not all_games:
            print(f"[WARNING] No games found in API for league {league_id}, year {year}")
            return []
        
        # Filter finished games for the specified year
        finished_games = []
        year_int = int(year)
        
        for game in all_games:
            # Check if game is finished (status 7 or has final result)
            status = game.get("status") or game.get("statusName") or 0
            is_finished = False
            
            try:
                status_int = int(status) if status else 0
                # Status 7 = Finished
                if status_int == 7:
                    is_finished = True
            except (ValueError, TypeError):
                # If status can't be converted, check if game has final result
                if game.get("homeResult") is not None and game.get("awayResult") is not None:
                    is_finished = True
            
            if not is_finished:
                continue
            
            # Check if game is from the specified year
            game_date = game.get("date") or game.get("gameDate") or ""
            game_year = None
            
            if game_date:
                try:
                    if "T" in str(game_date):
                        dt = datetime.fromisoformat(str(game_date).replace("Z", "+00:00"))
                        game_year = dt.year
                except:
                    pass
            
            # Also check season.year field
            if game_year is None:
                season = game.get("season")
                if season and isinstance(season, dict):
                    game_year = season.get("year")
            
            # Include if year matches
            if game_year == year_int:
                finished_games.append(game)
        
        print(f"[OK] Found {len(finished_games)} finished games in API for year {year}")
        return finished_games
        
    except Exception as e:
        print(f"[ERROR] Error fetching games from API: {e}")
        import traceback
        traceback.print_exc()
        return []


def get_games_from_db(db_manager: DatabaseManager, league_id: int, year: int) -> Dict[int, Dict]:
    """Get all games for a league and year from database"""
    print(f"[DB] Loading games from database for league {league_id}, year {year}...")
    
    try:
        conn = db_manager.get_connection()
        conn.row_factory = sqlite3.Row
        
        rows = conn.execute("""
            SELECT id, date, home_team_name, away_team_name, 
                   home_ft_result, away_ft_result, status,
                   calculated_xg_home, calculated_xg_away
            FROM games 
            WHERE league_id = ? AND season_year = ?
            ORDER BY date
        """, (league_id, year)).fetchall()
        
        games_dict = {}
        for row in rows:
            games_dict[row['id']] = {
                'id': row['id'],
                'date': row['date'],
                'home': row['home_team_name'],
                'away': row['away_team_name'],
                'result': f"{row['home_ft_result'] or 0}-{row['away_ft_result'] or 0}",
                'status': row['status'],
                'has_xg': row['calculated_xg_home'] is not None and row['calculated_xg_away'] is not None
            }
        
        print(f"[OK] Found {len(games_dict)} games in database")
        return games_dict
        
    except Exception as e:
        print(f"[ERROR] Error loading games from database: {e}")
        import traceback
        traceback.print_exc()
        return {}


def analyze_league_completeness(league_id: int, year: int):
    """Analyze completeness of games for a league and season"""
    print(f"\n{'='*60}")
    print(f"Analyzing League Completeness")
    print(f"{'='*60}")
    print(f"League ID: {league_id}")
    print(f"Year: {year}")
    print(f"{'='*60}\n")
    
    # Initialize services
    client = SStatsClient(base_url=cfg.BASE_URL, api_key=getattr(cfg, 'API_KEY', None))
    db_manager = DatabaseManager("data/flashscore.db")
    
    # Get games from API
    api_games = get_games_from_api(client, league_id, year)
    api_game_ids = {game.get('id') for game in api_games if game.get('id')}
    
    # Get games from database
    db_games = get_games_from_db(db_manager, league_id, year)
    db_game_ids = set(db_games.keys())
    
    # Find missing games
    missing_ids = api_game_ids - db_game_ids
    missing_games = [g for g in api_games if g.get('id') in missing_ids]
    
    # Find games with missing xG data
    games_without_xg = [g for g in db_games.values() if not g['has_xg']]
    
    # Statistics
    print(f"\n{'='*60}")
    print(f"Analysis Results")
    print(f"{'='*60}")
    print(f"Games in API:        {len(api_game_ids)}")
    print(f"Games in Database:   {len(db_game_ids)}")
    print(f"Missing Games:       {len(missing_ids)}")
    print(f"Games without xG:    {len(games_without_xg)}")
    print(f"Completeness:        {len(db_game_ids) / len(api_game_ids) * 100:.1f}%" if api_game_ids else "N/A")
    print(f"{'='*60}\n")
    
    # Show missing games
    if missing_games:
        print(f"[MISSING] Missing Games ({len(missing_games)}):")
        print(f"{'-'*60}")
        for game in sorted(missing_games[:20], key=lambda x: x.get('date', '')):  # Show first 20
            game_id = game.get('id', 'N/A')
            date = game.get('date', 'N/A')
            home = game.get('homeTeam', {}).get('name', 'N/A') if isinstance(game.get('homeTeam'), dict) else game.get('homeTeam', 'N/A')
            away = game.get('awayTeam', {}).get('name', 'N/A') if isinstance(game.get('awayTeam'), dict) else game.get('awayTeam', 'N/A')
            print(f"  ID: {game_id:8} | {date[:10]:10} | {home} vs {away}")
        
        if len(missing_games) > 20:
            print(f"  ... and {len(missing_games) - 20} more games")
        print()
    
    # Show games without xG
    if games_without_xg:
        print(f"[WARNING] Games without xG data ({len(games_without_xg)}):")
        print(f"{'-'*60}")
        for game in sorted(games_without_xg[:20], key=lambda x: x.get('date', '')):  # Show first 20
            print(f"  ID: {game['id']:8} | {game['date'][:10]:10} | {game['home']} vs {game['away']} | {game['result']}")
        
        if len(games_without_xg) > 20:
            print(f"  ... and {len(games_without_xg) - 20} more games")
        print()
    
    # Summary
    if not missing_ids and not games_without_xg:
        print("[OK] All games are loaded and have xG data!")
    elif not missing_ids:
        print(f"[OK] All games are loaded, but {len(games_without_xg)} games are missing xG data.")
    else:
        print(f"[WARNING] {len(missing_ids)} games are missing from the database.")
    
    return {
        'api_count': len(api_game_ids),
        'db_count': len(db_game_ids),
        'missing_count': len(missing_ids),
        'missing_games': missing_games,
        'games_without_xg': games_without_xg,
        'completeness': len(db_game_ids) / len(api_game_ids) * 100 if api_game_ids else 0
    }


def analyze_all_seasons_for_league(league_id: int):
    """Analyze all seasons for a league in the database"""
    print(f"\n{'='*60}")
    print(f"Analyzing All Seasons for League {league_id}")
    print(f"{'='*60}\n")
    
    db_manager = DatabaseManager("data/flashscore.db")
    
    try:
        conn = db_manager.get_connection()
        conn.row_factory = sqlite3.Row
        
        # Get all seasons for this league
        rows = conn.execute("""
            SELECT DISTINCT season_year, COUNT(*) as game_count,
                   SUM(CASE WHEN calculated_xg_home IS NOT NULL AND calculated_xg_away IS NOT NULL THEN 1 ELSE 0 END) as xg_count
            FROM games 
            WHERE league_id = ?
            GROUP BY season_year
            ORDER BY season_year DESC
        """, (league_id,)).fetchall()
        
        if not rows:
            print(f"[WARNING] No games found in database for league {league_id}")
            return
        
        print(f"Seasons found in database:")
        print(f"{'-'*60}")
        print(f"{'Season':<10} {'Games':<10} {'With xG':<10} {'xG %':<10}")
        print(f"{'-'*60}")
        
        total_games = 0
        total_with_xg = 0
        
        for row in rows:
            season = row['season_year']
            games = row['game_count']
            xg_count = row['xg_count']
            xg_percent = (xg_count / games * 100) if games > 0 else 0
            total_games += games
            total_with_xg += xg_count
            
            print(f"{season:<10} {games:<10} {xg_count:<10} {xg_percent:.1f}%")
        
        print(f"{'-'*60}")
        overall_xg_percent = (total_with_xg / total_games * 100) if total_games > 0 else 0
        print(f"{'TOTAL':<10} {total_games:<10} {total_with_xg:<10} {overall_xg_percent:.1f}%")
        print(f"{'='*60}\n")
        
    except Exception as e:
        print(f"[ERROR] Error analyzing seasons: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python analyze_league_completeness.py <league_id> [year]")
        print("\nExamples:")
        print("  python analyze_league_completeness.py 135        # Analyze all seasons for Serie A")
        print("  python analyze_league_completeness.py 135 2024   # Analyze Serie A 2024")
        print("  python analyze_league_completeness.py 144 2024    # Belgium Jupiler Pro League 2024")
        return
    
    try:
        league_id = int(sys.argv[1])
        
        if len(sys.argv) >= 3:
            # Analyze specific year
            year = int(sys.argv[2])
            analyze_league_completeness(league_id, year)
        else:
            # Analyze all seasons
            analyze_all_seasons_for_league(league_id)
            
    except ValueError:
        print("[ERROR] Error: league_id and year must be integers")
        return


if __name__ == "__main__":
    main()

