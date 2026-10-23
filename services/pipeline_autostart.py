"""Startet die Live-Pipeline im Hintergrund (mit der Web-API).

Verhindert Doppel-Instanzen per Lock-Datei. Stoppt sauber beim API-Shutdown.
"""
from __future__ import annotations

import os
import threading
import time
from typing import Any, Optional

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LOCK_PATH = os.path.join(ROOT, "logs", "live_pipeline.lock")
STATUS_PATH = os.path.join(ROOT, "logs", "live_pipeline_status.json")

_lock = threading.Lock()
_thread: Optional[threading.Thread] = None
_pipe: Any = None
_lock_fh: Any = None
_started_by_us = False


def _try_acquire_lock() -> bool:
    """Exklusives Lock (Windows/POSIX). False = andere Pipeline läuft schon."""
    global _lock_fh
    os.makedirs(os.path.dirname(LOCK_PATH), exist_ok=True)
    try:
        fh = open(LOCK_PATH, "a+", encoding="utf-8")
        try:
            if os.name == "nt":
                import msvcrt

                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            fh.close()
            return False
        fh.seek(0)
        fh.truncate()
        fh.write(str(os.getpid()))
        fh.flush()
        _lock_fh = fh
        return True
    except Exception:
        return False


def _release_lock() -> None:
    global _lock_fh
    fh = _lock_fh
    _lock_fh = None
    if fh is None:
        return
    try:
        if os.name == "nt":
            import msvcrt

            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    except Exception:
        pass
    try:
        fh.close()
    except Exception:
        pass


def _run_pipeline() -> None:
    global _pipe
    try:
        from api.sstats_client import SStatsClient
        from config import config as cfg
        from database import DatabaseManager
        from services.live_pipeline_service import LivePipelineService

        db = DatabaseManager(os.path.join(ROOT, "data", "flashscore.db"))
        try:
            db.get_connection().execute("PRAGMA busy_timeout = 30000")
        except Exception:
            pass
        client = SStatsClient(base_url=cfg.BASE_URL, api_key=getattr(cfg, "API_KEY", None))
        _pipe = LivePipelineService(
            client,
            db,
            sync_interval=180,
            odds_interval=900,
            enrich_interval=600,
            catchup_interval=600,
            catchup_leagues_per_tick=3,
            status_path=STATUS_PATH,
            log=lambda m: print(f"[pipeline] {m}", flush=True),
        )
        _pipe.run_forever()
    except Exception as e:
        print(f"[pipeline] Abbruch: {e}", flush=True)
    finally:
        _pipe = None
        _release_lock()


def start_background_pipeline(*, enabled: Optional[bool] = None) -> dict:
    """Startet Daemon-Thread einmalig. env FLASHSCORE_PIPELINE=0 zum Abschalten."""
    global _thread, _started_by_us
    if enabled is None:
        flag = (os.environ.get("FLASHSCORE_PIPELINE") or "1").strip().lower()
        enabled = flag not in ("0", "false", "off", "no")
    if not enabled:
        return {"ok": False, "started": False, "reason": "disabled"}

    with _lock:
        if _thread is not None and _thread.is_alive():
            return {"ok": True, "started": False, "reason": "already_running_in_process"}
        if not _try_acquire_lock():
            return {"ok": True, "started": False, "reason": "another_instance_holds_lock"}
        _thread = threading.Thread(target=_run_pipeline, name="live-pipeline", daemon=True)
        _thread.start()
        _started_by_us = True
        # kurz warten, ob Thread sofort crasht
        time.sleep(0.3)
        alive = _thread.is_alive()
        return {"ok": True, "started": alive, "reason": "started" if alive else "thread_died"}


def stop_background_pipeline() -> dict:
    """Stoppt die von uns gestartete Pipeline (API-Shutdown)."""
    global _pipe, _started_by_us
    with _lock:
        if not _started_by_us:
            return {"ok": True, "stopped": False, "reason": "not_ours"}
        pipe = _pipe
        if pipe is not None:
            try:
                pipe.stop()
            except Exception:
                pass
        _started_by_us = False
        return {"ok": True, "stopped": True}


def pipeline_status_brief() -> dict:
    running_thread = _thread is not None and _thread.is_alive()
    status: dict = {"thread_alive": running_thread, "started_by_api": _started_by_us}
    try:
        if os.path.exists(STATUS_PATH):
            import json

            with open(STATUS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            status["file_running"] = bool(data.get("running"))
            status["updated_at"] = data.get("updated_at")
            status["jobs"] = data.get("jobs")
    except Exception:
        pass
    return status
