@echo off
rem Normalbetrieb: API + UI + Live-Pipeline ohne Fenster, oeffnet http://127.0.0.1:8000
rem Entwickeln mit sichtbaren Fenstern und Live-Reload (:5173): start_dev.bat
start "" wscript.exe "%~dp0start_hidden.vbs"
