-- Comprehensive game details view
-- Combines games, glicko ratings, xG data, odds, and profits

CREATE VIEW IF NOT EXISTS game_details_view AS
SELECT 
    -- Basic game info
    g.id AS game_id,
    g.date,
    g.country_name,
    g.country_code,
    g.league_name,
    g.league_id,
    g.season_year,
    g.home_team_name,
    g.away_team_name,
    g.home_team_id,
    g.away_team_id,
    
    -- Results
    g.home_ft_result,
    g.away_ft_result,
    g.total_goals,
    
    -- xG from games table (calculated/expected)
    g.calculated_xg_home AS xg_home,
    g.calculated_xg_away AS xg_away,
    
    -- Glicko ratings
    gl.home_rating,
    gl.away_rating,
    gl.home_rd,
    gl.away_rd,
    gl.home_volatility,
    gl.away_volatility,
    
    -- Glicko xG predictions
    gl.home_xg AS xg_glicko_home,
    gl.away_xg AS xg_glicko_away,
    
    -- Glicko win probabilities
    gl.home_win_probability,
    gl.away_win_probability,
    gl.draw_probability,
    
    -- Odds (using the pivoted view for easier access)
    o.odd_home,
    o.odd_draw,
    o.odd_away,
    o.odd_under_15,
    o.odd_over_25,
    o.odd_under_25,
    o.odd_over_35,
    o.odd_under_35,
    o.odd_over_45,
    o.odd_under_45,
    o.odd_open_home,
    o.odd_open_draw,
    o.odd_open_away,
    o.odd_open_over_25,
    o.odd_open_under_25,
    
    -- Profit data for Match Winner (home team)
    (SELECT profit FROM game_profits WHERE game_id = g.id AND team_type = 'home' AND market = 'Match Winner' AND outcome_name = 'Win' LIMIT 1) AS profit_home_win,
    (SELECT profit FROM game_profits WHERE game_id = g.id AND team_type = 'home' AND market = 'Match Winner' AND outcome_name = 'Draw' LIMIT 1) AS profit_home_draw,
    (SELECT profit FROM game_profits WHERE game_id = g.id AND team_type = 'home' AND market = 'Match Winner' AND outcome_name = 'Lose' LIMIT 1) AS profit_home_lose,
    
    -- Profit data for Over/Under (home team)
    (SELECT profit FROM game_profits WHERE game_id = g.id AND team_type = 'home' AND market = 'Goals Over/Under' AND outcome_name = 'Over 2.5' LIMIT 1) AS profit_home_over_25,
    (SELECT profit FROM game_profits WHERE game_id = g.id AND team_type = 'home' AND market = 'Goals Over/Under' AND outcome_name = 'Under 2.5' LIMIT 1) AS profit_home_under_25,
    (SELECT profit FROM game_profits WHERE game_id = g.id AND team_type = 'home' AND market = 'Goals Over/Under' AND outcome_name = 'Over 3.5' LIMIT 1) AS profit_home_over_35,
    (SELECT profit FROM game_profits WHERE game_id = g.id AND team_type = 'home' AND market = 'Goals Over/Under' AND outcome_name = 'Under 3.5' LIMIT 1) AS profit_home_under_35,
    (SELECT profit FROM game_profits WHERE game_id = g.id AND team_type = 'home' AND market = 'Goals Over/Under' AND outcome_name = 'Over 4.5' LIMIT 1) AS profit_home_over_45,
    (SELECT profit FROM game_profits WHERE game_id = g.id AND team_type = 'home' AND market = 'Goals Over/Under' AND outcome_name = 'Under 4.5' LIMIT 1) AS profit_home_under_45,
    
    -- Games count and win count for Match Winner (home team)
    (SELECT games_count FROM game_profits WHERE game_id = g.id AND team_type = 'home' AND market = 'Match Winner' AND outcome_name = 'Win' LIMIT 1) AS games_count_home_win,
    (SELECT win_count FROM game_profits WHERE game_id = g.id AND team_type = 'home' AND market = 'Match Winner' AND outcome_name = 'Win' LIMIT 1) AS win_count_home_win,
    
    -- Chance (win probability) for each outcome - calculated as win_count / games_count
    CASE 
        WHEN (SELECT games_count FROM game_profits WHERE game_id = g.id AND team_type = 'home' AND market = 'Match Winner' AND outcome_name = 'Win' LIMIT 1) > 0
        THEN CAST((SELECT win_count FROM game_profits WHERE game_id = g.id AND team_type = 'home' AND market = 'Match Winner' AND outcome_name = 'Win' LIMIT 1) AS REAL) / 
             (SELECT games_count FROM game_profits WHERE game_id = g.id AND team_type = 'home' AND market = 'Match Winner' AND outcome_name = 'Win' LIMIT 1)
        ELSE NULL
    END AS chance_home_win,
    
    CASE 
        WHEN (SELECT games_count FROM game_profits WHERE game_id = g.id AND team_type = 'home' AND market = 'Match Winner' AND outcome_name = 'Draw' LIMIT 1) > 0
        THEN CAST((SELECT win_count FROM game_profits WHERE game_id = g.id AND team_type = 'home' AND market = 'Match Winner' AND outcome_name = 'Draw' LIMIT 1) AS REAL) / 
             (SELECT games_count FROM game_profits WHERE game_id = g.id AND team_type = 'home' AND market = 'Match Winner' AND outcome_name = 'Draw' LIMIT 1)
        ELSE NULL
    END AS chance_home_draw,
    
    CASE 
        WHEN (SELECT games_count FROM game_profits WHERE game_id = g.id AND team_type = 'home' AND market = 'Match Winner' AND outcome_name = 'Lose' LIMIT 1) > 0
        THEN CAST((SELECT win_count FROM game_profits WHERE game_id = g.id AND team_type = 'home' AND market = 'Match Winner' AND outcome_name = 'Lose' LIMIT 1) AS REAL) / 
             (SELECT games_count FROM game_profits WHERE game_id = g.id AND team_type = 'home' AND market = 'Match Winner' AND outcome_name = 'Lose' LIMIT 1)
        ELSE NULL
    END AS chance_home_lose,
    
    -- Chance for Over/Under
    CASE 
        WHEN (SELECT games_count FROM game_profits WHERE game_id = g.id AND team_type = 'home' AND market = 'Goals Over/Under' AND outcome_name = 'Over 2.5' LIMIT 1) > 0
        THEN CAST((SELECT win_count FROM game_profits WHERE game_id = g.id AND team_type = 'home' AND market = 'Goals Over/Under' AND outcome_name = 'Over 2.5' LIMIT 1) AS REAL) / 
             (SELECT games_count FROM game_profits WHERE game_id = g.id AND team_type = 'home' AND market = 'Goals Over/Under' AND outcome_name = 'Over 2.5' LIMIT 1)
        ELSE NULL
    END AS chance_home_over_25,
    
    CASE 
        WHEN (SELECT games_count FROM game_profits WHERE game_id = g.id AND team_type = 'home' AND market = 'Goals Over/Under' AND outcome_name = 'Under 2.5' LIMIT 1) > 0
        THEN CAST((SELECT win_count FROM game_profits WHERE game_id = g.id AND team_type = 'home' AND market = 'Goals Over/Under' AND outcome_name = 'Under 2.5' LIMIT 1) AS REAL) / 
             (SELECT games_count FROM game_profits WHERE game_id = g.id AND team_type = 'home' AND market = 'Goals Over/Under' AND outcome_name = 'Under 2.5' LIMIT 1)
        ELSE NULL
    END AS chance_home_under_25,
    
    CASE 
        WHEN (SELECT games_count FROM game_profits WHERE game_id = g.id AND team_type = 'home' AND market = 'Goals Over/Under' AND outcome_name = 'Over 3.5' LIMIT 1) > 0
        THEN CAST((SELECT win_count FROM game_profits WHERE game_id = g.id AND team_type = 'home' AND market = 'Goals Over/Under' AND outcome_name = 'Over 3.5' LIMIT 1) AS REAL) / 
             (SELECT games_count FROM game_profits WHERE game_id = g.id AND team_type = 'home' AND market = 'Goals Over/Under' AND outcome_name = 'Over 3.5' LIMIT 1)
        ELSE NULL
    END AS chance_home_over_35,
    
    CASE 
        WHEN (SELECT games_count FROM game_profits WHERE game_id = g.id AND team_type = 'home' AND market = 'Goals Over/Under' AND outcome_name = 'Under 3.5' LIMIT 1) > 0
        THEN CAST((SELECT win_count FROM game_profits WHERE game_id = g.id AND team_type = 'home' AND market = 'Goals Over/Under' AND outcome_name = 'Under 3.5' LIMIT 1) AS REAL) / 
             (SELECT games_count FROM game_profits WHERE game_id = g.id AND team_type = 'home' AND market = 'Goals Over/Under' AND outcome_name = 'Under 3.5' LIMIT 1)
        ELSE NULL
    END AS chance_home_under_35,
    
    CASE 
        WHEN (SELECT games_count FROM game_profits WHERE game_id = g.id AND team_type = 'home' AND market = 'Goals Over/Under' AND outcome_name = 'Over 4.5' LIMIT 1) > 0
        THEN CAST((SELECT win_count FROM game_profits WHERE game_id = g.id AND team_type = 'home' AND market = 'Goals Over/Under' AND outcome_name = 'Over 4.5' LIMIT 1) AS REAL) / 
             (SELECT games_count FROM game_profits WHERE game_id = g.id AND team_type = 'home' AND market = 'Goals Over/Under' AND outcome_name = 'Over 4.5' LIMIT 1)
        ELSE NULL
    END AS chance_home_over_45,
    
    CASE 
        WHEN (SELECT games_count FROM game_profits WHERE game_id = g.id AND team_type = 'home' AND market = 'Goals Over/Under' AND outcome_name = 'Under 4.5' LIMIT 1) > 0
        THEN CAST((SELECT win_count FROM game_profits WHERE game_id = g.id AND team_type = 'home' AND market = 'Goals Over/Under' AND outcome_name = 'Under 4.5' LIMIT 1) AS REAL) / 
             (SELECT games_count FROM game_profits WHERE game_id = g.id AND team_type = 'home' AND market = 'Goals Over/Under' AND outcome_name = 'Under 4.5' LIMIT 1)
        ELSE NULL
    END AS chance_home_under_45,
    
    -- Status
    g.status_name,
    g.status
    
FROM games g
LEFT JOIN game_glicko gl ON g.id = gl.game_id
LEFT JOIN game_odds_pivoted o ON g.id = o.game_id
WHERE g.status IN (7, 8, 9, 10)  -- Finished games only
ORDER BY g.date DESC;

