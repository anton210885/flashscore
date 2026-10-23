# Closing-Odds Backfill (parallel zu Glicko/Opening möglich)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
New-Item -ItemType Directory -Force -Path (Join-Path $Root "logs") | Out-Null
$Log = Join-Path $Root "logs\backfill_closing.log"
$env:PYTHONUNBUFFERED = "1"
Write-Host "Closing-Odds Backfill → $Log"
python -u scripts/backfill_closing_odds.py --prefer-glicko @args *>> $Log
