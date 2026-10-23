"""Script to add leagues to the leagues table"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import DatabaseManager
from datetime import datetime

def add_leagues():
    """Add League One (41) and League Two (42) for Great Britain to the leagues table"""
    print("=" * 70)
    print("Adding Leagues to Database")
    print("=" * 70)
    print()
    
    # Initialize database
    db_manager = DatabaseManager("data/flashscore.db")
    conn = db_manager.get_connection()
    
    # Ensure leagues table exists
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
    
    # Leagues to add
    leagues_to_add = [
        {
            "league_id": 41,
            "league_name": "League One",
            "country_name": "Great Britain",
            "country_code": "GB"
        },
        {
            "league_id": 42,
            "league_name": "League Two",
            "country_name": "Great Britain",
            "country_code": "GB"
        },
        {
            "league_id": 210,
            "league_name": "HNL",
            "country_name": "Croatia",
            "country_code": "HR"
        },
        {
            "league_id": 283,
            "league_name": "Liga I",
            "country_name": "Romania",
            "country_code": "RO"
        },
        {
            "league_id": 345,
            "league_name": "Czech Liga",
            "country_name": "Czech-Republic",
            "country_code": "CZ"
        },
        {
            "league_id": 271,
            "league_name": "NB I",
            "country_name": "Hungary",
            "country_code": "HU"
        },
        {
            "league_id": 287,
            "league_name": "Prva Liga",
            "country_name": "Serbia",
            "country_code": "RS"
        },
        {
            "league_id": 186,
            "league_name": "Ligue 1",
            "country_name": "Algeria",
            "country_code": "DZ"
        },
        {
            "league_id": 233,
            "league_name": "Premier League",
            "country_name": "Egypt",
            "country_code": "EG"
        },
        {
            "league_id": 265,
            "league_name": "Primera División",
            "country_name": "Chile",
            "country_code": "CL"
        },
        {
            "league_id": 239,
            "league_name": "Primera A",
            "country_name": "Colombia",
            "country_code": "CO"
        },
        {
            "league_id": 383,
            "league_name": "Ligat Ha'al",
            "country_name": "Israel",
            "country_code": "IL"
        },
        {
            "league_id": 169,
            "league_name": "Super League",
            "country_name": "China",
            "country_code": "CN"
        },
        {
            "league_id": 332,
            "league_name": "Super Liga",
            "country_name": "Slovakia",
            "country_code": "SK"
        },
        {
            "league_id": 373,
            "league_name": "1. SNL",
            "country_name": "Slovenia",
            "country_code": "SI"
        },
        {
            "league_id": 288,
            "league_name": "Premier Soccer League",
            "country_name": "South-Africa",
            "country_code": "ZA"
        },
        {
            "league_id": 268,
            "league_name": "Primera División - Apertura",
            "country_name": "Uruguay",
            "country_code": "UY"
        },
        {
            "league_id": 253,
            "league_name": "Major League Soccer",
            "country_name": "USA",
            "country_code": "US"
        },
        {
            "league_id": 301,
            "league_name": "Pro League",
            "country_name": "United-Arab-Emirates",
            "country_code": "AE"
        },
        {
            "league_id": 303,
            "league_name": "Division 1",
            "country_name": "United-Arab-Emirates",
            "country_code": "AE"
        },
        {
            "league_id": 235,
            "league_name": "Premier League",
            "country_name": "Russia",
            "country_code": "RU"
        },
        {
            "league_id": 236,
            "league_name": "First League",
            "country_name": "Russia",
            "country_code": "RU"
        },
        {
            "league_id": 103,
            "league_name": "Eliteserien",
            "country_name": "Norway",
            "country_code": "NO"
        },
        {
            "league_id": 104,
            "league_name": "1. Division",
            "country_name": "Norway",
            "country_code": "NO"
        },
        {
            "league_id": 113,
            "league_name": "Allsvenskan",
            "country_name": "Sweden",
            "country_code": "SE"
        },
        {
            "league_id": 114,
            "league_name": "Superettan",
            "country_name": "Sweden",
            "country_code": "SE"
        },
        {
            "league_id": 116,
            "league_name": "Premier League",
            "country_name": "Belarus",
            "country_code": "BY"
        },
        {
            "league_id": 117,
            "league_name": "1. Division",
            "country_name": "Belarus",
            "country_code": "BY"
        },
        {
            "league_id": 244,
            "league_name": "Veikkausliiga",
            "country_name": "Finland",
            "country_code": "FI"
        },
        {
            "league_id": 245,
            "league_name": "Ykkönen",
            "country_name": "Finland",
            "country_code": "FI"
        },
        {
            "league_id": 292,
            "league_name": "K League 1",
            "country_name": "South Korea",
            "country_code": "KR"
        },
        {
            "league_id": 293,
            "league_name": "K League 2",
            "country_name": "South Korea",
            "country_code": "KR"
        },
        {
            "league_id": 366,
            "league_name": "1. Deild",
            "country_name": "Faroe-Islands",
            "country_code": "FO"
        },
        {
            "league_id": 367,
            "league_name": "Meistaradeildin",
            "country_name": "Faroe-Islands",
            "country_code": "FO"
        },
        {
            "league_id": 286,
            "league_name": "Super Liga",
            "country_name": "Serbia",
            "country_code": "RS"
        }
    ]
    
    print(f"Adding {len(leagues_to_add)} leagues...")
    print()
    
    for league in leagues_to_add:
        league_id = league["league_id"]
        league_name = league["league_name"]
        country_name = league["country_name"]
        country_code = league["country_code"]
        
        # Check if league already exists
        existing = conn.execute("""
            SELECT league_id FROM leagues WHERE league_id = ?
        """, (league_id,)).fetchone()
        
        if existing:
            print(f"League {league_id} ({league_name}) already exists, updating...")
            # Update existing league
            conn.execute("""
                UPDATE leagues 
                SET league_name = ?, country_name = ?, country_code = ?, updated_at = ?
                WHERE league_id = ?
            """, (league_name, country_name, country_code, datetime.now().isoformat(), league_id))
        else:
            print(f"Adding League {league_id}: {league_name} ({country_name})")
            # Insert new league
            conn.execute("""
                INSERT INTO leagues 
                (league_id, league_name, country_name, country_code, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (league_id, league_name, country_name, country_code, datetime.now().isoformat()))
    
    conn.commit()
    
    print()
    print("=" * 70)
    print("Leagues added successfully!")
    print("=" * 70)
    
    # Show added leagues
    print("\nAdded/Updated Leagues:")
    for league in leagues_to_add:
        result = conn.execute("""
            SELECT league_id, league_name, country_name, country_code
            FROM leagues
            WHERE league_id = ?
        """, (league["league_id"],)).fetchone()
        
        if result:
            print(f"  ID: {result[0]:3d} | {result[1]:30s} | {result[2]:20s} | Code: {result[3]}")

if __name__ == "__main__":
    add_leagues()

