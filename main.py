"""FlashscoreTool Entry Point (CLI demo for Live tab)
"""
from sys import argv

from config import config as cfg


def main():
    # CLI demo kept for backward compatibility.
    if "--gui" in argv:
        try:
            from ui.main_window import run_gui
        except Exception as e:
            print("GUI kann nicht gestartet werden:", e)
            return
        run_gui()
        return

    # Default: simple CLI output of live games
    from api.sstats_client import SStatsClient
    from services.live_service import LiveService
    from ui.tabs.live_tab import build_live_tab

    print("FlashscoreTool gestartet (Live-Tab Demo)")
    client = SStatsClient(base_url=cfg.BASE_URL, api_key=getattr(cfg, 'API_KEY', None))
    live_service = LiveService(client)
    tab = build_live_tab(live_service)
    table = tab.get("table")
    if table:
        print(table)
    else:
        print(tab.get("content") or tab)


if __name__ == "__main__":
    main()
