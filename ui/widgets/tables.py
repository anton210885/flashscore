"""Table widgets (simple textual renderer)
"""


def render_games_table(games):
    """Render a simple text table for a list of game objects or dicts.

    Returns a string suitable for printing in a console or CLI preview.
    """
    if not games:
        return "(keine Live-Spiele)"

    # Determine rows
    rows = []
    header = f"{'ID':>4}  {'Country':12}  {'League':20}  {'Home':16}  {'Away':16}  {'Score':9}  {'Status'}"
    rows.append(header)
    rows.append('-' * len(header))
    for g in games:
        # support dataclass-like objects or dicts
        gid = getattr(g, 'id', None) or (g.get('id') if isinstance(g, dict) else '')
        home = getattr(g, 'home_team', None) or (g.get('home_team') if isinstance(g, dict) else '')
        away = getattr(g, 'away_team', None) or (g.get('away_team') if isinstance(g, dict) else '')
        sh = getattr(g, 'score_home', None) or (g.get('score_home') if isinstance(g, dict) else 0)
        sa = getattr(g, 'score_away', None) or (g.get('score_away') if isinstance(g, dict) else 0)
        status = getattr(g, 'status_text', None) or getattr(g, 'status', None) or (g.get('status_text') if isinstance(g, dict) else g.get('status', ''))
        league = getattr(g, 'league_name', None) or (g.get('league_name') if isinstance(g, dict) else '')
        country = getattr(g, 'country', None) or (g.get('country') if isinstance(g, dict) else '')
        score = f"{sh}-{sa}"
        rows.append(f"{str(gid):>4}  {country:12.12}  {league:20.20}  {home:16.16}  {away:16.16}  {score:9}  {status}")

    return "\n".join(rows)
