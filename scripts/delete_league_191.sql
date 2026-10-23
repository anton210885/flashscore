-- SQL Script to delete all games from League 191 (Brisbane)
-- This will delete games from all relevant tables

-- SQLite Database (flashscore.db)
-- =================================

-- 1. Delete from games table (CASCADE will automatically delete related data from:
--    - game_statistics
--    - game_events
--    - game_lineups
--    - player_statistics
--    - game_odds
--    - game_glicko
--    - game_profits
DELETE FROM games WHERE league_id = 191;

-- 2. Delete from upcoming_games table
DELETE FROM upcoming_games WHERE league_id = 191;

-- Verify deletion (optional - run these to check)
-- SELECT COUNT(*) as remaining_games FROM games WHERE league_id = 191;
-- SELECT COUNT(*) as remaining_upcoming FROM upcoming_games WHERE league_id = 191;

-- PostgreSQL Database (if using PostgreSQL)
-- ==========================================

-- 3. Delete from future_games table (PostgreSQL)
-- DELETE FROM future_games WHERE league_id = 191;

-- Verify deletion (optional - run this to check)
-- SELECT COUNT(*) as remaining_future FROM future_games WHERE league_id = 191;

