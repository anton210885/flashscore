# Opening-Odds Backfill (parallel zu Glicko möglich)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
New-Item -ItemType Directory -Force -Path (Join-Path $Root "logs") | Out-Null
$Log = Join-Path $Root "logs\backfill_opening.log"
$env:PYTHONUNBUFFERED = "1"
Write-Host "Opening-Odds Backfill → $Log"
python -u scripts/backfill_opening_odds.py --prefer-glicko @args *>> $Log
