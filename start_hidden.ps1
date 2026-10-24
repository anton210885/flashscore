# Startet die API (inkl. fertiger UI + Live-Pipeline) ohne Fenster.
# Aufruf ueber start_hidden.vbs; Ausgaben -> logs\uvicorn.log / logs\uvicorn.log.err
# -NoBrowser: Browser nicht oeffnen (Autostart bei Anmeldung)
param([switch]$NoBrowser)
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
Set-Location $root

$url = "http://127.0.0.1:8000"
# 0.0.0.0 = auch im Heimnetz erreichbar (iPhone: http://<PC-IP>:8000). Nur dieser PC: FLASHSCORE_HOST=127.0.0.1
$listenHost = if ($env:FLASHSCORE_HOST) { $env:FLASHSCORE_HOST } else { "0.0.0.0" }
$logDir = Join-Path $root "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Show-Error([string]$msg) {
    (New-Object -ComObject WScript.Shell).Popup($msg, 0, "Flashscore", 16) | Out-Null
}

function Test-Api {
    try {
        return (Invoke-WebRequest "$url/api/health" -UseBasicParsing -TimeoutSec 3).StatusCode -eq 200
    } catch {
        return $false
    }
}

if (-not (Test-Path (Join-Path $root "data\flashscore.db"))) {
    Show-Error "Datenbank fehlt: data\flashscore.db"
    exit 1
}

if (-not (Test-Api)) {
    $python = (Get-Command python -ErrorAction SilentlyContinue).Source
    if (-not $python) {
        Show-Error "Python nicht gefunden (PATH pruefen)."
        exit 1
    }
    $env:PYTHONUNBUFFERED = "1"
    Start-Process -FilePath $python `
        -ArgumentList "-m", "uvicorn", "web.backend.app:app", "--host", $listenHost, "--port", "8000", "--ws", "none" `
        -WorkingDirectory $root -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $logDir "uvicorn.log") `
        -RedirectStandardError (Join-Path $logDir "uvicorn.log.err")

    # Start kann je nach Rechner bis ~1 Minute dauern
    $ready = $false
    for ($i = 0; $i -lt 90; $i++) {
        if (Test-Api) { $ready = $true; break }
        Start-Sleep -Seconds 2
    }
    if (-not $ready) {
        Show-Error "API startet nicht. Details: logs\uvicorn.log.err"
        exit 1
    }
}

if (-not $NoBrowser) {
    Start-Process $url
}
