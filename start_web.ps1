# Startet API + React-UI in zwei Fenstern und oeffnet den Browser
$ErrorActionPreference = "Continue"
$root = $PSScriptRoot
if (-not $root) { $root = Get-Location }
Set-Location $root

function Stop-PortListeners {
    param([int[]]$Ports)
    foreach ($port in $Ports) {
        try {
            $conns = @(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
        } catch {
            $conns = @()
        }
        foreach ($c in $conns) {
            $procId = $c.OwningProcess
            if (-not $procId -or $procId -eq 0) { continue }
            try {
                $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
                $name = if ($proc) { $proc.ProcessName } else { "?" }
                Write-Host "Beende alten Prozess auf Port $port (PID $procId, $name) ..." -ForegroundColor Yellow
                Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
            } catch {}
        }
    }
    Start-Sleep -Seconds 1
}

$db = Join-Path $root "data\flashscore.db"
if (-not (Test-Path $db)) {
    Write-Host "FEHLER: data\flashscore.db fehlt." -ForegroundColor Red
    pause
    exit 1
}

Write-Host "Stoppe alte API/UI auf 8000 / 5173 (falls belegt) ..." -ForegroundColor DarkGray
Stop-PortListeners -Ports @(8000, 5173)

$apiScript = Join-Path $root "start_web_api.ps1"
$uiScript = Join-Path $root "start_web_ui.ps1"

Write-Host "Starte API + UI ..." -ForegroundColor Cyan
Write-Host "  (Live-Pipeline startet automatisch mit der API: Sync/Odds/Form2)" -ForegroundColor DarkGray
# cmd /k: Fenster bleibt offen, Fehler sichtbar
Start-Process -FilePath "cmd.exe" -ArgumentList "/k", "cd /d `"$root`" && powershell -NoProfile -ExecutionPolicy Bypass -File `"$apiScript`"" -WorkingDirectory $root
Start-Sleep -Seconds 3
Start-Process -FilePath "cmd.exe" -ArgumentList "/k", "cd /d `"$root`" && powershell -NoProfile -ExecutionPolicy Bypass -File `"$uiScript`"" -WorkingDirectory $root
Start-Sleep -Seconds 5
Start-Process "http://127.0.0.1:5173"

Write-Host ""
Write-Host "Fertig." -ForegroundColor Green
Write-Host "  UI:  http://127.0.0.1:5173" -ForegroundColor Green
Write-Host "  API: http://127.0.0.1:8000/docs" -ForegroundColor Green
Write-Host "  Pipeline: laeuft mit API (Status: /api/health → pipeline)" -ForegroundColor Green
Write-Host "  Abschalten: `$env:FLASHSCORE_PIPELINE='0'` vor API-Start" -ForegroundColor DarkGray
Write-Host "  Tkinter: python main.py --gui" -ForegroundColor DarkGray
Write-Host "Falls Fenster sofort zu: Fehlermeldung darin lesen." -ForegroundColor DarkGray
