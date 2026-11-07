#!/usr/bin/env bash
# Läuft auf der Oracle-VM, aufgerufen von deploy/deploy.ps1 (nicht von Hand nötig).
#   --first         Ersteinrichtung (server_setup.sh)
#   --overwrite-db  vorhandene Server-DB durch die hochgeladene ersetzen
set -euo pipefail

APP=/home/ubuntu/flashscore
cd "$APP"
sed -i 's/\r$//' deploy/*.sh deploy/flashscore.service

first=0; overwrite=0
for a in "$@"; do
  case "$a" in
    --first) first=1 ;;
    --overwrite-db) overwrite=1 ;;
  esac
done

[ "$first" = 1 ] && bash deploy/server_setup.sh

if [ -f /tmp/fs_db.sqlite.gz ]; then
  if [ -f data/flashscore.db ] && [ "$overwrite" = 0 ]; then
    echo "Server-DB existiert schon — NICHT überschrieben (deploy.ps1 -OverwriteDb erzwingt es)."
  else
    sudo systemctl stop flashscore || true
    rm -f data/flashscore.db-wal data/flashscore.db-shm
    gunzip -c /tmp/fs_db.sqlite.gz > data/flashscore.db
    echo "DB übernommen: $(du -h data/flashscore.db | cut -f1)"
  fi
  rm -f /tmp/fs_db.sqlite.gz
fi

if [ -f /tmp/fs_env ]; then
  if [ -f .env ]; then
    echo ".env existiert schon — behalten."
  else
    mv /tmp/fs_env .env
    chmod 600 .env
  fi
  rm -f /tmp/fs_env
fi

.venv/bin/pip install -q -r requirements.txt
sudo systemctl restart flashscore

for _ in $(seq 1 45); do
  if curl -fs http://127.0.0.1:8000/api/health > /tmp/fs_health.json; then
    echo "OK: $(head -c 400 /tmp/fs_health.json)"
    exit 0
  fi
  sleep 2
done
echo "Flashscore antwortet nicht. Log: sudo journalctl -u flashscore -n 50"
exit 1
