# Flashscore Web UI

Modernes Frontend (React) + Backend (FastAPI). Die bestehende **Tkinter-GUI** bleibt unverändert (`python main.py --gui`).

## Start

```powershell
# Einmalig
pip install -r requirements.txt
cd web\frontend
npm install
cd ..\..

# Beide starten
.\start_web.ps1
```

Oder getrennt:

```powershell
.\start_web_api.ps1   # http://127.0.0.1:8000
.\start_web_ui.ps1    # http://127.0.0.1:5173
```

API-Docs: http://127.0.0.1:8000/docs

## Endpoints

| Route | Beschreibung |
|-------|--------------|
| `GET /api/health` | Status |
| `GET /api/leagues` | Liga-Übersicht + Over-Stats |
| `GET /api/european` | CL / EL / Conference inkl. Phasen |
| `GET /api/leagues/{id}?phase=` | Detail + Chart-Serie + heutige offene Spiele |
| `GET /api/today` | Offene Spiele heute je Liga |

## Architektur

```
Python Domänenlogik (services/)  →  FastAPI (web/backend/)  →  React (web/frontend/)
```
