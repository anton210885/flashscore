# Datenbank-Abfragen - Anleitung

## 📍 Speicherort der Datenbank

Die Datenbank wird gespeichert in:
```
data/flashscore.db
```

Vollständiger Pfad (Windows):
```
C:\Users\anton\OneDrive\Desktop\Flashscore\data\flashscore.db
```

## 🔍 Daten abrufen - Methoden

### 1. Über Python-Code

#### Einfache Abfrage mit DatabaseManager:

```python
from database import DatabaseManager

# Datenbank öffnen
db = DatabaseManager("data/flashscore.db")

# Spiele nach Liga abrufen
games = db.get_games_by_league(league_id=188, year=2025)

# Einzelnes Spiel abrufen
game = db.get_game(game_id=1469600)

# Datenbank-Statistiken
stats = db.get_database_size()
print(f"Total Games: {stats['games']}")
print(f"Database Size: {stats['file_size_mb']} MB")

# Datenbank schließen
db.close()
```

#### Direkte SQL-Abfragen:

```python
from database import DatabaseManager
import sqlite3

db = DatabaseManager("data/flashscore.db")
conn = db.get_connection()
conn.row_factory = sqlite3.Row

# Beispiel: Alle Spiele mit xG-Daten
rows = conn.execute("""
    SELECT * FROM games 
    WHERE calculated_xg_home IS NOT NULL 
      AND calculated_xg_away IS NOT NULL
    ORDER BY date DESC
    LIMIT 10
""").fetchall()

for row in rows:
    print(f"{row['home_team_name']} vs {row['away_team_name']}")
    print(f"xG: {row['calculated_xg_home']} - {row['calculated_xg_away']}")

db.close()
```

### 2. Über SQLite-Befehlszeile

Du kannst die Datenbank auch direkt mit SQLite öffnen:

```bash
# SQLite öffnen
sqlite3 data/flashscore.db

# Dann SQL-Queries ausführen:
SELECT * FROM games LIMIT 10;
SELECT COUNT(*) FROM games;
SELECT league_name, COUNT(*) FROM games GROUP BY league_name;
```

### 3. Über das Query-Skript

Verwende das bereitgestellte Skript:

```bash
python scripts/query_database.py
```

Das Skript bietet ein interaktives Menü mit verschiedenen Abfrage-Optionen.

## 📊 Nützliche SQL-Queries

### Alle Spiele einer Liga:

```sql
SELECT * FROM games 
WHERE league_id = 188 AND season_year = 2025
ORDER BY date DESC;
```

### Spiele mit xG-Daten:

```sql
SELECT date, home_team_name, away_team_name, 
       calculated_xg_home, calculated_xg_away
FROM games
WHERE calculated_xg_home IS NOT NULL 
  AND calculated_xg_away IS NOT NULL
ORDER BY date DESC;
```

### Over/Under Statistiken:

```sql
SELECT 
    league_name,
    season_year,
    COUNT(*) as total_games,
    SUM(over_25) as over_25_count,
    ROUND(SUM(over_25) * 100.0 / COUNT(*), 2) as over_25_percentage
FROM games
WHERE league_id = 188
GROUP BY season_year
ORDER BY season_year DESC;
```

### Spiele mit vollständigen Statistiken:

```sql
SELECT g.*, s.*
FROM games g
JOIN game_statistics s ON g.id = s.game_id
WHERE g.league_id = 188
LIMIT 10;
```

### Events (Tore, Karten) eines Spiels:

```sql
SELECT * FROM game_events
WHERE game_id = 1469600
ORDER BY elapsed;
```

### Spieler-Statistiken:

```sql
SELECT player_name, goals_total, assists, rating
FROM player_statistics
WHERE game_id = 1469600
ORDER BY rating DESC;
```

## 📁 Datenbank-Struktur

### Haupttabellen:

1. **games** - Haupttabelle mit Spielinformationen
2. **game_statistics** - Detaillierte Match-Statistiken
3. **game_events** - Events (Tore, Karten, Wechsel)
4. **game_lineups** - Aufstellungen
5. **player_statistics** - Spieler-Statistiken
6. **game_odds** - Wettquoten

### Wichtige Spalten in `games`:

- `id` - Spiel-ID
- `date` - Datum
- `home_team_name`, `away_team_name` - Team-Namen
- `home_ft_result`, `away_ft_result` - Endergebnis
- `calculated_xg_home`, `calculated_xg_away` - xG-Werte
- `over_25`, `over_35`, `over_45` - Over/Under Flags
- `league_id`, `league_name` - Liga-Informationen
- `season_year` - Jahr

## 🔧 Daten exportieren

### Als CSV:

```python
import csv
from database import DatabaseManager
import sqlite3

db = DatabaseManager("data/flashscore.db")
conn = db.get_connection()
conn.row_factory = sqlite3.Row

rows = conn.execute("SELECT * FROM games").fetchall()

with open('games_export.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows([dict(row) for row in rows])

db.close()
```

### Als JSON:

```python
import json
from database import DatabaseManager
import sqlite3

db = DatabaseManager("data/flashscore.db")
conn = db.get_connection()
conn.row_factory = sqlite3.Row

rows = conn.execute("SELECT * FROM games").fetchall()
games = [dict(row) for row in rows]

with open('games_export.json', 'w', encoding='utf-8') as f:
    json.dump(games, f, indent=2, ensure_ascii=False)

db.close()
```

## 📝 Beispiel: Datenanalyse

```python
from database import DatabaseManager
import sqlite3

db = DatabaseManager("data/flashscore.db")
conn = db.get_connection()
conn.row_factory = sqlite3.Row

# Durchschnittliche Tore pro Liga
rows = conn.execute("""
    SELECT league_name, season_year,
           AVG(home_ft_result + away_ft_result) as avg_goals,
           COUNT(*) as games
    FROM games
    GROUP BY league_id, season_year
    ORDER BY avg_goals DESC
""").fetchall()

for row in rows:
    print(f"{row['league_name']} {row['season_year']}: "
          f"{row['avg_goals']:.2f} goals/game ({row['games']} games)")

db.close()
```























