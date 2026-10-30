@echo off
REM Fehlendes xG (beendete Spiele) und Glicko nachladen — neueste Spiele zuerst.
REM Fortschritt: Web-Oberflaeche -> DB Statistik, oder in diesem Fenster.
REM Nur xG:  start_backfill_xg.bat --only xg
REM Abbrechen mit Ctrl+C ist jederzeit moeglich, ein Neustart macht dort weiter.

cd /d "%~dp0"
set PYTHONUNBUFFERED=1
if not exist logs mkdir logs

python -u scripts\backfill_missing_xg_glicko.py %*

echo.
echo Fertig.
pause
