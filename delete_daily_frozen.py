#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Supprime les buckets /daily des jours corrompus par le blackout Ecowitt
(UTC 2026-07-23, 07-24, 07-25). Ils avaient agrégé les valeurs figées ET
l'ancien airb=10.80 (calculés avant la reconstruction). Une fois supprimés,
l'agrégation HA (script.manitou_aggregate_daily) les reconstruit depuis les
/readings corrigés — champs Ecowitt supprimés → exclus (selectattr), airb
reconstruit → moyenne correcte.

Usage : python delete_daily_frozen.py          (DRY-RUN)
        python delete_daily_frozen.py --write
"""
import sys, re, os, json
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
cfg = open(os.path.join(HERE, "backfill_veranda.py"), encoding="utf-8").read()
EMAIL = re.search(r'FB_WRITER_EMAIL\s*=\s*"([^"]+)"', cfg).group(1)
PASS  = re.search(r'FB_WRITER_PASS\s*=\s*"([^"]+)"', cfg).group(1)
KEY   = re.search(r'API_KEY\s*=\s*"([^"]+)"', cfg).group(1)
FB = "https://lac-manitou-temperatures-d284a-default-rtdb.firebaseio.com"
WRITE = "--write" in sys.argv

KEYS = ["1784764800000",  # UTC 2026-07-23
        "1784851200000",  # UTC 2026-07-24 (jour entièrement gelé)
        "1784937600000"]  # UTC 2026-07-25

daily = requests.get(f'{FB}/daily.json', timeout=60).json() or {}
backup = {k: daily[k] for k in KEYS if k in daily}
print(f"Buckets /daily à supprimer : {list(backup)}")
for k, v in backup.items():
    print(f"  {k}: airb={v.get('airb')} humb={v.get('humb')} wind={v.get('wind')} press={v.get('press')}")

bdir = os.path.join(HERE, "backups"); os.makedirs(bdir, exist_ok=True)
json.dump({"note": "buckets /daily supprimés (corrompus par blackout Ecowitt), "
                   "à reconstruire via script.manitou_aggregate_daily",
           "original": backup},
          open(os.path.join(bdir, "daily_frozen_20260723.json"), "w", encoding="utf-8"), indent=2)

if not WRITE:
    print("\n[DRY-RUN] Rien supprimé. Relance avec --write."); sys.exit(0)

tok = requests.post(f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={KEY}",
    json={"email": EMAIL, "password": PASS, "returnSecureToken": True}, timeout=30).json()["idToken"]
rr = requests.patch(f"{FB}/daily.json?auth={tok}", json={k: None for k in KEYS}, timeout=30)
print(f"Suppression : {rr.status_code}")
