"""Gespeicherte Strategie-Filter (Presets) auf dem Server — unabhängig von Browser und Adresse.

Vorher nur im localStorage des Browsers; der gilt pro Adresse (:5173 vs. :8000).
"""
from __future__ import annotations

import json
import os
import threading
from typing import Any, Dict, List

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PRESETS_PATH = os.path.join(ROOT, "data", "strategy_presets.json")

_lock = threading.Lock()


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
        tmp = PRESETS_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(clean, f, ensure_ascii=False, indent=2)
        os.replace(tmp, PRESETS_PATH)
    return clean
