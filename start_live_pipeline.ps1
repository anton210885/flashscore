# Live-Pipeline Daemon (Sync + Odds + Post-match xG)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
New-Item -ItemType Directory -Force -Path (Join-Path $Root "logs") | Out-Null
$Log = Join-Path $Root "logs\live_pipeline.log"
$env:PYTHONUNBUFFERED = "1"
Write-Host "Live-Pipeline → $Log"
Write-Host "Status JSON: logs\live_pipeline_status.json (auch in DB Statistik)"
python -u scripts/run_live_pipeline.py @args *>> $Log
