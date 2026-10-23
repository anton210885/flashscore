# Autostart bei Windows-Anmeldung ein-/ausschalten (Verknuepfung im Autostart-Ordner).
#   powershell -ExecutionPolicy Bypass -File autostart.ps1           -> einrichten
#   powershell -ExecutionPolicy Bypass -File autostart.ps1 -Remove   -> entfernen
param([switch]$Remove)
$ErrorActionPreference = "Stop"

$link = Join-Path ([Environment]::GetFolderPath("Startup")) "Flashscore.lnk"

if ($Remove) {
    if (Test-Path $link) {
        Remove-Item $link
        Write-Host "Autostart entfernt."
    } else {
        Write-Host "Kein Autostart eingerichtet."
    }
    exit 0
}

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($link)
$shortcut.TargetPath = Join-Path $env:WINDIR "System32\wscript.exe"
$shortcut.Arguments = "`"" + (Join-Path $PSScriptRoot "start_hidden.vbs") + "`" /nobrowser"
$shortcut.WorkingDirectory = $PSScriptRoot
$shortcut.Description = "Flashscore API + Live-Pipeline im Hintergrund"
$shortcut.Save()
Write-Host "Autostart eingerichtet: $link"
