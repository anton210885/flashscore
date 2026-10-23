# Startet Glicko-, Opening- und Closing-Odds-Backfill parallel (drei Prozesse)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
New-Item -ItemType Directory -Force -Path (Join-Path $Root "logs") | Out-Null

$env:PYTHONUNBUFFERED = "1"
$gLog = Join-Path $Root "logs\backfill_glicko.log"
$oLog = Join-Path $Root "logs\backfill_opening.log"
$cLog = Join-Path $Root "logs\backfill_closing.log"

Write-Host "Starte Glicko  → $gLog"
$g = Start-Process -FilePath python -ArgumentList "-u","scripts/backfill_glicko.py","--delay","0.5","--progress-every","50" `
  -WorkingDirectory $Root -RedirectStandardOutput $gLog -RedirectStandardError "$gLog.err" -WindowStyle Hidden -PassThru

Write-Host "Starte Opening → $oLog"
$o = Start-Process -FilePath python -ArgumentList "-u","scripts/backfill_opening_odds.py","--delay","0.4","--prefer-glicko","--progress-every","50" `
  -WorkingDirectory $Root -RedirectStandardOutput $oLog -RedirectStandardError "$oLog.err" -WindowStyle Hidden -PassThru

Write-Host "Starte Closing → $cLog"
$c = Start-Process -FilePath python -ArgumentList "-u","scripts/backfill_closing_odds.py","--delay","0.45","--prefer-glicko","--progress-every","50" `
  -WorkingDirectory $Root -RedirectStandardOutput $cLog -RedirectStandardError "$cLog.err" -WindowStyle Hidden -PassThru

Write-Host "PIDs: glicko=$($g.Id) opening=$($o.Id) closing=$($c.Id)"
Write-Host "Fortschritt: DB Statistik in der Web-UI (Auto 15s)"
