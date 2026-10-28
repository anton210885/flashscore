from config import config as cfg
from api.sstats_client import SStatsClient

client = SStatsClient(cfg.BASE_URL, cfg.API_KEY)
raw = client.get_games({"Today": True, "TimeZone": cfg.timezone_offset()}) or []
ns = [
    i
    for i in raw
    if isinstance(i, dict) and "not started" in str(i.get("statusName") or "").lower() and i.get("odds")
]
print("ns with odds", len(ns))
if ns:
    markets = ns[0].get("odds") or []
    for m in markets:
        print("market", m.get("marketId"), m.get("marketName"), [(o.get("name"), o.get("value")) for o in (m.get("odds") or [])[:8]])
