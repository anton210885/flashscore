# Backfill missing Glicko/xG into data/flashscore.db
# Logs to logs/backfill_glicko.log — safe to re-run (skips existing rows).

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

New-Item -ItemType Directory -Force -Path (Join-Path $Root "logs") | Out-Null
$Log = Join-Path $Root "logs\backfill_glicko.log"

Write-Host "Starting Glicko backfill..."
Write-Host "Log: $Log"
Write-Host "Stop: Ctrl+C in this window, or close the process."

$env:PYTHONUNBUFFERED = "1"
python -u scripts/backfill_glicko.py @args *>> $Log
Write-Host "Finished. See $Log"
