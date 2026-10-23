# FlashscoreTool Start-Skript (PowerShell)
# Sucht automatisch nach Python und startet das Tool

Write-Host "Suche nach Python..." -ForegroundColor Cyan

# Funktion zum Testen ob Python wirklich funktioniert (nicht nur Windows Store Stub)
function Test-PythonExecutable {
    param([string]$pythonPath)
    
    if (-not (Test-Path $pythonPath)) {
        return $false
    }
    
    # Ignoriere Windows Store Stub
    if ($pythonPath -like "*WindowsApps*") {
        return $false
    }
    
    try {
        $result = & $pythonPath --version 2>&1
        # Wenn es "Python wurde nicht gefunden" oder ähnliches ausgibt, ist es ein Stub
        if ($result -like "*nicht gefunden*" -or $result -like "*not found*" -or $result -like "*Microsoft Store*") {
            return $false
        }
        # Wenn es eine Versionsnummer ausgibt, ist es echt
        if ($result -match "Python \d+\.\d+") {
            return $true
        }
    } catch {
        return $false
    }
    return $false
}

$pythonCmd = $null

# Prüfe zuerst, ob python im PATH ist (aber ignoriere Windows Store Stub)
$pythonCommands = @('python', 'python3', 'py')
foreach ($cmd in $pythonCommands) {
    try {
        $result = & $cmd --version 2>&1
        # Prüfe ob es ein echter Python ist (nicht Windows Store Stub)
        if ($LASTEXITCODE -eq 0 -and $result -match "Python \d+\.\d+" -and $result -notlike "*Microsoft Store*") {
            $pythonCmd = $cmd
            Write-Host "Python gefunden: $cmd ($result)" -ForegroundColor Green
            break
        }
    } catch {
        continue
    }
}

# Prüfe typische Installationspfade
if (-not $pythonCmd) {
    $pythonPaths = @(
        'C:\Python311\python.exe',
        'C:\Python310\python.exe',
        'C:\Python39\python.exe',
        'C:\Python38\python.exe',
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python39\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python38\python.exe"
    )
    
    foreach ($path in $pythonPaths) {
        if (Test-PythonExecutable $path) {
            $pythonCmd = $path
            Write-Host "Python gefunden: $path" -ForegroundColor Green
            break
        }
    }
    
    # Suche rekursiv in typischen Installationsverzeichnissen
    if (-not $pythonCmd) {
        $searchPaths = @(
            "C:\Python*",
            "$env:LOCALAPPDATA\Programs\Python"
        )
        
        foreach ($searchPath in $searchPaths) {
            $found = Get-ChildItem -Path $searchPath -Recurse -Filter "python.exe" -ErrorAction SilentlyContinue | 
                     Where-Object { Test-PythonExecutable $_.FullName } | 
                     Select-Object -First 1
            
            if ($found) {
                $pythonCmd = $found.FullName
                Write-Host "Python gefunden: $pythonCmd" -ForegroundColor Green
                break
            }
        }
    }
}

# Python nicht gefunden
if (-not $pythonCmd) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "FEHLER: Python wurde nicht gefunden!" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "Python ist nicht installiert oder nicht im PATH." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Loesungsmoeglichkeiten:" -ForegroundColor Cyan
    Write-Host "1. Python installieren:" -ForegroundColor White
    Write-Host "   Download: https://www.python.org/downloads/" -ForegroundColor Gray
    Write-Host "   WICHTIG: Bei Installation 'Add Python to PATH' aktivieren!" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "2. Python manuell zum PATH hinzufuegen:" -ForegroundColor White
    Write-Host "   - Windows-Taste + R -> sysdm.cpl" -ForegroundColor Gray
    Write-Host "   - Tab 'Erweitert' -> 'Umgebungsvariablen'" -ForegroundColor Gray
    Write-Host "   - Unter 'Systemvariablen' -> 'Path' -> 'Bearbeiten'" -ForegroundColor Gray
    Write-Host "   - Python-Pfad hinzufuegen (z.B. C:\Python311)" -ForegroundColor Gray
    Write-Host ""
    Write-Host "3. Nach Installation: PowerShell/Terminal NEU STARTEN!" -ForegroundColor Yellow
    Write-Host ""
    
    # Versuche Windows Store Python zu öffnen
    $storePython = "$env:LOCALAPPDATA\Microsoft\WindowsApps\python.exe"
    if (Test-Path $storePython) {
        Write-Host "Hinweis: Windows Store Python-Stub gefunden." -ForegroundColor Yellow
        Write-Host "Dieser leitet nur zum Store weiter. Bitte installieren Sie Python von python.org" -ForegroundColor Yellow
        Write-Host ""
    }
    
    if (-not $env:CI) {
        Read-Host "Druecken Sie Enter zum Beenden"
    }
    exit 1
}

Write-Host ""
Write-Host "Starte FlashscoreTool..." -ForegroundColor Cyan
Write-Host ""

# Prüfe ob --gui Parameter übergeben wurde
$hasGuiFlag = $false

# Prüfe $args Array (wird verwendet wenn Skript mit .\start.ps1 --gui aufgerufen wird)
if ($args) {
    foreach ($arg in $args) {
        if ($arg -eq '--gui' -or $arg -eq '-gui') {
            $hasGuiFlag = $true
            Write-Host "GUI-Flag erkannt aus args: $arg" -ForegroundColor Yellow
            break
        }
    }
}

# Prüfe auch die Kommandozeile direkt (für den Fall dass $args nicht funktioniert)
if (-not $hasGuiFlag) {
    $cmdLine = $MyInvocation.Line
    if ($cmdLine -and ($cmdLine -like '*--gui*' -or $cmdLine -like '*-gui*')) {
        $hasGuiFlag = $true
        Write-Host "GUI-Flag erkannt aus Kommandozeile" -ForegroundColor Yellow
    }
}

if ($hasGuiFlag) {
    Write-Host "Starte GUI-Modus..." -ForegroundColor Green
    & $pythonCmd main.py --gui
} else {
    Write-Host "Starte CLI-Modus..." -ForegroundColor Cyan
    & $pythonCmd main.py
}

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "FEHLER beim Starten des Tools!" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "Moegliche Ursachen:" -ForegroundColor Yellow
    Write-Host "- Fehlende Abhaengigkeiten (pip install -r requirements.txt)" -ForegroundColor Yellow
    Write-Host "- Import-Fehler" -ForegroundColor Yellow
    Write-Host ""
    if (-not $env:CI) {
        try {
            Read-Host "Druecken Sie Enter zum Beenden"
        } catch {
            # Ignoriere Read-Host Fehler im NonInteractive-Modus
        }
    }
}

