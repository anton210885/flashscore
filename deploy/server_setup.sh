#!/usr/bin/env bash
# Einmalig auf der Oracle-VM (Ubuntu 24.04) ausführen — macht deploy/deploy.ps1 -FirstInstall automatisch.
# Installiert Python, legt ~/flashscore an, richtet Swap (bei wenig RAM) und den systemd-Dienst ein.
set -euo pipefail

APP=/home/ubuntu/flashscore

sudo apt-get update -y
sudo apt-get install -y python3-venv python3-pip sqlite3 tzdata
sudo timedatectl set-timezone Europe/Zurich

# Kleine VM (1 GB, VM.Standard.E2.1.Micro): 2 GB Swap, sonst bricht pandas/pip ab
mem_mb=$(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo)
if [ "$mem_mb" -lt 4000 ] && [ ! -f /swapfile ]; then
  sudo fallocate -l 2G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
fi

mkdir -p "$APP/data" "$APP/logs"
[ -d "$APP/.venv" ] || python3 -m venv "$APP/.venv"
"$APP/.venv/bin/pip" install --upgrade pip
"$APP/.venv/bin/pip" install -r "$APP/requirements.txt"

sudo cp "$APP/deploy/flashscore.service" /etc/systemd/system/flashscore.service
sudo systemctl daemon-reload
sudo systemctl enable flashscore
echo "Setup fertig. Start: sudo systemctl restart flashscore"
