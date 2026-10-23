# Game Details View

Die `game_details_view` kombiniert alle wichtigen Daten für jedes Spiel in einer einzigen View.

## Verfügbare Spalten

### Basis-Informationen
- `game_id` - Spiel-ID
- `date` - Datum
- `country_name`, `country_code` - Land
- `league_name`, `league_id` - Liga
- `season_year` - Saisonjahr
- `home_team_name`, `away_team_name` - Team-Namen
- `home_team_id`, `away_team_id` - Team-IDs

### Ergebnisse
- `home_ft_result`, `away_ft_result` - Endergebnis
- `total_goals` - Gesamttore

### xG-Daten
- `xg_home`, `xg_away` - xG aus games Tabelle (calculated/expected)
- `xg_glicko_home`, `xg_glicko_away` - xG-Vorhersagen von Glicko

### Glicko-Ratings
- `home_rating`, `away_rating` - Team-Ratings
- `home_rd`, `away_rd` - Rating Deviation
- `home_volatility`, `away_volatility` - Volatilität
- `home_win_probability`, `away_win_probability`, `draw_probability` - Win-Wahrscheinlichkeiten

### Odds
- `odd_home`, `odd_draw`, `odd_away` - Match Winner Odds
- `odd_over_25`, `odd_under_25` - Over/Under 2.5 Odds
- `odd_over_35`, `odd_under_35` - Over/Under 3.5 Odds
- `odd_over_45`, `odd_under_45` - Over/Under 4.5 Odds

### Profit-Daten (Home Team)
- `profit_home_win`, `profit_home_draw`, `profit_home_lose` - Profit für Match Winner
- `profit_home_over_25`, `profit_home_under_25` - Profit für Over/Under 2.5
- `profit_home_over_35`, `profit_home_under_35` - Profit für Over/Under 3.5
- `profit_home_over_45`, `profit_home_under_45` - Profit für Over/Under 4.5

### Chance (Wahrscheinlichkeit)
- `chance_home_win`, `chance_home_draw`, `chance_home_lose` - Win-Wahrscheinlichkeit (win_count / games_count)
- `chance_home_over_25`, `chance_home_under_25` - Wahrscheinlichkeit für Over/Under 2.5
- `chance_home_over_35`, `chance_home_under_35` - Wahrscheinlichkeit für Over/Under 3.5
- `chance_home_over_45`, `chance_home_under_45` - Wahrscheinlichkeit für Over/Under 4.5

### Statistiken
- `games_count_home_win` - Anzahl Spiele für Win-Statistik
- `win_count_home_win` - Anzahl Gewinne

## Verwendung

### Alle Spiele anzeigen:
```sql
SELECT * FROM game_details_view
ORDER BY date DESC
LIMIT 10;
```

### Spiele mit hohem Profit filtern:
```sql
SELECT game_id, home_team_name, away_team_name,
       profit_home_win, chance_home_win, odd_home
FROM game_details_view
WHERE profit_home_win > 5
ORDER BY profit_home_win DESC;
```

### Spiele mit xG-Daten:
```sql
SELECT * FROM game_details_view
WHERE xg_home IS NOT NULL 
  AND xg_away IS NOT NULL
ORDER BY date DESC;
```

### Spiele mit Glicko-Ratings:
```sql
SELECT * FROM game_details_view
WHERE home_rating IS NOT NULL
  AND away_rating IS NOT NULL
ORDER BY date DESC;
```

### Kombinierte Analyse:
```sql
SELECT 
    game_id,
    home_team_name,
    away_team_name,
    home_ft_result || '-' || away_ft_result AS result,
    xg_home,
    xg_away,
    home_rating,
    away_rating,
    odd_home,
    profit_home_win,
    chance_home_win,
    CASE 
        WHEN profit_home_win > 0 AND chance_home_win > 0.5 THEN 'Good Bet'
        WHEN profit_home_win > 0 THEN 'Positive'
        ELSE 'Negative'
    END AS bet_recommendation
FROM game_details_view
WHERE xg_home IS NOT NULL
ORDER BY profit_home_win DESC;
```























