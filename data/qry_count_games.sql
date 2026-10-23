-- Anzahl Spiele pro Liga, Jahr und Land
SELECT 
    COALESCE(country_name, 'Unknown') as country_name,
    COALESCE(league_name, 'Unknown League') as league_name,
    season_year,
    league_id,
    COUNT(*) as total_games,
    COUNT(CASE WHEN home_ft_result IS NOT NULL AND away_ft_result IS NOT NULL THEN 1 END) as finished_games,
    COUNT(CASE WHEN home_ft_result IS NULL OR away_ft_result IS NULL THEN 1 END) as unfinished_games,
    COUNT(CASE WHEN calculated_xg_home IS NOT NULL AND calculated_xg_away IS NOT NULL THEN 1 END) as games_with_xg,
    ROUND(
        COUNT(CASE WHEN calculated_xg_home IS NOT NULL AND calculated_xg_away IS NOT NULL THEN 1 END) * 100.0 / COUNT(*), 
        2
    ) as xg_coverage_percent
FROM games
WHERE league_id IS NOT NULL AND season_year IS NOT NULL
GROUP BY country_name, league_name, league_id, season_year
ORDER BY country_name, league_name, season_year DESC;

-- Alternative Gruppierung: Zuerst nach Land, dann nach Jahr, dann nach Liga
SELECT 
    COALESCE(country_name, 'Unknown') as country_name,
    season_year,
    COALESCE(league_name, 'Unknown League') as league_name,
    league_id,
    COUNT(*) as total_games,
    COUNT(CASE WHEN home_ft_result IS NOT NULL AND away_ft_result IS NOT NULL THEN 1 END) as finished_games,
    COUNT(CASE WHEN calculated_xg_home IS NOT NULL AND calculated_xg_away IS NOT NULL THEN 1 END) as games_with_xg
FROM games
WHERE league_id IS NOT NULL AND season_year IS NOT NULL
GROUP BY country_name, season_year, league_name, league_id
ORDER BY country_name, league_name, season_year DESC;