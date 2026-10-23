@echo off
rem Entwickeln: API + Vite (Live-Reload) in zwei sichtbaren Fenstern, UI unter http://127.0.0.1:5173
rem Normalbetrieb ohne Fenster: start_web.bat
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File "%~dp0start_web.ps1"
pause
