# Flashscore Analytics - FastAPI Backend
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$db = Join-Path $PSScriptRoot "data\flashscore.db"
if (-not (Test-Path $db)) {
    Write-Host "FEHLER: Datenbank fehlt: data\flashscore.db" -ForegroundColor Red
    Write-Host "Die App braucht die lokale SQLite-Datei (kein extra DB-Server)." -ForegroundColor Yellow
    pause
    exit 1
}

Write-Host "DB OK: $db ($([math]::Round((Get-Item $db).Length/1MB,1)) MB)" -ForegroundColor Green
Write-Host "API:  http://127.0.0.1:8000" -ForegroundColor Cyan
Write-Host "Docs: http://127.0.0.1:8000/docs" -ForegroundColor Cyan
Write-Host "Live-Pipeline startet mit der API (Sync/Odds/Form2)." -ForegroundColor Green
Write-Host "UI separat starten (start_web_ui.ps1) -> http://127.0.0.1:5173" -ForegroundColor Yellow
Write-Host ""

try {
    $busy = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
    if ($busy) {
        Write-Host "Port 8000 belegt - beende alten Prozess..." -ForegroundColor Yellow
        $busy | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
        Start-Sleep -Seconds 1
    }
}
catch {
    # Port-Check optional
}

# --ws none: vermeidet Konflikte mit aelteren websockets-Paketen
# ohne --reload: stabiler unter Windows / parallelen Backfills
python -m uvicorn web.backend.app:app --host 127.0.0.1 --port 8000 --ws none
if ($LASTEXITCODE -ne 0) {
    Write-Host "API-Start fehlgeschlagen." -ForegroundColor Red
    Write-Host '  - Port 8000 frei?  netstat -ano | findstr :8000' -ForegroundColor Yellow
    Write-Host "  - Pakete: pip install fastapi uvicorn" -ForegroundColor Yellow
    pause
}
