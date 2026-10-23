"""
PostgreSQL Connection Example for Future Games
This script shows how to connect to PostgreSQL and insert/update future games with odds
"""

import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime
from typing import Dict, Any, Optional, List


class PostgreSQLFutureGamesManager:
    """Manager for future games in PostgreSQL database"""
    
    def __init__(self, connection_string: str):
        """
        Initialize PostgreSQL connection
        
        Args:
            connection_string: PostgreSQL connection string
                Example: "postgresql://user:password@localhost:5432/dbname"
                Or use: host, port, database, user, password parameters
        """
        self.conn = None
        if isinstance(connection_string, str) and connection_string.startswith('postgresql://'):
            self.conn = psycopg2.connect(connection_string)
        else:
            # Assume dict with connection parameters
            if isinstance(connection_string, dict):
                self.conn = psycopg2.connect(**connection_string)
            else:
                raise ValueError("Invalid connection_string format")
        
        self.conn.autocommit = False
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            if exc_type:
                self.conn.rollback()
            else:
                self.conn.commit()
            self.conn.close()
    
    def save_future_game(self, game_data: Dict[str, Any], odds_data: Dict[str, Any]) -> bool:
        """
        Save or update a future game with odds
        
        Args:
            game_data: Game information dict with keys:
                - id: Game ID
                - date: Game date (ISO string or datetime)
                - home_team_name, away_team_name: Team names
                - league_id, league_name: League info
                - country_name: Country name
                - season_year: Year
                - status: Status (0, 1, 2)
                - etc.
            odds_data: Odds information dict with keys:
                - odd_home, odd_draw, odd_away
                - odd_over_25, odd_under_25
                - odd_home_opening, etc. (optional)
        
        Returns:
            True if successful
        """
        try:
            cursor = self.conn.cursor()
            
            # Parse date
            date_value = game_data.get('date')
            if isinstance(date_value, str):
                date_value = datetime.fromisoformat(date_value.replace('Z', '+00:00'))
            elif not isinstance(date_value, datetime):
                date_value = datetime.now()
            
            # Prepare SQL with ON CONFLICT for upsert
            sql = """
                INSERT INTO future_games (
                    id, flash_id, date, date_utc, status, status_name,
                    home_team_id, home_team_name, away_team_id, away_team_name,
                    league_id, league_name, country_code, country_name,
                    season_uid, season_year, round_name,
                    venue_name, venue_city, referee_name,
                    odd_home, odd_draw, odd_away,
                    odd_over_25, odd_under_25,
                    odd_over_35, odd_under_35,
                    odd_over_45, odd_under_45,
                    odd_home_opening, odd_draw_opening, odd_away_opening,
                    odd_over_25_opening, odd_under_25_opening,
                    bookmaker_id, bookmaker_name,
                    created_at, updated_at
                ) VALUES (
                    %(id)s, %(flash_id)s, %(date)s, %(date_utc)s, %(status)s, %(status_name)s,
                    %(home_team_id)s, %(home_team_name)s, %(away_team_id)s, %(away_team_name)s,
                    %(league_id)s, %(league_name)s, %(country_code)s, %(country_name)s,
                    %(season_uid)s, %(season_year)s, %(round_name)s,
                    %(venue_name)s, %(venue_city)s, %(referee_name)s,
                    %(odd_home)s, %(odd_draw)s, %(odd_away)s,
                    %(odd_over_25)s, %(odd_under_25)s,
                    %(odd_over_35)s, %(odd_over_35)s,
                    %(odd_over_45)s, %(odd_under_45)s,
                    %(odd_home_opening)s, %(odd_draw_opening)s, %(odd_away_opening)s,
                    %(odd_over_25_opening)s, %(odd_under_25_opening)s,
                    %(bookmaker_id)s, %(bookmaker_name)s,
                    COALESCE((SELECT created_at FROM future_games WHERE id = %(id)s), CURRENT_TIMESTAMP),
                    CURRENT_TIMESTAMP
                )
                ON CONFLICT (id) 
                DO UPDATE SET
                    date = EXCLUDED.date,
                    date_utc = EXCLUDED.date_utc,
                    status = EXCLUDED.status,
                    status_name = EXCLUDED.status_name,
                    home_team_name = EXCLUDED.home_team_name,
                    away_team_name = EXCLUDED.away_team_name,
                    league_id = EXCLUDED.league_id,
                    league_name = EXCLUDED.league_name,
                    country_name = EXCLUDED.country_name,
                    season_year = EXCLUDED.season_year,
                    odd_home = EXCLUDED.odd_home,
                    odd_draw = EXCLUDED.odd_draw,
                    odd_away = EXCLUDED.odd_away,
                    odd_over_25 = EXCLUDED.odd_over_25,
                    odd_under_25 = EXCLUDED.odd_under_25,
                    odd_over_35 = EXCLUDED.odd_over_35,
                    odd_under_35 = EXCLUDED.odd_under_35,
                    odd_over_45 = EXCLUDED.odd_over_45,
                    odd_under_45 = EXCLUDED.odd_under_45,
                    odd_home_opening = COALESCE(EXCLUDED.odd_home_opening, future_games.odd_home_opening),
                    odd_draw_opening = COALESCE(EXCLUDED.odd_draw_opening, future_games.odd_draw_opening),
                    odd_away_opening = COALESCE(EXCLUDED.odd_away_opening, future_games.odd_away_opening),
                    odd_over_25_opening = COALESCE(EXCLUDED.odd_over_25_opening, future_games.odd_over_25_opening),
                    odd_under_25_opening = COALESCE(EXCLUDED.odd_under_25_opening, future_games.odd_under_25_opening),
                    updated_at = CURRENT_TIMESTAMP
            """
            
            values = {
                'id': game_data.get('id'),
                'flash_id': game_data.get('flash_id'),
                'date': date_value,
                'date_utc': game_data.get('date_utc'),
                'status': game_data.get('status', 1),  # Default: Not Started
                'status_name': game_data.get('status_name') or game_data.get('statusName'),
                'home_team_id': game_data.get('home_team_id') or game_data.get('homeTeam', {}).get('id') if isinstance(game_data.get('homeTeam'), dict) else None,
                'home_team_name': game_data.get('home_team_name') or game_data.get('homeTeam', {}).get('name') if isinstance(game_data.get('homeTeam'), dict) else game_data.get('homeTeam'),
                'away_team_id': game_data.get('away_team_id') or game_data.get('awayTeam', {}).get('id') if isinstance(game_data.get('awayTeam'), dict) else None,
                'away_team_name': game_data.get('away_team_name') or game_data.get('awayTeam', {}).get('name') if isinstance(game_data.get('awayTeam'), dict) else game_data.get('awayTeam'),
                'league_id': game_data.get('league_id') or game_data.get('league', {}).get('id') if isinstance(game_data.get('league'), dict) else None,
                'league_name': game_data.get('league_name') or game_data.get('league', {}).get('name') if isinstance(game_data.get('league'), dict) else game_data.get('league'),
                'country_code': game_data.get('country_code') or game_data.get('country', {}).get('code') if isinstance(game_data.get('country'), dict) else None,
                'country_name': game_data.get('country_name') or game_data.get('country', {}).get('name') if isinstance(game_data.get('country'), dict) else game_data.get('country'),
                'season_uid': game_data.get('season_uid') or game_data.get('season', {}).get('uid') if isinstance(game_data.get('season'), dict) else None,
                'season_year': game_data.get('season_year') or game_data.get('season', {}).get('year') if isinstance(game_data.get('season'), dict) else None,
                'round_name': game_data.get('round_name') or game_data.get('roundName'),
                'venue_name': game_data.get('venue_name') or game_data.get('venue', {}).get('name') if isinstance(game_data.get('venue'), dict) else None,
                'venue_city': game_data.get('venue_city') or game_data.get('venue', {}).get('city') if isinstance(game_data.get('venue'), dict) else None,
                'referee_name': game_data.get('referee_name') or game_data.get('refereeName'),
                'odd_home': odds_data.get('odd_home'),
                'odd_draw': odds_data.get('odd_draw'),
                'odd_away': odds_data.get('odd_away'),
                'odd_over_25': odds_data.get('odd_over_25') or odds_data.get('odd_over'),
                'odd_under_25': odds_data.get('odd_under_25') or odds_data.get('odd_under'),
                'odd_over_35': odds_data.get('odd_over_35'),
                'odd_under_35': odds_data.get('odd_under_35'),
                'odd_over_45': odds_data.get('odd_over_45'),
                'odd_under_45': odds_data.get('odd_under_45'),
                'odd_home_opening': odds_data.get('odd_home_opening'),
                'odd_draw_opening': odds_data.get('odd_draw_opening'),
                'odd_away_opening': odds_data.get('odd_away_opening'),
                'odd_over_25_opening': odds_data.get('odd_over_25_opening'),
                'odd_under_25_opening': odds_data.get('odd_under_25_opening'),
                'bookmaker_id': odds_data.get('bookmaker_id', 1),
                'bookmaker_name': odds_data.get('bookmaker_name', 'Default'),
            }
            
            cursor.execute(sql, values)
            self.conn.commit()
            cursor.close()
            return True
            
        except Exception as e:
            print(f"Error saving future game: {e}")
            self.conn.rollback()
            return False
    
    def get_future_games(self, league_id: Optional[int] = None, country: Optional[str] = None, 
                        start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Get future games with filters
        
        Returns:
            List of game dicts
        """
        try:
            cursor = self.conn.cursor()
            sql = "SELECT * FROM future_games_with_odds WHERE 1=1"
            params = []
            
            if league_id:
                sql += " AND league_id = %s"
                params.append(league_id)
            
            if country:
                sql += " AND country_name = %s"
                params.append(country)
            
            if start_date:
                sql += " AND date >= %s"
                params.append(start_date)
            
            if end_date:
                sql += " AND date <= %s"
                params.append(end_date)
            
            sql += " ORDER BY date ASC"
            
            cursor.execute(sql, params)
            columns = [desc[0] for desc in cursor.description]
            results = [dict(zip(columns, row)) for row in cursor.fetchall()]
            cursor.close()
            return results
            
        except Exception as e:
            print(f"Error getting future games: {e}")
            return []


# Example usage
if __name__ == "__main__":
    # Example connection string
    # Option 1: Connection string
    # conn_str = "postgresql://user:password@localhost:5432/flashscore"
    
    # Option 2: Connection dict
    conn_params = {
        'host': 'localhost',
        'port': 5432,
        'database': 'flashscore',
        'user': 'your_username',
        'password': 'your_password'
    }
    
    # Example: Save a future game
    with PostgreSQLFutureGamesManager(conn_params) as pg_manager:
        game_data = {
            'id': 123456,
            'date': '2025-01-15T20:00:00+00:00',
            'home_team_name': 'Team A',
            'away_team_name': 'Team B',
            'league_id': 135,
            'league_name': 'Serie A',
            'country_name': 'Italy',
            'season_year': 2025,
            'status': 1
        }
        
        odds_data = {
            'odd_home': 2.50,
            'odd_draw': 3.20,
            'odd_away': 2.80,
            'odd_over_25': 1.90,
            'odd_under_25': 1.95
        }
        
        pg_manager.save_future_game(game_data, odds_data)












