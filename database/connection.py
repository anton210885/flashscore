"""Leichte SQLite-Verbindungen für Lesezugriffe (Web-API).

Das Schema (schema.sql, Odds-View, Form2, upcoming_games) richtet
`DatabaseManager` ein — das kostet DDL + Schreibsperre und passiert hier
nur einmal pro Prozess statt bei jeder Anfrage.
"""
from __future__ import annotations

import os
import sqlite3
import threading
from typing import Optional, Set

_ready: Set[str] = set()
_lock = threading.Lock()


def ensure_schema(db_path: str) -> None:
    """Schema einmal pro Prozess und Datenbankdatei einrichten."""
    key = os.path.abspath(db_path)
    if key in _ready:
        return
    with _lock:
        if key in _ready:
            return
        from .db_manager import DatabaseManager

        DatabaseManager(key).close()
        _ready.add(key)


def connect(
    db_path: str,
    *,
    row_factory: Optional[type] = sqlite3.Row,
    foreign_keys: bool = True,
    busy_timeout_ms: int = 15000,
) -> sqlite3.Connection:
    """Neue Verbindung ohne Schema-Arbeit (WAL ist in der Datei bereits gesetzt)."""
    ensure_schema(db_path)
    conn = sqlite3.connect(str(db_path), timeout=busy_timeout_ms / 1000)
    if row_factory is not None:
        conn.row_factory = row_factory
    conn.execute(f"PRAGMA busy_timeout = {int(busy_timeout_ms)}")
    if foreign_keys:
        conn.execute("PRAGMA foreign_keys = ON")
    return conn
