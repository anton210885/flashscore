"""Test the game_details_view"""
import sqlite3

conn = sqlite3.connect('data/flashscore.db')
conn.row_factory = sqlite3.Row

# Test with a game that has all data
row = conn.execute("""
    SELECT *
    FROM game_details_view 
    WHERE game_id = 1469600 
    LIMIT 1
""").fetchone()

if row:
    print("=" * 70)
    print("Game Details View - Sample Data")
    print("=" * 70)
    print()
    print(f"Game ID: {row['game_id']}")
    print(f"Date: {row['date']}")
    print(f"Country: {row['country_name']}")
    print(f"League: {row['league_name']} ({row['season_year']})")
    print(f"Teams: {row['home_team_name']} vs {row['away_team_name']}")
    print()
    print("Ratings:")
    print(f"  Home: {row['home_rating']}")
    print(f"  Away: {row['away_rating']}")
    print()
    print("xG (Glicko):")
    print(f"  Home: {row['xg_glicko_home']}")
    print(f"  Away: {row['xg_glicko_away']}")
    print()
    print("xG (Calculated):")
    print(f"  Home: {row['xg_home']}")
    print(f"  Away: {row['xg_away']}")
    print()
    print("Result:")
    print(f"  {row['home_ft_result']} - {row['away_ft_result']}")
    print()
    print("Odds:")
    print(f"  Home: {row['odd_home']}")
    print(f"  Draw: {row['odd_draw']}")
    print(f"  Away: {row['odd_away']}")
    print(f"  Over 2.5: {row['odd_over_25']}")
    print(f"  Under 2.5: {row['odd_under_25']}")
    print()
    print("Profits (Home team):")
    print(f"  Win: {row['profit_home_win']}")
    print(f"  Draw: {row['profit_home_draw']}")
    print(f"  Lose: {row['profit_home_lose']}")
    print()
    print("Chances (Home team):")
    print(f"  Win: {row['chance_home_win']}")
    print(f"  Draw: {row['chance_home_draw']}")
    print(f"  Lose: {row['chance_home_lose']}")
else:
    print("No data found for game 1469600")

# Count total rows
total = conn.execute("SELECT COUNT(*) FROM game_details_view").fetchone()[0]
print()
print(f"Total games in view: {total}")

conn.close()

