"""Konfiguration — Secrets kommen aus der Prozess-Umgebung oder der .env im Projektroot."""
import os
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ENV_PATH = os.path.join(ROOT, ".env")


def _load_env_file(path: str = ENV_PATH) -> None:
    """Minimaler .env-Loader: KEY=VALUE pro Zeile; bereits gesetzte Prozess-Variablen gewinnen."""
    if not os.path.isfile(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key, value = key.strip(), value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                value = value[1:-1]
            os.environ.setdefault(key, value)


_load_env_file()

API_KEY = os.environ.get("SSTATS_API_KEY") or None
BASE_URL = os.environ.get("SSTATS_BASE_URL") or "https://api.sstats.net"
# Feste Stunden-Verschiebung nur, wenn TIMEZONE gesetzt ist — sonst Schweizer Zeit inkl. Sommer-/Winterzeit
_TZ_FIXED = os.environ.get("TIMEZONE")
LOCAL_TZ = ZoneInfo("Europe/Zurich")


def timezone_offset() -> int:
    """Aktuelle Verschiebung zu UTC in Stunden (Winter 1, Sommer 2) — pro Aufruf, nicht beim Start."""
    if _TZ_FIXED:
        return int(_TZ_FIXED)
    return int(datetime.now(LOCAL_TZ).utcoffset().total_seconds() // 3600)


# Stand beim Import — für Code, der nur einen festen Wert lesen kann; besser timezone_offset()
TIMEZONE = timezone_offset()
