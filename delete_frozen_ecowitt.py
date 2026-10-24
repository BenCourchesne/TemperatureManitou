#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Supprime les champs Ecowitt FIGÉS pendant le blackout upload passerelle→HA
(2026-07-23 → 07-25). Tout le device gw3000b a cessé d'uploader vers Home
Assistant pendant ~54h ; l'automation 5 min a recopié la dernière valeur connue
de chaque champ. Résultat : humb/wind/gust/wdir/rrate/rday/uv/solar/press figés.

Aucune source de secours pour la plupart → on SUPPRIME les valeurs figées (le
frontend affiche un trou honnête ; pour humb il retombe sur la véranda via
`val('humidity') = humb ?? hum`). `airb`, déjà reconstruit depuis le quai, est
conservé.

On ne supprime un champ que si sa valeur == la constante figée (relevée au cœur
du gel), pour préserver les vraies valeurs juste avant/après le décrochage.

Usage : python delete_frozen_ecowitt.py         (DRY-RUN)
        python delete_frozen_ecowitt.py --write
"""
import sys, re, os, json
from datetime import datetime, timezone, timedelta
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
cfg = open(os.path.join(HERE, "backfill_veranda.py"), encoding="utf-8").read()
EMAIL = re.search(r'FB_WRITER_EMAIL\s*=\s*"([^"]+)"', cfg).group(1)
PASS  = re.search(r'FB_WRITER_PASS\s*=\s*"([^"]+)"', cfg).group(1)
KEY   = re.search(r'API_KEY\s*=\s*"([^"]+)"', cfg).group(1)
FB = "https://lac-manitou-temperatures-d284a-default-rtdb.firebaseio.com"
TZ = timezone(timedelta(hours=-4))
def fmt(ts): return datetime.fromtimestamp(ts, TZ).strftime("%m-%d %H:%M")
WRITE = "--write" in sys.argv

FIELDS = ["humb", "wind", "gust", "wdir", "rrate", "rday", "uv", "solar", "press"]

ms0 = int(datetime(2026, 7, 23, 3, 55, tzinfo=TZ).timestamp() * 1000)
ms1 = int(datetime(2026, 7, 25, 11, 31, tzinfo=TZ).timestamp() * 1000)
data = requests.get(f'{FB}/readings.json?orderBy="$key"&startAt="{ms0}"&endAt="{ms1}"', timeout=120).json() or {}
rows = sorted(((k, int(k) / 1000, v) for k, v in data.items()), key=lambda x: x[1])

# Constante figée de chaque champ : relevée au cœur du gel (24 juil ~12:00)
deep_ts = datetime(2026, 7, 24, 12, tzinfo=TZ).timestamp()
deep = min(rows, key=lambda x: abs(x[1] - deep_ts))[2]
frozen_const = {f: deep.get(f) for f in FIELDS}
print("Constantes figées (relevées le " + fmt(deep_ts) + ") :")
print("  " + ", ".join(f"{f}={frozen_const[f]}" for f in FIELDS) + "\n")

# Cibles = lignes du gel (airb_est). On supprime chaque champ == sa constante figée.
patches = {}   # key -> {field: None}
backup  = {}   # key -> {field: valeur supprimée}
n_fields = 0
for k, ts, r in rows:
    if not r.get("airb_est"):
        continue
    dele = {f: None for f in FIELDS if r.get(f) is not None and r.get(f) == frozen_const[f]}
    if dele:
        patches[k] = dele
        backup[k] = {f: r.get(f) for f in dele}
        n_fields += len(dele)

print(f"Lignes touchées : {len(patches)} | suppressions de champs : {n_fields}")
# aperçu
for i, (k, ts, r) in enumerate(rows):
    if k in patches and i % 120 == 0:
        print(f"  {fmt(ts)} : supprime {list(patches[k])}")

# backup
bdir = os.path.join(HERE, "backups"); os.makedirs(bdir, exist_ok=True)
bpath = os.path.join(bdir, "ecowitt_frozen_20260723.json")
if patches:
    json.dump({"note": "Champs Ecowitt figés (device gw3000b n'uploadait plus vers HA "
                        "~54h) supprimés de /readings. Valeurs d'origine ci-dessous.",
               "freeze": "2026-07-23 05:05 → 2026-07-25 11:30 EDT",
               "frozen_const": frozen_const, "count_rows": len(backup), "original": backup},
              open(bpath, "w", encoding="utf-8"), indent=2)
    print(f"\nBackup : {bpath} ({len(backup)} lignes)")

if not WRITE:
    print("\n[DRY-RUN] Rien supprimé. Relance avec --write."); sys.exit(0)

tok = requests.post(f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={KEY}",
    json={"email": EMAIL, "password": PASS, "returnSecureToken": True}, timeout=30).json()["idToken"]
ok = fail = 0
for k, dele in patches.items():
    rr = requests.patch(f"{FB}/readings/{k}.json?auth={tok}", json=dele, timeout=30)
    if rr.status_code == 200: ok += 1
    else:
        fail += 1
        if fail <= 5: print(f"  échec {k}: {rr.status_code} {rr.text[:80]}")
print(f"\nTerminé : {ok} lignes nettoyées, {fail} échecs.")
