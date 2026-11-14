"""Strategie-Builder im Tool: Suche im Hintergrund, Ergebnisse als JSON (logs/strategy_builder/).

Gefundene Kombinationen lassen sich als Strategie (Preset) speichern — dann zeichnet die
Verifikation ab sofort ihre echten Wetten auf (ehrlicher Vorwärts-Test).
"""
from __future__ import annotations

import json
import secrets
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = ROOT / "logs" / "strategy_builder"
MAX_RUNS = 40

_lock = threading.Lock()
_state: Dict[str, Any] = {"running": False, "run_id": None, "started_at": None, "step": None}


def catalog() -> Dict[str, Any]:
    from strategy_builder.search_space import METRICS, ODDS_BANDS

    return {
        "markets": list(ODDS_BANDS),
        "metrics": [{"id": k, "label": v[3], "glicko": v[4]} for k, v in METRICS.items()],
        "bands": {k: [list(b) for b in v] for k, v in ODDS_BANDS.items()},
    }


def _validate(cfg: Dict[str, Any]) -> Dict[str, Any]:
    from strategy_builder.search_space import ODDS_BANDS

    markets = [m for m in cfg.get("markets") or [] if m in ODDS_BANDS] or list(ODDS_BANDS)
    split = cfg.get("split") or None
    if split:
        try:
            split = str(datetime.fromisoformat(str(split)[:10]).date())
        except ValueError:
            raise ValueError("Stichtag ungültig.")
    return {
        "markets": markets,
        "odds_type": "closing" if cfg.get("odds_type") == "closing" else "opening",
        "split": split,
        "min_bets": max(30, min(2000, int(cfg.get("min_bets") or 100))),
        "include_glicko": bool(cfg.get("include_glicko")),
        "scope_only": bool(cfg.get("scope_only")),
        "top_k": max(5, min(50, int(cfg.get("top_k") or 20))),
    }


def _save(run: Dict[str, Any]) -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    tmp = RUNS_DIR / f"{run['id']}.json.tmp"
    tmp.write_text(json.dumps(run, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    tmp.replace(RUNS_DIR / f"{run['id']}.json")
    for f in sorted(RUNS_DIR.glob("*.json"))[:-MAX_RUNS]:
        f.unlink(missing_ok=True)


def _worker(run: Dict[str, Any]) -> None:
    from strategy_builder import run_search

    t0 = time.time()
    try:
        run["result"] = run_search(**run["config"], progress=lambda s: _state.update(step=s))
        run["status"] = "done"
    except ValueError as e:
        run["status"], run["error"] = "error", str(e)
    except Exception as e:  # pragma: no cover
        traceback.print_exc()
        run["status"], run["error"] = "error", f"{type(e).__name__}: {e}"
    run["seconds"] = round(time.time() - t0, 1)
    _save(run)
    with _lock:
        _state.update(running=False, run_id=None, started_at=None, step=None)


def start(cfg: Dict[str, Any]) -> Dict[str, Any]:
    cfg = _validate(cfg)
    with _lock:
        if _state["running"]:
            return {"started": False, "error": "Es läuft schon eine Suche.", "run_id": _state["run_id"]}
        run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
        _state.update(running=True, run_id=run_id, started_at=datetime.now().isoformat(timespec="seconds"),
                      step="Start")
    run = {"id": run_id, "created_at": datetime.now().isoformat(timespec="seconds"), "status": "running",
           "config": cfg}
    threading.Thread(target=_worker, args=(run,), daemon=True, name="strategy-builder").start()
    return {"started": True, "run_id": run_id}


def runs() -> Dict[str, Any]:
    items = []
    if RUNS_DIR.exists():
        for f in sorted(RUNS_DIR.glob("*.json"), reverse=True):
            try:
                r = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            res = r.get("result") or {}
            items.append({
                "id": r["id"], "created_at": r.get("created_at"), "status": r.get("status"),
                "error": r.get("error"), "seconds": r.get("seconds"), "config": r.get("config"),
                "split": res.get("split"), "summary": res.get("summary"),
            })
    return {"running": dict(_state), "runs": items}


def _safe_id(run_id: str) -> bool:
    return run_id.replace("-", "").isdigit()


def get_run(run_id: str) -> Optional[Dict[str, Any]]:
    f = RUNS_DIR / f"{run_id}.json"
    return json.loads(f.read_text(encoding="utf-8")) if _safe_id(run_id) and f.exists() else None


def delete_run(run_id: str) -> bool:
    f = RUNS_DIR / f"{run_id}.json"
    if _safe_id(run_id) and f.exists():
        f.unlink()
        return True
    return False


def save_as_preset(run_id: str, index: int, name: str) -> Dict[str, Any]:
    """Kombination Nr. index eines Laufs als neue Strategie anlegen."""
    from services import strategy_presets_service as presets_svc

    run = get_run(run_id)
    top = ((run or {}).get("result") or {}).get("top") or []
    if not (0 <= index < len(top)):
        raise ValueError("Kombination nicht gefunden.")
    name = (name or "").strip() or f"builder_{top[index]['label']}"[:80]
    presets = presets_svc.load_presets()
    if any(str(p.get("name")).strip() == name for p in presets):
        raise ValueError(f"Es gibt schon eine Strategie „{name}“.")
    preset = {
        "id": f"sb_{secrets.token_hex(5)}",
        "name": name,
        "filters": top[index]["filters"],
        "source": {"builder_run": run_id, "label": top[index]["label"],
                   "train": top[index]["train"], "test": top[index]["test"]},
    }
    presets_svc.save_presets(presets + [preset])
    return {"id": preset["id"], "name": name}
