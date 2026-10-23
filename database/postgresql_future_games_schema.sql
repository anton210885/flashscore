-- PostgreSQL Schema for Future Games with Odds
-- This table stores upcoming/future games with their betting odds
-- Run this script in PostgreSQL to create the table

CREATE TABLE IF NOT EXISTS future_games (
    -- Primary key
    id BIGINT PRIMARY KEY,
    
    -- Game identification
    flash_id TEXT,
    
    -- Date and time
    date TIMESTAMP WITH TIME ZONE NOT NULL,
    date_utc BIGINT,
    
    -- Game status
    status INTEGER,
    status_name TEXT,
    
    -- Teams
    home_team_id INTEGER,
    home_team_name TEXT NOT NULL,
    away_team_id INTEGER,
    away_team_name TEXT NOT NULL,
    
    -- League/Season information
    league_id INTEGER NOT NULL,
    league_name TEXT,
    country_code TEXT,
    country_name TEXT,
    season_uid TEXT,
    season_year INTEGER,
    round_name TEXT,
    
    -- Venue information
    venue_name TEXT,
    venue_city TEXT,
    referee_name TEXT,
    
    -- Odds - Match Winner (1X2)
    odd_home DECIMAL(10, 3),
    odd_draw DECIMAL(10, 3),
    odd_away DECIMAL(10, 3),
    
    -- Odds - Over/Under 2.5 Goals
    odd_over_25 DECIMAL(10, 3),
    odd_under_25 DECIMAL(10, 3),
    
    -- Odds - Over/Under 3.5 Goals (optional)
    odd_over_35 DECIMAL(10, 3),
    odd_under_35 DECIMAL(10, 3),
    
    -- Odds - Over/Under 4.5 Goals (optional)
    odd_over_45 DECIMAL(10, 3),
    odd_under_45 DECIMAL(10, 3),
    
    -- Opening Odds (initial odds when market opens)
    odd_home_opening DECIMAL(10, 3),
    odd_draw_opening DECIMAL(10, 3),
    odd_away_opening DECIMAL(10, 3),
    odd_over_25_opening DECIMAL(10, 3),
    odd_under_25_opening DECIMAL(10, 3),
    
    -- Bookmaker information
    bookmaker_id INTEGER,
    bookmaker_name TEXT,
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT future_games_status_check CHECK (status IN (0, 1, 2) OR status IS NULL) -- Only upcoming/not started games
);

-- Indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_future_games_date ON future_games(date);
CREATE INDEX IF NOT EXISTS idx_future_games_league_id ON future_games(league_id);
CREATE INDEX IF NOT EXISTS idx_future_games_country ON future_games(country_name);
CREATE INDEX IF NOT EXISTS idx_future_games_status ON future_games(status);
CREATE INDEX IF NOT EXISTS idx_future_games_created_at ON future_games(created_at);

-- Index for common query patterns
CREATE INDEX IF NOT EXISTS idx_future_games_league_date ON future_games(league_id, date);
CREATE INDEX IF NOT EXISTS idx_future_games_country_date ON future_games(country_name, date);

-- Function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_future_games_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to update updated_at on row update
CREATE TRIGGER trigger_update_future_games_updated_at
    BEFORE UPDATE ON future_games
    FOR EACH ROW
    EXECUTE FUNCTION update_future_games_updated_at();

-- View for easy access to games with odds
CREATE OR REPLACE VIEW future_games_with_odds AS
SELECT 
    id,
    date,
    date_utc,
    status,
    status_name,
    home_team_name,
    away_team_name,
    league_name,
    country_name,
    season_year,
    round_name,
    venue_name,
    venue_city,
    -- Current odds
    odd_home,
    odd_draw,
    odd_away,
    odd_over_25,
    odd_under_25,
    odd_over_35,
    odd_under_35,
    odd_over_45,
    odd_under_45,
    -- Opening odds
    odd_home_opening,
    odd_draw_opening,
    odd_away_opening,
    odd_over_25_opening,
    odd_under_25_opening,
    -- Odds movement (current - opening)
    (odd_home - odd_home_opening) AS odd_home_movement,
    (odd_draw - odd_draw_opening) AS odd_draw_movement,
    (odd_away - odd_away_opening) AS odd_away_movement,
    (odd_over_25 - odd_over_25_opening) AS odd_over_25_movement,
    (odd_under_25 - odd_under_25_opening) AS odd_under_25_movement,
    bookmaker_name,
    created_at,
    updated_at
FROM future_games
WHERE status IN (0, 1, 2) OR status IS NULL  -- Only upcoming games
ORDER BY date ASC;

-- Comment on table
COMMENT ON TABLE future_games IS 'Stores upcoming/future games with betting odds';
COMMENT ON COLUMN future_games.id IS 'Game ID from API';
COMMENT ON COLUMN future_games.date IS 'Game date and time';
COMMENT ON COLUMN future_games.status IS 'Game status: 0=Unknown, 1=Not Started, 2=Scheduled';
COMMENT ON COLUMN future_games.odd_home IS 'Current odds for home win';
COMMENT ON COLUMN future_games.odd_draw IS 'Current odds for draw';
COMMENT ON COLUMN future_games.odd_away IS 'Current odds for away win';
COMMENT ON COLUMN future_games.odd_over_25 IS 'Current odds for over 2.5 goals';
COMMENT ON COLUMN future_games.odd_under_25 IS 'Current odds for under 2.5 goals';


