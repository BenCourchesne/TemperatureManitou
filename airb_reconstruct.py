#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Reconstruction du champ `airb` (température Ecowitt) pendant le GEL du capteur
du 2026-07-23 05:05 au 2026-07-25 11:30 EDT, où il est resté figé à 10.80 °C.

Méthode : airb_est = air(quai) + décalage_horaire, où le décalage par heure de
la journée est calibré sur les lectures saines (airb valide) avant/après le gel.
Le quai bat la véranda (RMSE 1.20° vs 1.56°) car la véranda dérive en après-midi.

Chaque lecture corrigée reçoit "airb_est": true (traçable, réversible : toute
ligne avec ce marqueur avait airb=10.80 à l'origine). Un backup JSON complet des
lignes originales est aussi écrit dans backups/.

Usage :
    python airb_reconstruct.py           # DRY-RUN (n'écrit rien)
    python airb_reconstruct.py --write    # applique les PATCH sur Firebase
"""
import sys, json, math, os
from datetime import datetime, timezone, timedelta
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
cfg = open(os.path.join(HERE, "backfill_veranda.py"), encoding="utf-8").read()
import re
FB_WRITER_EMAIL = re.search(r'FB_WRITER_EMAIL\s*=\s*"([^"]+)"', cfg).group(1)
FB_WRITER_PASS  = re.search(r'FB_WRITER_PASS\s*=\s*"([^"]+)"', cfg).group(1)
API_KEY         = re.search(r'API_KEY\s*=\s*"([^"]+)"', cfg).group(1)
FB = "https://lac-manitou-temperatures-d284a-default-rtdb.firebaseio.com"

TZ = timezone(timedelta(hours=-4))  # EDT
def fmt(ts): return datetime.fromtimestamp(ts, TZ).strftime("%m-%d %H:%M")
def hour_of(ts): return datetime.fromtimestamp(ts, TZ).hour

FROZEN_VAL = 10.80
# Le capteur a décroché vers 04:00 (pas 05:05) et repris à 11:30 : fenêtre large.
FREEZE0 = datetime(2026, 7, 23, 3, 55,  tzinfo=TZ).timestamp()
FREEZE1 = datetime(2026, 7, 25, 11, 31, tzinfo=TZ).timestamp()

WRITE = "--write" in sys.argv

# ── 1. Charger les lectures (référence large + fenêtre de gel) ────────────────
ms0 = int(datetime(2026, 7, 17, tzinfo=TZ).timestamp() * 1000)
ms1 = int(datetime(2026, 7, 26, 12, tzinfo=TZ).timestamp() * 1000)
data = requests.get(f'{FB}/readings.json?orderBy="$key"&startAt="{ms0}"&endAt="{ms1}"',
                    timeout=120).json() or {}
rows = sorted(((k, int(k) / 1000, v) for k, v in data.items()), key=lambda x: x[1])

# Idempotent : les lignes déjà reconstruites (airb_est) sont exclues à la fois
# des cibles (leur airb n'est plus 10.80) et de la référence (ne pas calibrer
# l'offset sur des valeurs estimées).
ref, frozen = [], []
for k, ts, r in rows:
    if r.get("airb_est"):
        continue
    if FREEZE0 <= ts <= FREEZE1 and r.get("airb") is not None \
            and abs(r["airb"] - FROZEN_VAL) < 0.05:
        frozen.append((k, ts, r))
    elif r.get("airb") is not None:
        ref.append((ts, r))

# ── 2. Profil horaire de décalage airb - air(quai) sur les données saines ────
buckets = {h: [] for h in range(24)}
for ts, r in ref:
    if r.get("air") is not None:
        buckets[hour_of(ts)].append(r["airb"] - r["air"])
offset = {h: (sum(d) / len(d)) for h, d in buckets.items() if d}
print(f"Référence saine : {len(ref)} lectures | Gel : {len(frozen)} lectures à corriger")
print("Décalage horaire airb-air (quai) calibré :")
for h in range(24):
    if h in offset:
        print(f"   {h:02d}h : {offset[h]:+.2f}°", end="")
        if (h + 1) % 6 == 0: print()
print()

# ── 3. Backup des lignes originales (fusion, jamais d'écrasement) ─────────────
# On n'écrit un backup que s'il y a des cibles, et on FUSIONNE avec l'existant :
# un dry-run sans cible ne doit jamais vider un backup déjà écrit.
bdir = os.path.join(HERE, "backups")
os.makedirs(bdir, exist_ok=True)
bpath = os.path.join(bdir, "airb_blackout_20260723.json")
if frozen:
    bk = {"note": "airb original (figé à 10.80) avant reconstruction quai+offset",
          "freeze": "2026-07-23 04:00 → 2026-07-25 11:30 EDT", "original": {}}
    if os.path.exists(bpath):
        try: bk = json.load(open(bpath, encoding="utf-8"))
        except Exception: pass
    for k, ts, r in frozen:
        bk["original"].setdefault(k, {"airb": r.get("airb")})
    bk["count"] = len(bk["original"])
    json.dump(bk, open(bpath, "w", encoding="utf-8"), indent=2)
    print(f"Backup fusionné : {bpath} ({len(bk['original'])} lignes)")
else:
    print("Aucune cible → backup inchangé.")

# ── 4. Calcul des valeurs reconstruites ──────────────────────────────────────
patches = []
skipped = 0
for k, ts, r in frozen:
    h = hour_of(ts)
    air = r.get("air")
    if air is not None and h in offset:
        newv = round(air + offset[h], 1)
        patches.append((k, ts, newv))
    else:
        skipped += 1

vals = [v for _, _, v in patches]
print(f"\nReconstruction : {len(patches)} valeurs calculées, {skipped} ignorées (air manquant)")
if vals:
    print(f"  Nouvelle plage airb : {min(vals):.1f}° → {max(vals):.1f}°  (vs 10.8 figé)")
print("  Aperçu (toutes les ~3h) :")
last = 0
for k, ts, v in patches:
    if ts - last < 10800: continue
    last = ts
    print(f"    {fmt(ts)} h{hour_of(ts):02d} : 10.8 → {v}")

# ── 5. Écriture (si --write) ─────────────────────────────────────────────────
if not WRITE:
    print("\n[DRY-RUN] Rien écrit. Relance avec --write pour appliquer.")
    sys.exit(0)

def fb_signin():
    r = requests.post(
        f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={API_KEY}",
        json={"email": FB_WRITER_EMAIL, "password": FB_WRITER_PASS, "returnSecureToken": True},
        timeout=30)
    if r.status_code != 200:
        raise SystemExit(f"Auth Firebase échouée : {r.status_code}")
    return r.json()["idToken"]

token = fb_signin()
ok = fail = 0
for k, ts, v in patches:
    rr = requests.patch(f"{FB}/readings/{k}.json?auth={token}",
                        json={"airb": v, "airb_est": True}, timeout=30)
    if rr.status_code == 200:
        ok += 1
    else:
        fail += 1
        if fail <= 5:
            print(f"  échec {k} : {rr.status_code} {rr.text[:80]}")
print(f"\nTerminé : {ok} lectures corrigées, {fail} échecs.")
