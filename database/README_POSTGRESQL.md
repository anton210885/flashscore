# PostgreSQL Future Games Tabelle

Diese Anleitung zeigt, wie Sie eine PostgreSQL-Tabelle für zukünftige Spiele mit Quoten erstellen und verwenden.

## 📋 Voraussetzungen

1. PostgreSQL installiert (Version 12 oder höher)
2. Python-Paket `psycopg2` installiert:
   ```bash
   pip install psycopg2-binary
   ```

## 🗄️ Datenbank erstellen

1. PostgreSQL starten und Datenbank erstellen:
   ```sql
   CREATE DATABASE flashscore;
   ```

2. Schema erstellen - Datei ausführen:
   ```bash
   psql -U your_username -d flashscore -f database/postgresql_future_games_schema.sql
   ```
   
   Oder direkt in psql:
   ```sql
   \i database/postgresql_future_games_schema.sql
   ```

## 📊 Tabellenstruktur

Die Tabelle `future_games` enthält:

### Spiele-Informationen:
- `id` - Spiel-ID (Primary Key)
- `date` - Spiel-Datum und Zeit (mit Zeitzone)
- `status` - Status (0=Unknown, 1=Not Started, 2=Scheduled)
- `home_team_name`, `away_team_name` - Team-Namen
- `league_id`, `league_name` - Liga-Informationen
- `country_name` - Land

### Quoten:
- **Match Winner (1X2):**
  - `odd_home` - Quote Heim-Sieg
  - `odd_draw` - Quote Unentschieden
  - `odd_away` - Quote Auswärts-Sieg

- **Over/Under 2.5 Goals:**
  - `odd_over_25` - Quote Über 2.5 Tore
  - `odd_under_25` - Quote Unter 2.5 Tore

- **Opening Odds** (erste Quoten):
  - `odd_home_opening`, `odd_draw_opening`, etc.

### Features:
- ✅ Automatische `updated_at` Aktualisierung via Trigger
- ✅ View `future_games_with_odds` für einfache Abfragen
- ✅ Odds-Bewegung (current - opening) berechnet
- ✅ Indizes für schnelle Queries

## 💻 Python-Verwendung

### Beispiel 1: Einzelnes Spiel speichern

```python
from database.postgresql_connection_example import PostgreSQLFutureGamesManager

# Verbindung aufbauen
conn_params = {
    'host': 'localhost',
    'port': 5432,
    'database': 'flashscore',
    'user': 'your_username',
    'password': 'your_password'
}

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
        'odd_under_25': 1.95,
        'odd_home_opening': 2.60,  # Opening odds (optional)
        'odd_over_25_opening': 1.85
    }
    
    success = pg_manager.save_future_game(game_data, odds_data)
    print(f"Spiel gespeichert: {success}")
```

### Beispiel 2: Spiele abfragen

```python
# Alle zukünftigen Spiele einer Liga
games = pg_manager.get_future_games(league_id=135)

# Spiele nach Land filtern
games = pg_manager.get_future_games(country='Italy')

# Spiele in einem Zeitraum
from datetime import datetime, timedelta
start = datetime.now()
end = datetime.now() + timedelta(days=7)
games = pg_manager.get_future_games(start_date=start, end_date=end)

for game in games:
    print(f"{game['home_team_name']} vs {game['away_team_name']}")
    print(f"Quoten: H={game['odd_home']}, D={game['odd_draw']}, A={game['odd_away']}")
    print(f"Over 2.5: {game['odd_over_25']}")
```

### Beispiel 3: Direkte SQL-Abfragen

```python
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='flashscore',
    user='your_username',
    password='your_password'
)

cursor = conn.cursor()

# Alle zukünftigen Spiele mit Quoten-Bewegung
cursor.execute("""
    SELECT 
        home_team_name, 
        away_team_name, 
        date,
        odd_home,
        odd_draw,
        odd_away,
        odd_home_movement,
        odd_draw_movement,
        odd_away_movement
    FROM future_games_with_odds
    WHERE date >= CURRENT_TIMESTAMP
    ORDER BY date ASC
    LIMIT 10
""")

for row in cursor.fetchall():
    print(row)

conn.close()
```

## 🔍 Nützliche SQL-Queries

### Zukünftige Spiele mit bestem Odd für Over 2.5:
```sql
SELECT 
    home_team_name,
    away_team_name,
    date,
    odd_over_25,
    odd_under_25,
    (odd_over_25 - odd_under_25) as odds_difference
FROM future_games_with_odds
WHERE date >= CURRENT_TIMESTAMP
    AND odd_over_25 IS NOT NULL
ORDER BY odd_over_25 DESC
LIMIT 20;
```

### Quoten-Änderungen (Opening vs. Current):
```sql
SELECT 
    home_team_name,
    away_team_name,
    odd_home_opening as opening_home,
    odd_home as current_home,
    (odd_home - odd_home_opening) as movement
FROM future_games_with_odds
WHERE odd_home_opening IS NOT NULL
    AND date >= CURRENT_TIMESTAMP
ORDER BY ABS(odd_home - odd_home_opening) DESC;
```

### Spiele nach Liga gruppiert:
```sql
SELECT 
    league_name,
    country_name,
    COUNT(*) as total_games,
    AVG(odd_home) as avg_odd_home,
    AVG(odd_draw) as avg_odd_draw,
    AVG(odd_away) as avg_odd_away
FROM future_games_with_odds
WHERE date >= CURRENT_TIMESTAMP
GROUP BY league_name, country_name
ORDER BY total_games DESC;
```

## 🔄 Integration in bestehendes Projekt

Um die PostgreSQL-Tabelle in das bestehende Flashscore-Projekt zu integrieren, können Sie:

1. **Automatisches Speichern:** Beim Laden der "Today's Matches" auch in PostgreSQL speichern
2. **Sync-Service:** Ein separater Service synchronisiert SQLite → PostgreSQL
3. **Doppel-Schreiben:** Bei `save_upcoming_game()` auch PostgreSQL aktualisieren

Beispiel für Integration:
```python
# In main_window.py oder einem Service
from database.postgresql_connection_example import PostgreSQLFutureGamesManager

# Beim Speichern eines zukünftigen Spiels
pg_manager = PostgreSQLFutureGamesManager(conn_params)
pg_manager.save_future_game(game_data, odds_data)
```

## 📝 Hinweise

- Die Tabelle speichert nur zukünftige Spiele (Status 0, 1, 2)
- Bei Update werden Quoten aktualisiert, aber `created_at` bleibt erhalten
- Opening Odds werden nur beim ersten Speichern gesetzt
- Alle Timestamps verwenden `TIMESTAMP WITH TIME ZONE` für korrekte Zeitzonen-Handhabung












