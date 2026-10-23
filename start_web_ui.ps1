# Flashscore Analytics - React Frontend (Vite)
$ErrorActionPreference = "Stop"
$fe = Join-Path $PSScriptRoot "web\frontend"
Set-Location $fe

if (-not (Test-Path "package.json")) {
    Write-Host "FEHLER: web\frontend nicht gefunden" -ForegroundColor Red
    pause
    exit 1
}

if (-not (Test-Path "node_modules")) {
    Write-Host "npm install (einmalig)..." -ForegroundColor Yellow
    npm install
}

Write-Host "UI:  http://127.0.0.1:5173" -ForegroundColor Cyan
Write-Host "API muss laufen auf http://127.0.0.1:8000" -ForegroundColor Yellow
Write-Host ""

try {
    $busy = Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue
    if ($busy) {
        Write-Host "Port 5173 belegt - beende alten Prozess..." -ForegroundColor Yellow
        $busy | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
        Start-Sleep -Seconds 1
    }
}
catch {
    # Port-Check optional
}

$npmCmd = Get-Command npm.cmd -ErrorAction SilentlyContinue
if (-not $npmCmd) { $npmCmd = Get-Command npm -ErrorAction SilentlyContinue }
if (-not $npmCmd) {
    Write-Host "FEHLER: npm nicht gefunden. Node.js installieren und PATH pruefen." -ForegroundColor Red
    pause
    exit 1
}

& $npmCmd.Source run dev -- --host 127.0.0.1 --port 5173
if ($LASTEXITCODE -ne 0) {
    Write-Host 'UI-Start fehlgeschlagen. Pruefe Node.js und: npm -v' -ForegroundColor Red
    pause
}
