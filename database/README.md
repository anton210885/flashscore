# Flashscore Database

## Datenbank-Empfehlung: SQLite

**Warum SQLite?**
- ✅ Keine separate Server-Installation nötig
- ✅ Datei-basiert (eine .db Datei)
- ✅ Sehr schnell für lokale Anwendungen
- ✅ Unterstützt komplexe Queries und Joins
- ✅ ACID-konform (Datenintegrität)
- ✅ Perfekt für bis zu mehreren GB Daten

## Geschätzte Datenbankgröße

### Pro Spiel (mit vollständigen Statistiken):
- **Basis-Informationen**: ~2-3 KB
- **Statistiken**: ~3-5 KB
- **Events (Tore, Karten, etc.)**: ~1-2 KB
- **Lineups**: ~2-3 KB
- **Player Statistics**: ~5-10 KB
- **Odds (optional)**: ~1-2 KB
- **Gesamt pro Spiel**: ~15-25 KB

### Gesamtgröße:
- **1.000 Spiele**: ~15-25 MB
- **10.000 Spiele**: ~150-250 MB
- **50.000 Spiele**: ~750 MB - 1.25 GB
- **100.000 Spiele**: ~1.5-2.5 GB

### Empfehlung:
- **Für 10.000-50.000 Spiele**: SQLite ist perfekt
- **Für >100.000 Spiele**: SQLite funktioniert noch, aber könnte langsamer werden
- **Für >500.000 Spiele**: PostgreSQL oder MySQL in Betracht ziehen

## Datenbankstruktur

Die Datenbank besteht aus folgenden Tabellen:

1. **games** - Haupttabelle mit Spielinformationen
2. **game_statistics** - Detaillierte Match-Statistiken
3. **game_events** - Events (Tore, Karten, Wechsel)
4. **game_lineups** - Aufstellungen
5. **player_statistics** - Spieler-Statistiken
6. **game_odds** - Wettquoten (optional)

## Verwendung

```python
from database.db_manager import DatabaseManager

# Datenbank initialisieren
db = DatabaseManager("data/flashscore.db")

# Spiel speichern (komplett mit allen Statistiken)
game_data = api_client.get_game(game_id)
db.save_game(game_data)

# Spiele abrufen
games = db.get_games_by_league(league_id=188, year=2025)

# Datenbankgröße prüfen
size_info = db.get_database_size()
print(f"DB Größe: {size_info['file_size_mb']} MB")
print(f"Spiele: {size_info['games']}")
```

## Performance-Tipps

1. **Indizes**: Bereits in schema.sql definiert für schnelle Queries
2. **Batch-Inserts**: Mehrere Spiele auf einmal speichern
3. **VACUUM**: Regelmäßig `VACUUM` ausführen für Optimierung
4. **WAL-Mode**: Für bessere Performance bei vielen Schreibvorgängen

## Migration zu größerer DB

Falls SQLite zu langsam wird:
- **PostgreSQL**: Professionell, sehr schnell, benötigt Server
- **MySQL/MariaDB**: Ähnlich wie PostgreSQL
- **Datenexport**: SQLite → PostgreSQL Migration möglich
























