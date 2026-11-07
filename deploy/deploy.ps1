# Flashscore auf die Oracle-VM bringen (Code + fertige UI). Anleitung: deploy/ORACLE.md
#
#   powershell -ExecutionPolicy Bypass -File deploy\deploy.ps1 -FirstInstall   # einmalig: Setup + DB + .env
#   powershell -ExecutionPolicy Bypass -File deploy\deploy.ps1                 # Updates: nur Code + UI
#
# Hochgeladen wird der letzte Commit (git archive HEAD), nicht ungespeicherte Aenderungen.
# Was der Server selbst schreibt (Strategie-Presets, DB, .env), wird bei Updates nie ueberschrieben.
param(
    [string]$Server = "flashscore-oracle",   # Host-Alias aus ~/.ssh/config
    [switch]$FirstInstall,
    [switch]$OverwriteDb,
    [switch]$SkipBuild
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

# Vom Server verwaltet: bei Updates nicht mitschicken
$serverOwned = @("data/strategy_presets.json", "data/liga128_leagues.json", "data/league_watchlist.json")

$dirty = git status --porcelain | Where-Object { $_ -notmatch "data/strategy_presets.json" }
if ($dirty) {
    Write-Warning "Nicht committete Aenderungen werden NICHT hochgeladen:`n$($dirty -join "`n")"
}

if (-not $SkipBuild) {
    Write-Host "UI bauen ..."
    Push-Location web\frontend
    npm.cmd run build | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "UI-Build fehlgeschlagen" }
    Pop-Location
}

$tmp = Join-Path $env:TEMP "flashscore_deploy"
$stage = Join-Path $tmp "stage"
if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }
New-Item -ItemType Directory -Force $stage | Out-Null

git archive --format=tar -o "$tmp\code.tar" HEAD
tar -xf "$tmp\code.tar" -C $stage
foreach ($f in $serverOwned) {
    $p = Join-Path $stage $f
    if ($FirstInstall -and (Test-Path $f)) { Copy-Item $f $p -Force }   # Erstinstallation: lokalen Stand mitnehmen
    elseif (Test-Path $p) { Remove-Item $p }
}
Copy-Item -Recurse web\frontend\dist (Join-Path $stage "web\frontend\dist")
@{
    version     = (git describe --tags --always)
    commit_date = (git log -1 --format=%cd --date=format:"%Y-%m-%d %H:%M")
} | ConvertTo-Json | Out-File -Encoding ascii (Join-Path $stage "VERSION.json")
tar -czf "$tmp\fs_bundle.tgz" -C $stage .

$uploads = @("$tmp\fs_bundle.tgz")
$flags = @()
if ($FirstInstall) {
    $flags += "--first"
    Write-Host "DB-Kopie erstellen (laeuft auch, waehrend Flashscore lokal laeuft) ..."
    $db = "$tmp\fs_db.sqlite"
    python deploy\db_snapshot.py $db
    if ($LASTEXITCODE -ne 0) { throw "DB-Kopie fehlgeschlagen" }
    $uploads += "$db.gz"
    if (Test-Path .env) {
        Copy-Item .env "$tmp\fs_env"
        $uploads += "$tmp\fs_env"
    }
}
if ($OverwriteDb) { $flags += "--overwrite-db" }

# Ab hier zaehlt der Exit-Code: Fortschritt auf stderr (pip, systemd) soll nicht abbrechen
$ErrorActionPreference = "Continue"
Write-Host "Hochladen nach $Server ..."
scp @uploads "${Server}:/tmp/"
if ($LASTEXITCODE -ne 0) { throw "scp fehlgeschlagen - SSH-Zugang pruefen (deploy/ORACLE.md, Schritt 3)" }

$remote = "mkdir -p ~/flashscore && tar -xzf /tmp/fs_bundle.tgz -C ~/flashscore && rm /tmp/fs_bundle.tgz && sed -i 's/\r$//' ~/flashscore/deploy/*.sh && bash ~/flashscore/deploy/remote_update.sh $($flags -join ' ')"
ssh $Server $remote
if ($LASTEXITCODE -ne 0) { throw "Server-Update fehlgeschlagen" }
Remove-Item -Recurse -Force $tmp
Write-Host "Fertig."
