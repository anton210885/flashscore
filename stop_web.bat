@echo off
rem Beendet API (inkl. UI + Live-Pipeline, Port 8000) und einen evtl. laufenden Vite-Entwicklungsserver (Port 5173).
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ids = Get-NetTCPConnection -LocalPort 8000,5173 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique; if ($ids) { $ids | ForEach-Object { Stop-Process -Id $_ -Force }; Write-Host 'Flashscore gestoppt.' } else { Write-Host 'Flashscore laeuft nicht.' }; Start-Sleep -Seconds 3"
