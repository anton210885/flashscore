# Anleitung: FlashscoreTool starten

## Normalbetrieb (ohne Fenster)

- **Starten:** Doppelklick auf `start_web.bat` (oder `start_hidden.vbs`) → öffnet http://127.0.0.1:8000
  (API, Oberfläche und Live-Pipeline laufen unsichtbar im Hintergrund)
- **Stoppen:** Doppelklick auf `stop_web.bat`
- **Autostart bei Anmeldung:** `powershell -ExecutionPolicy Bypass -File autostart.ps1`
  (entfernen mit `-Remove`)
- **Nach Änderungen am Frontend** (`web\frontend\src`): `build_ui.bat`, dann Seite neu laden
- **Fehler/Ausgaben:** `logs\uvicorn.log` und `logs\uvicorn.log.err`

Zum Entwickeln mit sichtbaren Fenstern und Live-Reload (:5173): `start_dev.bat`.

## Problem: Python nicht gefunden

Wenn Sie die Fehlermeldung sehen:
```
python : Die Benennung "python" wurde nicht als Name eines Cmdlet... erkannt
```

bedeutet das, dass Python nicht im PATH ist.

## Lösung 1: Start-Skript verwenden (Einfachste Methode)

Doppelklicken Sie auf eine der folgenden Dateien:
- **`start.bat`** - Startet das Tool im CLI-Modus
- **`start_gui.bat`** - Startet das Tool mit GUI

Das Skript sucht automatisch nach Python und startet das Tool.

## Lösung 2: Python zum PATH hinzufügen

1. **Python installieren** (falls noch nicht installiert):
   - Download: https://www.python.org/downloads/
   - Bei der Installation: **"Add Python to PATH"** aktivieren ✅

2. **Falls Python bereits installiert ist**, aber nicht im PATH:
   - Windows-Taste + R drücken
   - `sysdm.cpl` eingeben und Enter
   - Tab "Erweitert" → "Umgebungsvariablen"
   - Unter "Systemvariablen" → "Path" auswählen → "Bearbeiten"
   - "Neu" klicken und Python-Pfad hinzufügen, z.B.:
     - `C:\Python311`
     - `C:\Users\IhrName\AppData\Local\Programs\Python\Python311`
   - Alle Dialoge mit "OK" schließen
   - **PowerShell/Terminal neu starten**

3. **Testen**:
   ```powershell
   python --version
   ```

## Lösung 3: Abhängigkeiten installieren

Nachdem Python funktioniert, installieren Sie die benötigten Pakete:

```powershell
pip install -r requirements.txt
```

oder einzeln:
```powershell
pip install requests matplotlib
```

## Tool starten

Nachdem alles eingerichtet ist:

**CLI-Modus:**
```powershell
python main.py
```

**GUI-Modus (Tkinter):**
```powershell
python main.py --gui
```

**Web-UI (React + FastAPI):**
```powershell
pip install -r requirements.txt
cd web\frontend
npm install
cd ..\..
.\start_web.ps1
```
Dann öffnen: http://127.0.0.1:5173  
API-Docs: http://127.0.0.1:8000/docs  
Details: `web/README.md`

## Hilfe bei weiteren Problemen

Falls weiterhin Fehler auftreten:
1. Prüfen Sie, ob alle `__init__.py` Dateien vorhanden sind
2. Prüfen Sie, ob alle Abhängigkeiten installiert sind
3. Prüfen Sie die Fehlermeldung genau - sie zeigt meist das Problem

