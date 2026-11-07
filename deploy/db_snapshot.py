"""Konsistente, gepackte Kopie der DB für den Server (sicher auch bei laufender API/Pipeline).

  python deploy/db_snapshot.py <ziel.sqlite>   ->  <ziel.sqlite>.gz
"""
import gzip
import shutil
import sqlite3
import sys

target = sys.argv[1]
src = sqlite3.connect("data/flashscore.db")
dst = sqlite3.connect(target)
src.backup(dst)
dst.close()
src.close()
with open(target, "rb") as f_in, gzip.open(target + ".gz", "wb", compresslevel=6) as f_out:
    shutil.copyfileobj(f_in, f_out)
