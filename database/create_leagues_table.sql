-- Create leagues table to store league statistics including max streaks
CREATE TABLE IF NOT EXISTS leagues (
    league_id INTEGER PRIMARY KEY,
    league_name TEXT,
    country_name TEXT,
    country_code TEXT,
    
    -- Max streak for current season (2025)
    max_streak_current_season INTEGER DEFAULT 0,
    
    -- Max streak over all seasons
    max_streak_all_seasons INTEGER DEFAULT 0,
    
    -- Metadata
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_leagues_league_id ON leagues(league_id);
CREATE INDEX IF NOT EXISTS idx_leagues_country ON leagues(country_name);

