@echo off
REM FlashscoreTool Start-Skript
REM Sucht automatisch nach Python und startet das Tool

REM Typische Python-Installationspfade
set PYTHON_PATHS[0]=python
set PYTHON_PATHS[1]=python3
set PYTHON_PATHS[2]=py
set PYTHON_PATHS[3]=C:\Python311\python.exe
set PYTHON_PATHS[4]=C:\Python310\python.exe
set PYTHON_PATHS[5]=C:\Python39\python.exe
set PYTHON_PATHS[6]=C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python311\python.exe
set PYTHON_PATHS[7]=C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python310\python.exe
set PYTHON_PATHS[8]=C:\Users\%USERNAME%\AppData\Local\Microsoft\WindowsApps\python.exe

set PYTHON_CMD=

REM Prüfe zuerst, ob python im PATH ist
python --version >nul 2>&1
if %errorlevel% == 0 (
    set PYTHON_CMD=python
    goto :found
)

python3 --version >nul 2>&1
if %errorlevel% == 0 (
    set PYTHON_CMD=python3
    goto :found
)

py --version >nul 2>&1
if %errorlevel% == 0 (
    set PYTHON_CMD=py
    goto :found
)

REM Prüfe typische Installationspfade
for %%P in (
    "C:\Python311\python.exe"
    "C:\Python310\python.exe"
    "C:\Python39\python.exe"
    "C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python311\python.exe"
    "C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python310\python.exe"
    "C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python39\python.exe"
    "C:\Users\%USERNAME%\AppData\Local\Microsoft\WindowsApps\python.exe"
) do (
    if exist %%P (
        set PYTHON_CMD=%%P
        goto :found
    )
)

:not_found
echo.
echo ========================================
echo FEHLER: Python wurde nicht gefunden!
echo ========================================
echo.
echo Bitte installieren Sie Python von: https://www.python.org/downloads/
echo Wichtig: Aktivieren Sie bei der Installation "Add Python to PATH"
echo.
pause
exit /b 1

:found
echo Python gefunden: %PYTHON_CMD%
echo.
echo Starte FlashscoreTool...
echo.

REM Prüfe ob --gui Parameter übergeben wurde
if "%1"=="--gui" (
    %PYTHON_CMD% main.py --gui
) else (
    %PYTHON_CMD% main.py
)

if %errorlevel% neq 0 (
    echo.
    echo ========================================
    echo FEHLER beim Starten des Tools!
    echo ========================================
    echo.
    echo Moegliche Ursachen:
    echo - Fehlende Abhaengigkeiten (pip install -r requirements.txt)
    echo - Import-Fehler
    echo.
    pause
)

