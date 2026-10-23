@echo off
rem Baut die React-Oberflaeche nach web\frontend\dist — die API liefert sie unter http://127.0.0.1:8000 aus.
rem Nur noetig nach Aenderungen am Frontend (web\frontend\src).
cd /d "%~dp0web\frontend"
if not exist node_modules call npm install
call npm run build
if errorlevel 1 (
    echo UI-Build fehlgeschlagen.
    pause
    exit /b 1
)
echo UI gebaut. API neu starten oder Seite neu laden.
