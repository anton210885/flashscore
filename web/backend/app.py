"""Flashscore Web API – FastAPI Backend."""
from __future__ import annotations

import mimetypes
import os
import subprocess
import sys
import threading
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

# Projektroot auf sys.path, damit services/database importierbar sind
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)

from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response

from database import connect as db_connect, ensure_schema
from services import web_league_service as svc
from services import sstats_catalog_service as catalog_svc
from services import web_games_service as games_svc
from services import web_stats_service as stats_svc
from services import web_strategy_service as strategy_svc
from services import strategy_presets_service as presets_svc
from services import verification_service as verification_svc
from services import ai_settings_service as ai_settings_svc
from services.pipeline_autostart import (
    pipeline_status_brief,
    start_background_pipeline,
    stop_background_pipeline,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # DB-Schema einmal beim Start einrichten — Requests öffnen danach nur noch Verbindungen
    ensure_schema(os.path.join(ROOT, "data", "flashscore.db"))
    # Meisterschaften/Upcoming/Odds/Form2 automatisch laden, solange API läuft
    info = start_background_pipeline()
    print(f"[api] live-pipeline: {info}", flush=True)
    try:
        yield
    finally:
        stop_background_pipeline()


app = FastAPI(
    title="Flashscore Analytics API",
    version="1.0.0",
    description="Backend für das React-Frontend. Tkinter-GUI bleibt parallel nutzbar.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Windows-Registry liefert für .js oft text/plain — Browser führen das Modul dann nicht aus
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("image/svg+xml", ".svg")
mimetypes.add_type("application/manifest+json", ".webmanifest")

FRONTEND_DIST = os.path.join(ROOT, "web", "frontend", "dist")
FRONTEND_INDEX = os.path.join(FRONTEND_DIST, "index.html")


@app.get("/", include_in_schema=False)
def root():
    """Gebaute UI ausliefern; ohne Build Hinweis auf Vite (:5173)."""
    if os.path.isfile(FRONTEND_INDEX):
        return FileResponse(FRONTEND_INDEX)
    return {
        "message": "Flashscore API läuft. UI fehlt: build_ui.bat ausführen oder Vite unter http://127.0.0.1:5173 nutzen.",
        "docs": "http://127.0.0.1:8000/docs",
        "health": "/api/health",
    }


def _git(*args: str) -> str:
    try:
        out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=5)
        return out.stdout.strip() if out.returncode == 0 else ""
    except Exception:
        return ""


# Version beim API-Start aus Git: letzter Tag + Commits danach + Commit-ID, z. B. v1.0.0-17-g28d20ca
APP_VERSION = {
    "version": _git("describe", "--tags", "--always") or "unbekannt",
    "commit_date": _git("log", "-1", "--format=%cd", "--date=format:%Y-%m-%d %H:%M"),
}


@app.get("/api/health")
def health():
    db_path = os.path.join(ROOT, "data", "flashscore.db")
    return {
        "ok": True,
        "db": "data/flashscore.db",
        "db_exists": os.path.exists(db_path),
        "db_size_mb": round(os.path.getsize(db_path) / (1024 * 1024), 1) if os.path.exists(db_path) else 0,
        "pipeline": pipeline_status_brief(),
        **APP_VERSION,
    }


@app.get("/api/leagues")
def leagues(
    limit: Optional[int] = Query(None, ge=1, le=500),
    years: Optional[str] = Query(None, description="Komma-getrennte Jahre, z.B. 2022,2023,2024,2025,2026"),
    group: str = Query(
        "meisterschaften",
        description="meisterschaften | liga128 | european",
    ),
):
    year_list = [y.strip() for y in years.split(",") if y.strip()] if years else None
    try:
        g = (group or "meisterschaften").strip().lower()
        if g in ("liga128", "liga_128", "calendar", "kalender"):
            return svc.liga128_overview(years=year_list, limit=limit)
        if g in ("european", "euro", "uefa"):
            return svc.european_overview()
        return svc.overview(years=year_list, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/leagues/liga128")
def leagues_liga128(
    limit: Optional[int] = Query(None, ge=1, le=500),
    years: Optional[str] = Query(None),
):
    year_list = [y.strip() for y in years.split(",") if y.strip()] if years else None
    try:
        return svc.liga128_overview(years=year_list, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/european")
def european():
    try:
        return svc.european_overview()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/leagues/{league_id}")
def league_detail(
    league_id: int,
    phase: str = Query("all"),
    year: Optional[int] = Query(None, description="Saisonjahr für Spieleliste (beendet)"),
):
    try:
        return svc.league_detail(league_id, phase=phase, year=year)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/leagues/{league_id}/sync")
def league_sync(
    league_id: int,
    year: Optional[int] = Query(None, description="Saisonjahr (default aktuelle Saison)"),
):
    """Fehlende beendete Spiele dieser Liga von der API nachladen."""
    try:
        return svc.sync_league_season(league_id, year=year)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/today")
def today_counts():
    try:
        counts = svc.today_pending_counts()
        return {"counts": {str(k): v for k, v in counts.items()}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/stats")
def db_stats(top: int = Query(12, ge=1, le=50)):
    try:
        return stats_svc.get_stats(top_n=top)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/strategy/analyze")
def strategy_analyze(
    filters: Dict[str, Any] = Body(...),
    limit: int = Query(200, ge=1, le=1000),
):
    """Strategie-Backtest (Glicko xG, Saison-Spielnr., Opening/Closing, …)."""
    try:
        return strategy_svc.analyze(filters or {}, limit_results=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/strategy/upcoming")
def strategy_upcoming(
    filters: Dict[str, Any] = Body(...),
    limit: int = Query(200, ge=1, le=1000),
):
    """Bevorstehende Spiele zu aktuellen Strategie-Filtern (+ Open/Close/xROI)."""
    try:
        return strategy_svc.find_upcoming(filters or {}, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/strategy/metric-rank")
def strategy_metric_rank(
    filters: Dict[str, Any] = Body(...),
    min_n: int = Query(40, ge=10, le=500),
    sort_by: str = Query("roi", description="roi | profit"),
):
    """Metric-Korrelation: Ranking nach Δ ROI oder Δ Profit vs. Baseline."""
    try:
        return strategy_svc.metric_rank(filters or {}, min_n=min_n, sort_by=sort_by)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/strategy/metric-buckets")
def strategy_metric_buckets(
    filters: Dict[str, Any] = Body(...),
    metric: str = Query("rating_diff"),
    vmin: Optional[float] = Query(None),
    vmax: Optional[float] = Query(None),
    step: Optional[float] = Query(None, gt=0),
    bins: int = Query(16, ge=4, le=40),
):
    """Parameter-Grafik: Profit/ROI je Metrik-Bin (Auto-Range oder Min/Max/Step)."""
    try:
        return strategy_svc.metric_buckets(
            filters or {},
            metric=metric,
            vmin=vmin,
            vmax=vmax,
            step=step,
            target_bins=bins,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/strategy/optimize-params")
def strategy_optimize_params(
    filters: Dict[str, Any] = Body(...),
    min_n: int = Query(25, ge=5, le=200),
    max_params: int = Query(2, ge=1, le=2),
    top_k: int = Query(15, ge=1, le=40),
):
    """Sucht max. 2 vordefinierte Parameter (inkl. Quote) mit höchstem Profit."""
    try:
        return strategy_svc.optimize_params(
            filters or {},
            min_n=min_n,
            max_params=max_params,
            top_k=top_k,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/strategy/presets")
def strategy_presets():
    """Gespeicherte Strategie-Filter (data/strategy_presets.json)."""
    return {"presets": presets_svc.load_presets()}


@app.get("/api/verification")
def verification(strategy_id: Optional[str] = Query(None)):
    """Verifikation: festgehaltene Strategie-Treffer + Zusammenfassung pro Strategie."""
    conn = db_connect(os.path.join(ROOT, "data", "flashscore.db"))
    try:
        return verification_svc.report(
            conn, strategy_id=strategy_id, presets=presets_svc.load_presets()
        )
    finally:
        conn.close()


@app.post("/api/verification/placed")
def verification_placed(body: Dict[str, Any] = Body(...)):
    """Wette als bei Swisslos gesetzt markieren: {bet_id, odds, stake, note?}."""
    conn = db_connect(os.path.join(ROOT, "data", "flashscore.db"))
    try:
        verification_svc.set_placed(conn, body.get("bet_id"), body.get("odds"), body.get("stake"), body.get("note"))
        return {"ok": True}
    except (TypeError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    finally:
        conn.close()


@app.delete("/api/verification/placed/{bet_id}")
def verification_unplaced(bet_id: int):
    conn = db_connect(os.path.join(ROOT, "data", "flashscore.db"))
    try:
        verification_svc.unset_placed(conn, bet_id)
        return {"ok": True}
    finally:
        conn.close()


@app.post("/api/verification/scan")
def verification_scan():
    """Jetzt prüfen: bevorstehende Treffer aller Strategien eintragen + Ergebnisse abrechnen."""
    conn = db_connect(os.path.join(ROOT, "data", "flashscore.db"))
    try:
        stats = verification_svc.record_upcoming(conn, presets_svc.load_presets())
        stats["settled"] = verification_svc.settle(conn)["settled"]
        return {"ok": True, **stats}
    finally:
        conn.close()


@app.post("/api/strategy/presets/upcoming")
def strategy_presets_upcoming(body: Dict[str, Any] = Body(...)):
    """Bevorstehende Spiele aller übergebenen Strategien + aktuelle Siegen-/Niederlagen-Serie."""
    try:
        return strategy_svc.presets_upcoming(body.get("presets") or [])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/strategy/presets")
def strategy_presets_save(body: Dict[str, Any] = Body(...)):
    """Komplette Preset-Liste speichern (ersetzt den bisherigen Stand).

    Neue oder geänderte Strategien werden sofort im Hintergrund für die Verifikation
    geprüft — sonst erst beim nächsten stündlichen Lauf der Pipeline.
    """
    before = {p.get("id"): p.get("filters") for p in presets_svc.load_presets()}
    try:
        saved = presets_svc.save_presets(body.get("presets"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    changed = [p for p in saved if p.get("id") not in before or before[p["id"]] != p.get("filters")]
    if changed:
        threading.Thread(target=_verification_scan_presets, args=(changed,), daemon=True).start()
    return {"presets": saved}


def _verification_scan_presets(presets: Any) -> None:
    conn = db_connect(os.path.join(ROOT, "data", "flashscore.db"))
    try:
        verification_svc.record_upcoming(conn, presets)
    except Exception as e:
        print(f"[verification] Scan neuer Strategien fehlgeschlagen: {e}", flush=True)
    finally:
        conn.close()


@app.get("/api/games")
def games_list(
    status: str = Query("all", description="all | live | finished | not_started"),
    date_from: Optional[str] = Query(None, description="YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="YYYY-MM-DD"),
    q: Optional[str] = Query(None, description="Suche Team/Liga"),
    limit: int = Query(100, ge=1, le=300),
    offset: int = Query(0, ge=0),
    pinnacle: bool = Query(False, description="Pinnacle-Quoten live nachladen"),
):
    try:
        return games_svc.list_games(
            status=status,
            date_from=date_from,
            date_to=date_to,
            q=q,
            limit=limit,
            offset=offset,
            pinnacle=pinnacle,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/games/{game_id}/odds/pinnacle")
def game_pinnacle_odds(game_id: int):
    try:
        return {"game_id": game_id, **games_svc.fetch_pinnacle_odds(game_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/sstats/catalog")
def sstats_catalog(
    live: bool = Query(True, description="Live-Stichprobe von der API laden"),
    game_id: Optional[int] = Query(None, description="Optionale Game-ID für Sample"),
    save: bool = Query(False, description="Zusätzlich JSON/CSV nach data/ schreiben"),
):
    try:
        catalog = catalog_svc.build_catalog(live=live, game_id=game_id)
        if save:
            catalog["saved"] = catalog_svc.save_catalog_files(catalog)
        return catalog
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/sstats/catalog.csv")
def sstats_catalog_csv(
    live: bool = Query(True),
    game_id: Optional[int] = Query(None),
):
    try:
        catalog = catalog_svc.build_catalog(live=live, game_id=game_id)
        csv_text = catalog_svc.catalog_to_csv(catalog)
        return Response(
            content=csv_text,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=sstats_parameters.csv"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/sstats/catalog.json")
def sstats_catalog_json_download(
    live: bool = Query(True),
    game_id: Optional[int] = Query(None),
):
    try:
        import json

        catalog = catalog_svc.build_catalog(live=live, game_id=game_id)
        body = json.dumps(catalog, ensure_ascii=False, indent=2, default=str)
        return Response(
            content=body,
            media_type="application/json; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=sstats_parameters.json"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/settings/ai")
def settings_ai_get():
    """Status OpenAI-Key (nur maskiert) + Modell."""
    try:
        return ai_settings_svc.settings_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/settings/ai")
def settings_ai_save(body: Dict[str, Any] = Body(default_factory=dict)):
    """OPENAI_API_KEY / OPENAI_MODEL in .env speichern."""
    try:
        api_key = body.get("api_key")
        model = body.get("model")
        if api_key is None and model is None:
            raise HTTPException(status_code=400, detail="api_key oder model erforderlich.")
        return ai_settings_svc.save_openai_settings(
            api_key=api_key if api_key is not None else None,
            model=model if model is not None else None,
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.delete("/api/settings/ai/key")
def settings_ai_clear_key():
    try:
        return ai_settings_svc.clear_openai_api_key()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/settings/ai/env-export")
def settings_ai_env_export():
    """Lädt eine .env-Vorlage herunter — nur den Key einfügen."""
    try:
        body = ai_settings_svc.env_export_template(include_placeholder_key=True)
        return Response(
            content=body,
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=.env"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


# ── Gebaute UI (muss nach allen API-Routen stehen) ────────────────────────


@app.get("/{full_path:path}", include_in_schema=False)
def frontend(full_path: str):
    """Dateien aus dist/ ausliefern, sonst index.html (React-Router-Unterseiten wie /stats)."""
    if full_path.startswith("api/") or not os.path.isfile(FRONTEND_INDEX):
        raise HTTPException(status_code=404, detail="Not Found")
    candidate = os.path.normpath(os.path.join(FRONTEND_DIST, full_path))
    if candidate.startswith(FRONTEND_DIST + os.sep) and os.path.isfile(candidate):
        return FileResponse(candidate)
    return FileResponse(FRONTEND_INDEX)
