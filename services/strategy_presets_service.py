"""Gespeicherte Strategie-Filter (Presets) auf dem Server — unabhängig von Browser und Adresse.

Vorher nur im localStorage des Browsers; der gilt pro Adresse (:5173 vs. :8000).
"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PRESETS_PATH = os.path.join(ROOT, "data", "strategy_presets.json")

_lock = threading.Lock()

# Felder, die nur zählen, wenn ihr Schalter an ist (sonst ändert sich am Ergebnis nichts)
_GROUPS = {
    "use_xg_comparison": (
        "xg_attr1", "xg_operation", "xg_attr2", "xg_comparison_operator",
        "xg_comparison_value", "xg_comparisons",
    ),
    "use_percentile": ("percentile_value", "percentile_metric"),
}


def effective_filters(filters: Any) -> Dict[str, Any]:
    """Filter ohne leere Felder und ohne Felder abgeschalteter Gruppen — zum Vergleichen."""
    f = {k: v for k, v in (filters or {}).items() if v not in ("", None, [], {})}
    for switch, keys in _GROUPS.items():
        if not f.get(switch):
            f.pop(switch, None)
            for k in keys:
                f.pop(k, None)
    return f


def filter_changes(old: Any, new: Any) -> List[Dict[str, Any]]:
    """Geänderte Filter: [{key, old, new}] — fehlend = None."""
    a, b = effective_filters(old), effective_filters(new)
    return [
        {"key": k, "old": a.get(k), "new": b.get(k)}
        for k in sorted(set(a) | set(b))
        if a.get(k) != b.get(k)
    ]


def _with_version(p: Dict[str, Any], old: Optional[Dict[str, Any]], now: str) -> Dict[str, Any]:
    """Version/Änderungsverlauf vom Server führen — was der Browser schickt, zählt nicht."""
    p = dict(p)
    if old is None:
        p["version"], p["versionAt"], p["history"] = 1, now, []
        return p
    version = int(old.get("version") or 1)
    history = list(old.get("history") or [])
    version_at = old.get("versionAt")
    changes = filter_changes(old.get("filters"), p.get("filters"))
    if changes:
        version += 1
        version_at = now
        history.append({"version": version, "at": now, "changes": changes})
    p["version"], p["versionAt"], p["history"] = version, version_at, history
    return p


def load_presets() -> List[Dict[str, Any]]:
    if not os.path.isfile(PRESETS_PATH):
        return []
    with open(PRESETS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else []


def save_presets(presets: Any) -> List[Dict[str, Any]]:
    """Ersetzt die komplette Liste (der Browser schickt immer den Gesamtstand)."""
    if not isinstance(presets, list):
        raise ValueError("presets muss eine Liste sein.")
    clean = [
        p for p in presets
        if isinstance(p, dict) and p.get("id") and str(p.get("name") or "").strip()
    ]
    with _lock:
        before = {p.get("id"): p for p in load_presets()}
        now = datetime.now().isoformat(timespec="seconds")
        clean = [_with_version(p, before.get(p["id"]), now) for p in clean]
        tmp = PRESETS_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(clean, f, ensure_ascii=False, indent=2)
        os.replace(tmp, PRESETS_PATH)
    return clean
