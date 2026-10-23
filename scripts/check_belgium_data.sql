-- SQL Script zum Überprüfen der belgischen Ligen-Daten in der Datenbank
-- Ausführen mit: sqlite3 data/flashscore.db < scripts/check_belgium_data.sql

-- Übersicht: Anzahl Spiele pro Liga
SELECT 
    league_id,
    CASE 
        WHEN league_id = 144 THEN 'Jupiler Pro League'
        WHEN league_id = 145 THEN 'Challenger Pro League'
        ELSE 'Unknown'
    END AS league_name,
    COUNT(*) AS total_games,
    COUNT(CASE WHEN status IN (7, 8, 9, 10) THEN 1 END) AS finished_games,
    MIN(date) AS earliest_game,
    MAX(date) AS latest_game
FROM games
WHERE league_id IN (144, 145)
GROUP BY league_id;

-- Spiele pro Jahr
SELECT 
    league_id,
    CASE 
        WHEN league_id = 144 THEN 'Jupiler Pro League'
        WHEN league_id = 145 THEN 'Challenger Pro League'
        ELSE 'Unknown'
    END AS league_name,
    season_year,
    COUNT(*) AS games_count
FROM games
WHERE league_id IN (144, 145)
GROUP BY league_id, season_year
ORDER BY league_id, season_year DESC;

-- Spiele mit xG Daten
SELECT 
    league_id,
    CASE 
        WHEN league_id = 144 THEN 'Jupiler Pro League'
        WHEN league_id = 145 THEN 'Challenger Pro League'
        ELSE 'Unknown'
    END AS league_name,
    COUNT(*) AS total_games,
    COUNT(calculated_xg_home) AS games_with_xg_home,
    COUNT(calculated_xg_away) AS games_with_xg_away,
    COUNT(CASE WHEN calculated_xg_home IS NOT NULL AND calculated_xg_away IS NOT NULL THEN 1 END) AS games_with_both_xg
FROM games
WHERE league_id IN (144, 145)
GROUP BY league_id;

-- Spiele mit Glicko Daten
SELECT 
    g.league_id,
    CASE 
        WHEN g.league_id = 144 THEN 'Jupiler Pro League'
        WHEN g.league_id = 145 THEN 'Challenger Pro League'
        ELSE 'Unknown'
    END AS league_name,
    COUNT(DISTINCT g.id) AS total_games,
    COUNT(DISTINCT gl.game_id) AS games_with_glicko
FROM games g
LEFT JOIN game_glicko gl ON g.id = gl.game_id
WHERE g.league_id IN (144, 145)
GROUP BY g.league_id;

-- Spiele mit Odds Daten
SELECT 
    g.league_id,
    CASE 
        WHEN g.league_id = 144 THEN 'Jupiler Pro League'
        WHEN g.league_id = 145 THEN 'Challenger Pro League'
        ELSE 'Unknown'
    END AS league_name,
    COUNT(DISTINCT g.id) AS total_games,
    COUNT(DISTINCT o.game_id) AS games_with_odds
FROM games g
LEFT JOIN game_odds o ON g.id = o.game_id
WHERE g.league_id IN (144, 145)
GROUP BY g.league_id;

-- Spiele mit Profit Daten
SELECT 
    g.league_id,
    CASE 
        WHEN g.league_id = 144 THEN 'Jupiler Pro League'
        WHEN g.league_id = 145 THEN 'Challenger Pro League'
        ELSE 'Unknown'
    END AS league_name,
    COUNT(DISTINCT g.id) AS total_games,
    COUNT(DISTINCT p.game_id) AS games_with_profits
FROM games g
LEFT JOIN game_profits p ON g.id = p.game_id
WHERE g.league_id IN (144, 145)
GROUP BY g.league_id;

-- Beispiel: Letzte 10 Spiele mit Details
SELECT 
    g.id,
    g.date,
    g.home_team_name,
    g.away_team_name,
    g.home_ft_result || '-' || g.away_ft_result AS score,
    g.calculated_xg_home,
    g.calculated_xg_away,
    CASE 
        WHEN g.league_id = 144 THEN 'Jupiler Pro League'
        WHEN g.league_id = 145 THEN 'Challenger Pro League'
        ELSE 'Unknown'
    END AS league_name
FROM games g
WHERE g.league_id IN (144, 145)
ORDER BY g.date DESC
LIMIT 10;

