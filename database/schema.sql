-- SQLite Database Schema for Flashscore Game Statistics
-- Estimated size per game: ~10-20 KB (with full statistics)
-- 1,000 games: ~10-20 MB
-- 10,000 games: ~100-200 MB
-- 100,000 games: ~1-2 GB

-- Games table - main game information
CREATE TABLE IF NOT EXISTS games (
    id INTEGER PRIMARY KEY,
    flash_id TEXT,
    date TEXT NOT NULL,
    date_utc INTEGER,
    status INTEGER,
    status_name TEXT,
    elapsed INTEGER,
    extra_minutes INTEGER,
    
    -- Scores
    home_result INTEGER,
    away_result INTEGER,
    home_ht_result INTEGER,
    away_ht_result INTEGER,
    home_ft_result INTEGER,
    away_ft_result INTEGER,
    
    -- Teams
    home_team_id INTEGER,
    home_team_name TEXT,
    away_team_id INTEGER,
    away_team_name TEXT,
    
    -- League/Season
    league_id INTEGER,
    league_name TEXT,
    country_code TEXT,
    country_name TEXT,
    season_uid TEXT,
    season_year INTEGER,
    round_name TEXT,
    
    -- Venue
    venue_name TEXT,
    venue_city TEXT,
    referee_name TEXT,
    
    -- Calculated values
    calculated_xg_home REAL,
    calculated_xg_away REAL,
    total_goals INTEGER,
    over_25 INTEGER DEFAULT 0,  -- 1 if > 2.5, 0 if <= 2.5
    over_35 INTEGER DEFAULT 0,
    over_45 INTEGER DEFAULT 0,
    
    -- Metadata
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    
    -- Indexes for faster queries
    UNIQUE(id)
);

-- Upcoming games table - for future/upcoming games only
-- This table is used for live tracking and can be cleaned up without affecting historical statistics
CREATE TABLE IF NOT EXISTS upcoming_games (
    id INTEGER PRIMARY KEY,
    flash_id TEXT,
    date TEXT NOT NULL,
    date_utc INTEGER,
    status INTEGER,
    status_name TEXT,
    elapsed INTEGER,
    extra_minutes INTEGER,
    
    -- Scores (may be NULL for upcoming games)
    home_result INTEGER,
    away_result INTEGER,
    home_ht_result INTEGER,
    away_ht_result INTEGER,
    home_ft_result INTEGER,
    away_ft_result INTEGER,
    
    -- Teams
    home_team_id INTEGER,
    home_team_name TEXT,
    away_team_id INTEGER,
    away_team_name TEXT,
    
    -- League/Season
    league_id INTEGER,
    league_name TEXT,
    country_code TEXT,
    country_name TEXT,
    season_uid TEXT,
    season_year INTEGER,
    round_name TEXT,
    
    -- Venue
    venue_name TEXT,
    venue_city TEXT,
    referee_name TEXT,
    
    -- Metadata
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    
    -- Indexes for faster queries
    UNIQUE(id)
);

CREATE INDEX IF NOT EXISTS idx_upcoming_games_date ON upcoming_games(date);
CREATE INDEX IF NOT EXISTS idx_upcoming_games_league_id ON upcoming_games(league_id);
CREATE INDEX IF NOT EXISTS idx_upcoming_games_status ON upcoming_games(status);

-- Statistics table - detailed match statistics
CREATE TABLE IF NOT EXISTS game_statistics (
    game_id INTEGER PRIMARY KEY,
    
    -- Shots
    shots_on_goal_home INTEGER,
    shots_on_goal_away INTEGER,
    shots_off_goal_home INTEGER,
    shots_off_goal_away INTEGER,
    total_shots_home INTEGER,
    total_shots_away INTEGER,
    blocked_shots_home INTEGER,
    blocked_shots_away INTEGER,
    shots_inside_box_home INTEGER,
    shots_inside_box_away INTEGER,
    shots_outside_box_home INTEGER,
    shots_outside_box_away INTEGER,
    
    -- Possession & Passing
    ball_possession_home INTEGER,
    ball_possession_away INTEGER,
    total_passes_home INTEGER,
    total_passes_away INTEGER,
    passes_accurate_home INTEGER,
    passes_accurate_away INTEGER,
    
    -- Other stats
    fouls_home INTEGER,
    fouls_away INTEGER,
    corner_kicks_home INTEGER,
    corner_kicks_away INTEGER,
    yellow_cards_home INTEGER,
    yellow_cards_away INTEGER,
    red_cards_home INTEGER,
    red_cards_away INTEGER,
    goalkeeper_saves_home INTEGER,
    goalkeeper_saves_away INTEGER,
    offsides_home INTEGER,
    offsides_away INTEGER,
    
    -- Expected values
    expected_goals_home REAL,
    expected_goals_away REAL,
    expected_assists_home REAL,
    expected_assists_away REAL,
    big_chances_home INTEGER,
    big_chances_away INTEGER,
    goals_prevented_home REAL,
    goals_prevented_away REAL,
    
    -- Additional stats (stored as JSON for flexibility)
    other_stats_home TEXT,  -- JSON
    other_stats_away TEXT,  -- JSON
    
    FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE
);

-- Events table - match events (goals, cards, substitutions)
CREATE TABLE IF NOT EXISTS game_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL,
    event_id INTEGER,
    team_id INTEGER,
    elapsed INTEGER,
    extra_minutes INTEGER,
    type INTEGER,  -- 1=Goal, 2=Card, 3=Substitution, etc.
    name TEXT,
    player_id INTEGER,
    player_name TEXT,
    assist_player_id INTEGER,
    assist_player_name TEXT,
    
    FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE
);

-- Lineups table - player lineups
CREATE TABLE IF NOT EXISTS game_lineups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    player_id INTEGER,
    player_name TEXT,
    number INTEGER,
    position TEXT,
    grid TEXT,
    start_xi INTEGER DEFAULT 0,  -- 1 if starting, 0 if substitute
    
    FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE
);

-- Player statistics table
CREATE TABLE IF NOT EXISTS player_statistics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL,
    player_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    
    minutes INTEGER,
    captain INTEGER DEFAULT 0,
    substitute INTEGER DEFAULT 0,
    
    -- Offensive
    shots_total INTEGER,
    shots_on INTEGER,
    goals_total INTEGER,
    goals_assists INTEGER,
    
    -- Defensive
    goals_conceded INTEGER,
    goals_saves INTEGER,
    
    -- Passing
    passes_total INTEGER,
    passes_key INTEGER,
    passes_accuracy INTEGER,
    
    -- Defensive actions
    tackles_total INTEGER,
    tackles_blocks INTEGER,
    tackles_interceptions INTEGER,
    duels_total INTEGER,
    duels_won INTEGER,
    
    -- Other
    dribbles_attempts INTEGER,
    dribbles_success INTEGER,
    dribbles_past INTEGER,
    fouls_drawn INTEGER,
    fouls_committed INTEGER,
    cards_yellow INTEGER DEFAULT 0,
    cards_red INTEGER DEFAULT 0,
    penalty_won INTEGER,
    penalty_committed INTEGER,
    penalty_scored INTEGER DEFAULT 0,
    penalty_missed INTEGER DEFAULT 0,
    penalty_saved INTEGER,
    offsides INTEGER,
    rating REAL,
    
    FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE
);

-- Odds table - betting odds (optional)
CREATE TABLE IF NOT EXISTS game_odds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL,
    market_id INTEGER,
    market_name TEXT,
    name TEXT,  -- Home/Away/Draw, Over/Under, etc.
    value REAL,
    opening_value REAL,
    
    FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE
);

-- Glicko ratings and predictions table
CREATE TABLE IF NOT EXISTS game_glicko (
    game_id INTEGER PRIMARY KEY,
    
    -- Home team ratings
    home_rating REAL,
    home_rd REAL,  -- Rating deviation
    home_volatility REAL,
    
    -- Away team ratings
    away_rating REAL,
    away_rd REAL,  -- Rating deviation
    away_volatility REAL,
    
    -- Predictions
    home_xg REAL,
    away_xg REAL,
    home_win_probability REAL,
    away_win_probability REAL,
    draw_probability REAL,  -- Calculated as 1 - home_win - away_win
    
    -- Metadata
    updated TEXT,  -- Timestamp from API
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE
);

-- Form2: saisonale Team-Avgs (gesamt + Home/Away-Split) + pred. Match-xG
-- Parallel zu Glicko2, selbst berechnet (nur Meisterschaften, Reset pro Saison)
-- Venue-Namen B: hometeam_home_xg, awayteam_away_xga, …
CREATE TABLE IF NOT EXISTS game_form2 (
    game_id INTEGER PRIMARY KEY,
    home_n INTEGER NOT NULL DEFAULT 0,
    home_avg_xg REAL,
    home_avg_xga REAL,
    home_avg_gf REAL,
    home_avg_ga REAL,
    away_n INTEGER NOT NULL DEFAULT 0,
    away_avg_xg REAL,
    away_avg_xga REAL,
    away_avg_gf REAL,
    away_avg_ga REAL,
    -- Pred. Match-xG gesamt: (eigenes avgXG + Gegner avgXGA) / 2
    home_xg REAL,
    away_xg REAL,
    -- Venue-Split (Namen B)
    hometeam_home_n INTEGER NOT NULL DEFAULT 0,
    hometeam_home_xg REAL,
    hometeam_home_xga REAL,
    hometeam_home_gf REAL,
    hometeam_home_ga REAL,
    hometeam_away_n INTEGER NOT NULL DEFAULT 0,
    hometeam_away_xg REAL,
    hometeam_away_xga REAL,
    hometeam_away_gf REAL,
    hometeam_away_ga REAL,
    awayteam_home_n INTEGER NOT NULL DEFAULT 0,
    awayteam_home_xg REAL,
    awayteam_home_xga REAL,
    awayteam_home_gf REAL,
    awayteam_home_ga REAL,
    awayteam_away_n INTEGER NOT NULL DEFAULT 0,
    awayteam_away_xg REAL,
    awayteam_away_xga REAL,
    awayteam_away_gf REAL,
    awayteam_away_ga REAL,
    hometeam_pred_xg REAL,
    awayteam_pred_xg REAL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_games_date ON games(date);
CREATE INDEX IF NOT EXISTS idx_games_league_id ON games(league_id);
CREATE INDEX IF NOT EXISTS idx_games_season_year ON games(season_year);
CREATE INDEX IF NOT EXISTS idx_games_status ON games(status);
CREATE INDEX IF NOT EXISTS idx_games_home_team_id ON games(home_team_id);
CREATE INDEX IF NOT EXISTS idx_games_away_team_id ON games(away_team_id);
CREATE INDEX IF NOT EXISTS idx_games_over_25 ON games(over_25);
CREATE INDEX IF NOT EXISTS idx_games_over_35 ON games(over_35);
CREATE INDEX IF NOT EXISTS idx_games_over_45 ON games(over_45);

CREATE INDEX IF NOT EXISTS idx_events_game_id ON game_events(game_id);
CREATE INDEX IF NOT EXISTS idx_lineups_game_id ON game_lineups(game_id);
CREATE INDEX IF NOT EXISTS idx_player_stats_game_id ON player_statistics(game_id);
CREATE INDEX IF NOT EXISTS idx_odds_game_id ON game_odds(game_id);
CREATE INDEX IF NOT EXISTS idx_glicko_game_id ON game_glicko(game_id);
CREATE INDEX IF NOT EXISTS idx_form2_game_id ON game_form2(game_id);

-- Game profits table - betting profit data
CREATE TABLE IF NOT EXISTS game_profits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL,
    team_type TEXT NOT NULL,  -- 'home', 'away', 'homeFirstHalf', 'awayFirstHalf', 'homeSecondHalf', 'awaySecondHalf'
    market TEXT NOT NULL,  -- 'Match Winner', 'Double Chance', 'Goals Over/Under', etc.
    outcome_name TEXT NOT NULL,  -- 'Win', 'Draw', 'Lose', 'Over 2.5', etc.
    profit REAL,
    profit_history TEXT,  -- JSON array of profit values
    games_count INTEGER,
    win_count INTEGER,
    
    FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE,
    UNIQUE(game_id, team_type, market, outcome_name)
);

CREATE INDEX IF NOT EXISTS idx_profits_game_id ON game_profits(game_id);
CREATE INDEX IF NOT EXISTS idx_profits_team_type ON game_profits(team_type);
CREATE INDEX IF NOT EXISTS idx_profits_market ON game_profits(market);

-- Leagues table - stores league statistics including streak stats for Over 2.5, 3.5, and 4.5 goals
CREATE TABLE IF NOT EXISTS leagues (
    league_id INTEGER PRIMARY KEY,
    league_name TEXT,
    country_name TEXT,
    country_code TEXT,
    
    -- Streak statistics for season 2022 (Over 2.5 goals)
    max_streak_current_season INTEGER DEFAULT 0,
    min_streak_current_season INTEGER DEFAULT 0,
    median_streak_current_season REAL DEFAULT 0,
    
    -- Streak statistics over all seasons (Over 2.5 goals)
    max_streak_all_seasons INTEGER DEFAULT 0,
    min_streak_all_seasons INTEGER DEFAULT 0,
    median_streak_all_seasons REAL DEFAULT 0,
    
    -- Streak statistics for season 2022 (Over 3.5 goals)
    max_streak_current_season_35 INTEGER DEFAULT 0,
    median_streak_current_season_35 REAL DEFAULT 0,
    
    -- Streak statistics over all seasons (Over 3.5 goals)
    max_streak_all_seasons_35 INTEGER DEFAULT 0,
    median_streak_all_seasons_35 REAL DEFAULT 0,
    
    -- Streak statistics for season 2022 (Over 4.5 goals)
    max_streak_current_season_45 INTEGER DEFAULT 0,
    median_streak_current_season_45 REAL DEFAULT 0,
    
    -- Streak statistics over all seasons (Over 4.5 goals)
    max_streak_all_seasons_45 INTEGER DEFAULT 0,
    median_streak_all_seasons_45 REAL DEFAULT 0,
    
    -- Max streak per season for Over 2.5 goals
    max_streak_2022_25 INTEGER DEFAULT 0,
    max_streak_2023_25 INTEGER DEFAULT 0,
    max_streak_2024_25 INTEGER DEFAULT 0,
    max_streak_2025_25 INTEGER DEFAULT 0,
    max_streak_2026_25 INTEGER DEFAULT 0,
    
    -- Max streak per season for Over 3.5 goals
    max_streak_2022_35 INTEGER DEFAULT 0,
    max_streak_2023_35 INTEGER DEFAULT 0,
    max_streak_2024_35 INTEGER DEFAULT 0,
    max_streak_2025_35 INTEGER DEFAULT 0,
    max_streak_2026_35 INTEGER DEFAULT 0,
    
    -- Max streak per season for Over 4.5 goals
    max_streak_2022_45 INTEGER DEFAULT 0,
    max_streak_2023_45 INTEGER DEFAULT 0,
    max_streak_2024_45 INTEGER DEFAULT 0,
    max_streak_2025_45 INTEGER DEFAULT 0,
    max_streak_2026_45 INTEGER DEFAULT 0,
    
    -- Metadata
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_leagues_league_id ON leagues(league_id);
CREATE INDEX IF NOT EXISTS idx_leagues_country ON leagues(country_name);

-- View for quick game overview
CREATE VIEW IF NOT EXISTS games_overview AS
SELECT 
    g.id,
    g.date,
    g.home_team_name,
    g.away_team_name,
    g.home_ft_result,
    g.away_ft_result,
    g.total_goals,
    g.over_25,
    g.over_35,
    g.over_45,
    g.calculated_xg_home,
    g.calculated_xg_away,
    g.league_name,
    g.country_name,
    g.season_year,
    g.status_name
FROM games g
WHERE g.status IN (7, 8, 9, 10)  -- Finished games only
ORDER BY g.date DESC;

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

-- View to transform game_odds from rows to columns
-- Makes it easier to query odds as columns instead of rows
-- value = Closing, opening_value = Opening (siehe create_odds_view.sql)
-- IF NOT EXISTS: paralleler DB-Init (API + Desktop) sonst "view already exists"
DROP VIEW IF EXISTS game_odds_pivoted;
CREATE VIEW IF NOT EXISTS game_odds_pivoted AS
SELECT
    game_id,
    MAX(CASE WHEN market_id = 1 AND name = 'Home' THEN value END) AS odd_home,
    MAX(CASE WHEN market_id = 1 AND name = 'Draw' THEN value END) AS odd_draw,
    MAX(CASE WHEN market_id = 1 AND name = 'Away' THEN value END) AS odd_away,
    MAX(CASE WHEN market_id = 1 AND name = 'Under 1.5' THEN value END) AS odd_under_15,
    MAX(CASE WHEN market_id = 1 AND name = 'Home' THEN opening_value END) AS odd_open_home,
    MAX(CASE WHEN market_id = 1 AND name = 'Draw' THEN opening_value END) AS odd_open_draw,
    MAX(CASE WHEN market_id = 1 AND name = 'Away' THEN opening_value END) AS odd_open_away,
    MAX(CASE WHEN market_id = 5 AND name = 'Over 2.5' THEN value END) AS odd_over_25,
    MAX(CASE WHEN market_id = 5 AND name = 'Under 2.5' THEN value END) AS odd_under_25,
    MAX(CASE WHEN market_id = 5 AND name = 'Over 3.5' THEN value END) AS odd_over_35,
    MAX(CASE WHEN market_id = 5 AND name = 'Under 3.5' THEN value END) AS odd_under_35,
    MAX(CASE WHEN market_id = 5 AND name = 'Over 4.5' THEN value END) AS odd_over_45,
    MAX(CASE WHEN market_id = 5 AND name = 'Under 4.5' THEN value END) AS odd_under_45,
    MAX(CASE WHEN market_id = 5 AND name = 'Over 2.5' THEN opening_value END) AS odd_open_over_25,
    MAX(CASE WHEN market_id = 5 AND name = 'Under 2.5' THEN opening_value END) AS odd_open_under_25,
    MAX(CASE WHEN market_id = 5 AND name = 'Over 3.5' THEN opening_value END) AS odd_open_over_35,
    MAX(CASE WHEN market_id = 5 AND name = 'Under 3.5' THEN opening_value END) AS odd_open_under_35,
    MAX(CASE WHEN market_id = 5 AND name = 'Over 4.5' THEN opening_value END) AS odd_open_over_45,
    MAX(CASE WHEN market_id = 5 AND name = 'Under 4.5' THEN opening_value END) AS odd_open_under_45
FROM game_odds
GROUP BY game_id;


