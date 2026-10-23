@echo off
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File "%~dp0start_web.ps1"
pause
