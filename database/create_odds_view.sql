-- View to transform game_odds from rows to columns
-- Makes it easier to query odds as columns instead of rows
-- value = Closing (kurz vor Anpfiff), opening_value = Opening (Eröffnung)

-- IF NOT EXISTS: paralleler DB-Init (API + Desktop) sonst "view already exists"
DROP VIEW IF EXISTS game_odds_pivoted;

CREATE VIEW IF NOT EXISTS game_odds_pivoted AS
SELECT
    game_id,
    -- Match Winner (market_id = 1) — Closing
    MAX(CASE WHEN market_id = 1 AND name = 'Home' THEN value END) AS odd_home,
    MAX(CASE WHEN market_id = 1 AND name = 'Draw' THEN value END) AS odd_draw,
    MAX(CASE WHEN market_id = 1 AND name = 'Away' THEN value END) AS odd_away,
    MAX(CASE WHEN market_id = 1 AND name = 'Under 1.5' THEN value END) AS odd_under_15,

    -- Match Winner — Opening
    MAX(CASE WHEN market_id = 1 AND name = 'Home' THEN opening_value END) AS odd_open_home,
    MAX(CASE WHEN market_id = 1 AND name = 'Draw' THEN opening_value END) AS odd_open_draw,
    MAX(CASE WHEN market_id = 1 AND name = 'Away' THEN opening_value END) AS odd_open_away,

    -- Over/Under (market_id = 5) — Closing
    MAX(CASE WHEN market_id = 5 AND name = 'Over 2.5' THEN value END) AS odd_over_25,
    MAX(CASE WHEN market_id = 5 AND name = 'Under 2.5' THEN value END) AS odd_under_25,
    MAX(CASE WHEN market_id = 5 AND name = 'Over 3.5' THEN value END) AS odd_over_35,
    MAX(CASE WHEN market_id = 5 AND name = 'Under 3.5' THEN value END) AS odd_under_35,
    MAX(CASE WHEN market_id = 5 AND name = 'Over 4.5' THEN value END) AS odd_over_45,
    MAX(CASE WHEN market_id = 5 AND name = 'Under 4.5' THEN value END) AS odd_under_45,

    -- Over/Under — Opening
    MAX(CASE WHEN market_id = 5 AND name = 'Over 2.5' THEN opening_value END) AS odd_open_over_25,
    MAX(CASE WHEN market_id = 5 AND name = 'Under 2.5' THEN opening_value END) AS odd_open_under_25,
    MAX(CASE WHEN market_id = 5 AND name = 'Over 3.5' THEN opening_value END) AS odd_open_over_35,
    MAX(CASE WHEN market_id = 5 AND name = 'Under 3.5' THEN opening_value END) AS odd_open_under_35,
    MAX(CASE WHEN market_id = 5 AND name = 'Over 4.5' THEN opening_value END) AS odd_open_over_45,
    MAX(CASE WHEN market_id = 5 AND name = 'Under 4.5' THEN opening_value END) AS odd_open_under_45

FROM game_odds
GROUP BY game_id;
