# Flashscore dauerhaft auf Oracle Cloud (Always Free)

Ziel: Flashscore läuft rund um die Uhr auf einer kostenlosen Oracle-VM — Pipeline, Verifikation,
Swisslos-Quoten. Du greifst von PC und iPhone über **Tailscale** darauf zu (privates Netz, kein offener Port).

> **Wichtig:** Die App hat kein Login. Port 8000 darf in Oracle **nie** öffentlich geöffnet werden.

---

## 1. Oracle-Konto anlegen (machst du selbst)

1. <https://www.oracle.com/cloud/free/> → „Start for free“.
2. **Home Region: Switzerland North (Zurich)** wählen. Lässt sich später nicht ändern.
   Zürich = Schweizer IP, wichtig für die Swisslos-Quoten.
3. Kreditkarte wird nur zur Prüfung verlangt. Always-Free-Ressourcen kosten nichts.
4. Empfehlung nach ein paar Tagen: Konto auf **Pay As You Go** umstellen (bleibt gratis, solange du
   in den Always-Free-Grenzen bleibst). Dann löscht Oracle die VM nicht wegen „Leerlauf“ und
   ARM-VMs sind leichter zu bekommen.

## 2. VM erstellen

Menü → Compute → Instances → **Create instance**

| Feld | Wert |
|---|---|
| Name | `flashscore` |
| Image | **Canonical Ubuntu 24.04** |
| Shape | **VM.Standard.A1.Flex** (Ampere/ARM), **2 OCPU, 12 GB RAM** |
| Networking | Standard-VCN, öffentliche IPv4 zuweisen: ja |
| SSH keys | **„Generate a key pair“ → Private Key herunterladen** |
| Boot volume | Standard (≈47 GB) reicht |

- Meldung „Out of capacity“: anderes Availability Domain probieren oder später nochmals.
  Notlösung: `VM.Standard.E2.1.Micro` (1 GB RAM, langsam; das Setup legt dann Swap an).
- **Keine** Ingress-Regel für Port 8000 hinzufügen.
- Nach dem Start: **Public IP address** der Instanz notieren.

## 3. SSH vom PC einrichten

PowerShell:

```powershell
mkdir $HOME\.ssh -Force
Move-Item $HOME\Downloads\ssh-key-*.key $HOME\.ssh\oracle_flashscore.key
icacls $HOME\.ssh\oracle_flashscore.key /inheritance:r /grant:r "$($env:USERNAME):R"
notepad $HOME\.ssh\config
```

In `config` eintragen (IP ersetzen):

```
Host flashscore-oracle
  HostName 123.45.67.89
  User ubuntu
  IdentityFile ~/.ssh/oracle_flashscore.key
```

Test: `ssh flashscore-oracle` → einmal „yes“ bestätigen → du bist auf der VM (`exit` zum Verlassen).

## 4. Flashscore installieren

Im Projektordner (die deploy-Dateien müssen committet sein, hochgeladen wird der letzte Commit):

```powershell
powershell -ExecutionPolicy Bypass -File deploy\deploy.ps1 -FirstInstall
```

Das Skript baut die UI, packt den Code, macht eine konsistente DB-Kopie (~160 MB gepackt),
lädt alles samt `.env` hoch, installiert Python + Pakete, richtet den Dienst `flashscore` ein
und prüft `/api/health`. Dauer: ca. 5–10 Minuten.

## 5. Tailscale (Zugriff von PC und iPhone)

1. Tailscale-Konto anlegen: <https://tailscale.com> (gratis für privat).
2. Auf der VM (`ssh flashscore-oracle`):
   ```bash
   curl -fsSL https://tailscale.com/install.sh | sh
   sudo tailscale up
   ```
   Den angezeigten Link im Browser öffnen und die VM bestätigen.
3. Tailscale auf dem **PC** und dem **iPhone** installieren, mit demselben Konto anmelden.
4. Aufrufen: **http://flashscore:8000** (Name der VM in Tailscale; sonst die `100.x.y.z`-Adresse
   aus der Tailscale-App).

## 6. iPhone-Apps neu hinzufügen

Die alten Home-Bildschirm-Apps zeigen auf `192.168.1.46`. Löschen und in Safari neu anlegen:

- Flashscore: `http://flashscore:8000` → Teilen → „Zum Home-Bildschirm“
- SL Tipps: `http://flashscore:8000/sl` → Teilen → „Zum Home-Bildschirm“

Tailscale muss auf dem iPhone verbunden sein (geht auch unterwegs mit Mobilfunk).

## 7. Lokales Flashscore abschalten

Sonst laufen zwei Pipelines (doppelte API-Abfragen) und zwei Datenbanken laufen auseinander:

```powershell
.\stop_web.bat
powershell -ExecutionPolicy Bypass -File autostart.ps1 -Remove
```

Ab jetzt ist die **Server-DB die echte**. Die lokale `data/flashscore.db` ist nur noch ein alter Stand.

---

## Updates einspielen

Nach Änderungen committen, dann:

```powershell
powershell -ExecutionPolicy Bypass -File deploy\deploy.ps1
```

Lädt Code + UI hoch und startet neu. DB, `.env` und die Strategie-Presets auf dem Server bleiben unberührt.

## Nützliche Befehle auf der VM

```bash
sudo systemctl status flashscore          # läuft er?
sudo journalctl -u flashscore -n 100 -f   # Log live
sudo systemctl restart flashscore         # Neustart
free -h; df -h                            # RAM / Platz
```

## Server-DB auf den PC holen (Backup / lokal analysieren)

```powershell
ssh flashscore-oracle "sqlite3 ~/flashscore/data/flashscore.db '.backup /tmp/fs_backup.db' && gzip -f /tmp/fs_backup.db"
scp flashscore-oracle:/tmp/fs_backup.db.gz .
```

## sstats über Cloudflare WARP

sstats bricht Antworten an Cloud-IPs (Oracle) nach ~30 KB ab, die Tagesliste kommt so nie an.
Darum läuft auf der VM Cloudflare WARP als lokaler SOCKS-Proxy, und nur die sstats-Abfragen gehen darüber:

```bash
# einmalig (offizielles Paket von pkg.cloudflareclient.com)
sudo apt-get install -y cloudflare-warp
warp-cli --accept-tos registration new
warp-cli --accept-tos mode proxy          # nur Proxy, Routing/SSH/Tailscale bleiben unberührt
warp-cli --accept-tos proxy port 40000
warp-cli --accept-tos connect
echo 'SSTATS_PROXY=socks5h://127.0.0.1:40000' >> ~/flashscore/.env
sudo systemctl restart flashscore
```

Prüfen: `warp-cli --accept-tos status` → „Connected“.

## Bekannte Punkte

- **Swisslos** von einer Rechenzentrums-IP: sollte aus Zürich gehen, ist aber nicht garantiert.
  Nach der Installation in der Verifikation prüfen, ob Swisslos-Quoten weiter ankommen.
- **Hintergrund-Skripte** (z. B. xG-Nachladen) laufen auf dem Server per SSH:
  `cd ~/flashscore && nohup .venv/bin/python -u scripts/backfill_missing_xg_glicko.py > logs/backfill.log 2>&1 &`
