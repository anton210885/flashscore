@echo off
rem Beendet die im Hintergrund laufende API (inkl. UI + Live-Pipeline) auf Port 8000.
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ids = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique; if ($ids) { $ids | ForEach-Object { Stop-Process -Id $_ -Force }; Write-Host 'Flashscore gestoppt.' } else { Write-Host 'Flashscore laeuft nicht.' }; Start-Sleep -Seconds 3"
