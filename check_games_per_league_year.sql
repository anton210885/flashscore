-- SQL Script to check number of games per league and per year
-- Run this in SQLite to see game counts

-- Total games per league and year
SELECT 
    league_id,
    COALESCE(league_name, 'Unknown League') as league_name,
    COALESCE(country_name, 'Unknown') as country_name,
    season_year,
    COUNT(*) as total_games,
    COUNT(CASE WHEN home_ft_result IS NOT NULL AND away_ft_result IS NOT NULL THEN 1 END) as finished_games,
    COUNT(CASE WHEN home_ft_result IS NULL OR away_ft_result IS NULL THEN 1 END) as unfinished_games,
    COUNT(CASE WHEN calculated_xg_home IS NOT NULL AND calculated_xg_away IS NOT NULL THEN 1 END) as games_with_xg
FROM games
WHERE league_id IS NOT NULL
GROUP BY league_id, league_name, country_name, season_year
ORDER BY country_name, league_name, season_year DESC;

-- Summary: Total games per league (all years combined)
SELECT 
    league_id,
    COALESCE(league_name, 'Unknown League') as league_name,
    COALESCE(country_name, 'Unknown') as country_name,
    COUNT(*) as total_games_all_years,
    COUNT(CASE WHEN home_ft_result IS NOT NULL AND away_ft_result IS NOT NULL THEN 1 END) as finished_games_all_years,
    COUNT(CASE WHEN calculated_xg_home IS NOT NULL AND calculated_xg_away IS NOT NULL THEN 1 END) as games_with_xg_all_years,
    MIN(season_year) as first_year,
    MAX(season_year) as last_year
FROM games
WHERE league_id IS NOT NULL
GROUP BY league_id, league_name, country_name
ORDER BY country_name, league_name;

-- Summary: Total games per year (all leagues combined)
SELECT 
    season_year,
    COUNT(*) as total_games,
    COUNT(CASE WHEN home_ft_result IS NOT NULL AND away_ft_result IS NOT NULL THEN 1 END) as finished_games,
    COUNT(CASE WHEN calculated_xg_home IS NOT NULL AND calculated_xg_away IS NOT NULL THEN 1 END) as games_with_xg,
    COUNT(DISTINCT league_id) as number_of_leagues
FROM games
WHERE league_id IS NOT NULL AND season_year IS NOT NULL
GROUP BY season_year
ORDER BY season_year DESC;















