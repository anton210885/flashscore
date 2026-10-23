"""Live tab (UI stub)
"""


def build_live_tab(live_service=None):
    """Return a representation of the Live tab.

    If `live_service` is provided it will fetch live matches and render a table.
    """
    tab = {"name": "Live", "icon": "🔴"}
    if live_service is None:
        tab["content"] = "No live service configured"
        return tab

    games = live_service.fetch_live_games()
    try:
        from ui.widgets.tables import render_games_table
    except Exception:
        # fallback local import in case of package layout differences
        from ..widgets.tables import render_games_table

    tab["table"] = render_games_table(games)
    return tab
